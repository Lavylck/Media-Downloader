import sys
from PySide6.QtCore import QObject, Signal, Slot
from ..downloader.yt_dlp_wrapper import YtDlpWrapper

class DownloadWorker(QObject):
    progress = Signal(int)
    finished = Signal(bool)
    error = Signal(str)
    status = Signal(str)

    def __init__(self, ydl_wrapper: YtDlpWrapper, url: str, format_id: str, outtmpl: str, postprocessors: list = None):
        super().__init__()
        self.ydl_wrapper = ydl_wrapper
        self.url = url
        self.format_id = format_id
        self.outtmpl = outtmpl
        self.postprocessors = postprocessors

    @Slot()
    def run(self):
        try:
            self.status.emit("Starting download...")
            
            def progress_hook(id, title, download_bytes, total_bytes):
                if total_bytes > 0:
                    progress = int((download_bytes / total_bytes) * 100)
                    self.progress.emit(progress)
                self.status.emit(f"Downloading: {title} ({download_bytes}/{total_bytes})")

            result = self.ydl_wrapper.download(
                self.url, 
                self.format_id, 
                self.outtmpl, 
                self.postprocessors,
                progress_hook=progress_hook
            )
            
            self.status.emit(f"Finished: {result}")
            self.progress.emit(100)
            self.finished.emit(True)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)
