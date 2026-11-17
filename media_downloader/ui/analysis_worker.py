from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from ..downloader.yt_dlp_wrapper import OperationCancelled, check_cancelled


class AnalysisWorker(QObject):
    info_received = Signal(dict)
    finished = Signal(bool)
    error = Signal(str)
    status = Signal(str)
    cancelled = Signal()

    def __init__(self, ydl_wrapper, url):
        super().__init__()
        self.ydl_wrapper = ydl_wrapper
        self.url = url
        self.cancel_event = Event()

    def cancel(self):
        # Called by the GUI: Event.set is thread-safe, unlike a queued slot
        # which cannot execute while run() occupies the worker's event loop.
        self.cancel_event.set()

    @Slot()
    def run(self):
        success = False
        try:
            self.status.emit("Analisando URL…")
            info = self.ydl_wrapper.extract_info(
                self.url, cancel_event=self.cancel_event, status_hook=self.status.emit)
            check_cancelled(self.cancel_event)
            self.info_received.emit(info)
            success = True
        except Exception as exc:
            if isinstance(exc, OperationCancelled) or self.cancel_event.is_set():
                self.cancelled.emit()
            else:
                self.error.emit(str(exc))
        finally:
            self.finished.emit(success)
