import sys
from PySide6.QtCore import QObject, Signal, Slot
from ..downloader.yt_dlp_wrapper import YtDlpWrapper

class AnalysisWorker(QObject):
    info_received = Signal(dict)
    finished = Signal(bool)
    error = Signal(str)
    status = Signal(str)

    def __init__(self, ydl_wrapper: YtDlpWrapper, url: str):
        super().__init__()
        self.ydl_wrapper = ydl_wrapper
        self.url = url

    @Slot()
    def run(self):
        try:
            self.status.emit("Analisando URL...")
            info = self.ydl_wrapper.extract_info(self.url)
            self.info_received.emit(info)
            self.finished.emit(True)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)
