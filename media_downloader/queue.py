"""Sequential queue scheduler. GUI state is owned here; I/O lives in workers."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from uuid import uuid4

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot

from .ui.download_worker import DownloadWorker

ACTIVE = {"pending", "analyzing", "downloading", "converting", "cancelling"}


@dataclass
class QueueItem:
    url: str
    destination: str
    container: str = "MP4"
    quality: object = None
    quality_text: str = "Melhor disponível"
    title: str = ""
    thumbnail: str = ""
    group: str = ""
    format_id: str | None = None
    postprocessors: list = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex)
    state: str = "pending"
    progress: int = 0
    speed: float | None = None
    eta: float | None = None
    path: str = ""
    error: str = ""
    size: int | None = None
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def fingerprint(self):
        return (self.url.strip(), os.path.normcase(os.path.abspath(self.destination)), self.container,
                json.dumps(self.quality, sort_keys=True))


class DownloadQueue(QObject):
    structure_changed = Signal()
    item_changed = Signal(str)
    active_changed = Signal()
    item_finished = Signal(str)
    persist = Signal(dict)
    drained = Signal()

    def __init__(self, wrapper, parent=None):
        super().__init__(parent)
        self.wrapper = wrapper
        self.items = []
        self.thread = None
        self.worker = None
        self.current = None
        self.stopping = False
        self.remove_after = set()

    @property
    def busy(self):
        return self.thread is not None or any(i.state == "pending" for i in self.items)

    def add(self, items):
        if self.stopping:
            return []
        added = []
        fingerprints = {i.fingerprint for i in self.items if i.state in ACTIVE}
        for item in items:
            if item.fingerprint in fingerprints:
                continue
            fingerprints.add(item.fingerprint)
            self.items.append(item)
            self.persist.emit(asdict(item))
            added.append(item)
        if added:
            self.structure_changed.emit()
            self.active_changed.emit()
            self._start_next()
        return added

    def get(self, item_id):
        return next((i for i in self.items if i.id == item_id), None)

    def _notify(self, persist=False):
        if self.current:
            self.item_changed.emit(self.current.id)
            if persist:
                self.persist.emit(asdict(self.current))

    @Slot()
    def _start_next(self):
        if self.thread is not None or self.stopping:
            return
        self.current = next((i for i in self.items if i.state == "pending"), None)
        if self.current is None:
            self.active_changed.emit()
            self.drained.emit()
            return
        item = self.current
        item.state = "analyzing"
        worker = DownloadWorker(
            self.wrapper, item.url, item.format_id, None, item.postprocessors,
            destination=item.destination, container=item.container, quality=item.quality)
        thread = QThread(self)
        self.thread, self.worker = thread, worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._progress, Qt.ConnectionType.QueuedConnection)
        worker.details.connect(self._details, Qt.ConnectionType.QueuedConnection)
        worker.metadata.connect(self._metadata, Qt.ConnectionType.QueuedConnection)
        worker.status.connect(self._status, Qt.ConnectionType.QueuedConnection)
        worker.completed.connect(self._completed, Qt.ConnectionType.QueuedConnection)
        worker.error.connect(self._error, Qt.ConnectionType.QueuedConnection)
        worker.cancelled.connect(self._cancelled, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._cleanup, Qt.ConnectionType.QueuedConnection)
        self._notify(True)
        self.active_changed.emit()
        thread.start()

    @Slot(int)
    def _progress(self, value):
        if self.current.state != "cancelling":
            self.current.progress = value
            self._notify()

    @Slot(dict)
    def _details(self, data):
        if self.current.state != "cancelling":
            previous = self.current.state
            self.current.state = "downloading"
            self.current.speed = data.get("speed")
            self.current.eta = data.get("eta")
            self._notify(previous != self.current.state)

    @Slot(dict)
    def _metadata(self, info):
        for name in ("title", "thumbnail", "size"):
            if info.get(name) is not None:
                setattr(self.current, name, info[name])
        self._notify(True)

    @Slot(str)
    def _status(self, message):
        if self.current.state != "cancelling" and ("Processando" in message or "processando" in message):
            self.current.state = "converting"
            self._notify(True)

    @Slot(str)
    def _completed(self, path):
        self.current.path = path
        self.current.state = "completed"
        self.current.progress = 100
        self._notify(True)

    @Slot(str)
    def _error(self, message):
        self.current.state = "failed"
        self.current.error = message
        self._notify(True)

    @Slot()
    def _cancelled(self):
        self.current.state = "cancelled"
        self._notify(True)

    @Slot()
    def _cleanup(self):
        if not self.thread.wait(0):
            QTimer.singleShot(10, self, self._cleanup)
            return
        item = self.current
        if item.state in ACTIVE:
            item.state = "cancelled" if self.stopping else "failed"
            item.error = item.error or "Operação encerrada sem arquivo final."
            self._notify(True)
        self.thread.deleteLater()
        self.thread = self.worker = None
        self.current = None
        self.item_finished.emit(item.id)
        if item.id in self.remove_after:
            self.items.remove(item)
            self.remove_after.discard(item.id)
            self.structure_changed.emit()
        self.active_changed.emit()
        QTimer.singleShot(0, self, self._start_next)

    def cancel(self, item_id):
        item = self.get(item_id)
        if item is None or item.state not in ACTIVE:
            return
        if item is self.current:
            item.state = "cancelling"
            self.worker.cancel()
        else:
            item.state = "cancelled"
        self.persist.emit(asdict(item))
        self.item_changed.emit(item.id)
        self.active_changed.emit()

    def cancel_group(self, group):
        for item in self.items:
            if item.group == group:
                self.cancel(item.id)

    def cancel_all(self):
        for item in self.items:
            self.cancel(item.id)

    def remove(self, item_id):
        item = self.get(item_id)
        if item is self.current and item is not None:
            self.remove_after.add(item_id)
            self.cancel(item_id)
        elif item:
            self.cancel(item_id)
            self.items.remove(item)
            self.structure_changed.emit()

    def retry(self, item_id):
        item = self.get(item_id)
        if not self.stopping and item and item is not self.current and item.state not in ACTIVE and item.url:
            if any(i is not item and i.state in ACTIVE and i.fingerprint == item.fingerprint for i in self.items):
                return
            item.state, item.error, item.progress = "pending", "", 0
            item.path, item.size, item.speed, item.eta = "", None, None, None
            # Resolve fresh source formats for retries; IDs/URLs can expire.
            item.format_id = None
            self.persist.emit(asdict(item))
            self.item_changed.emit(item.id)
            self.active_changed.emit()
            QTimer.singleShot(0, self, self._start_next)

    def close(self):
        self.stopping = True
        self.cancel_all()
