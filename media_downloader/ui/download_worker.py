from threading import Event
from time import monotonic
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from ..downloader.yt_dlp_wrapper import OperationCancelled, check_cancelled


class DownloadWorker(QObject):
    progress = Signal(int)
    finished = Signal(bool)
    completed = Signal(str)
    error = Signal(str)
    status = Signal(str)
    cancelled = Signal()
    details = Signal(dict)
    metadata = Signal(dict)

    def __init__(self, ydl_wrapper, url, format_id, outtmpl, postprocessors=None,
                 *, destination=None, container="MP4", quality=None):
        super().__init__()
        self.ydl_wrapper = ydl_wrapper
        self.url = url
        self.format_id = format_id
        self.outtmpl = outtmpl
        self.postprocessors = postprocessors
        self.cancel_event = Event()
        self._last_update = 0
        self.destination, self.container, self.quality = destination, container, quality

    def cancel(self):
        self.cancel_event.set()

    def _progress(self, data):
        check_cancelled(self.cancel_event)
        now = monotonic()
        if data.get("status") == "downloading":
            if now - self._last_update < 0.1:
                return
            self._last_update = now
            self.details.emit({key: data.get(key) for key in ("speed", "eta", "downloaded_bytes", "total_bytes")})
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes") or 0
            # Reserve 100% for completed postprocessing and a verified final path.
            self.progress.emit(min(99, int(downloaded * 100 / total)) if total else -1)
            self.status.emit(f"Baixando: {downloaded / 1048576:.1f} MiB"
                             + (f" / {total / 1048576:.1f} MiB" if total else ""))
        elif data.get("status") == "finished":
            self.progress.emit(-1)
            self.status.emit("Transferência concluída; processando mídia…")

    @Slot()
    def run(self):
        success = False
        try:
            check_cancelled(self.cancel_event)
            self.status.emit("Iniciando download…")
            if self.format_id is None:
                info = self.ydl_wrapper.extract_info(
                    self.url, cancel_event=self.cancel_event, status_hook=self.status.emit)
                self.ydl_wrapper._single_media(info)
                self.metadata.emit({"title": info.get("title"), "thumbnail": info.get("thumbnail")})
                self.format_id, self.postprocessors = self.ydl_wrapper.download_selection(
                    info, self.container, self.quality)
            if self.destination:
                self.outtmpl = self.ydl_wrapper.output_template(
                    self.destination, self.container, self.quality)
            result = self.ydl_wrapper.download(
                self.url, self.format_id, self.outtmpl, self.postprocessors,
                progress_hook=self._progress, cancel_event=self.cancel_event,
                status_hook=self.status.emit)
            check_cancelled(self.cancel_event)
            try:
                self.metadata.emit({"size": Path(result).stat().st_size})
            except OSError:
                pass
            self.progress.emit(100)
            self.completed.emit(result)
            success = True
        except Exception as exc:
            if isinstance(exc, OperationCancelled) or self.cancel_event.is_set():
                self.cancelled.emit()
            else:
                self.error.emit(str(exc))
        finally:
            self.finished.emit(success)
