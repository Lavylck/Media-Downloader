from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from ..downloader.yt_dlp_wrapper import OperationCancelled, check_cancelled


class AnalysisWorker(QObject):
    info_received = Signal(int, dict)
    finished = Signal(bool)
    error = Signal(int, str)
    status = Signal(int, str)
    cancelled = Signal(int)

    def __init__(self, ydl_wrapper, url, request_id=0, *, mode="single", offset=0):
        super().__init__()
        self.ydl_wrapper = ydl_wrapper
        self.url = url
        self.request_id = request_id
        self.cancel_event = Event()
        self.mode, self.offset = mode, offset

    def cancel(self):
        # Called by the GUI: Event.set is thread-safe, unlike a queued slot
        # which cannot execute while run() occupies the worker's event loop.
        self.cancel_event.set()

    def _status(self, message):
        self.status.emit(self.request_id, message)

    @Slot()
    def run(self):
        success = False
        try:
            self._status("Analisando URL…")
            if self.mode == "playlist":
                info = self.ydl_wrapper.playlist_page(
                    self.url, self.offset, cancel_event=self.cancel_event, status_hook=self._status)
            else:
                info = self.ydl_wrapper.extract_info(
                    self.url, cancel_event=self.cancel_event, status_hook=self._status)
            check_cancelled(self.cancel_event)
            self.info_received.emit(self.request_id, info)
            success = True
        except Exception as exc:
            if isinstance(exc, OperationCancelled) or self.cancel_event.is_set():
                self.cancelled.emit(self.request_id)
            else:
                self.error.emit(self.request_id, str(exc))
        finally:
            self.finished.emit(success)
