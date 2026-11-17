import time
import threading
from PySide6.QtCore import QThread, Signal
from .yt_dlp_wrapper import YtDlpWrapper
from typing import List, Dict, Any

class DownloadWorker(QThread):
    progress_signal = Signal(int)
    finished_signal = Signal(str)
    error_signal = Signal(str)
    status_signal = Signal(str)

    def __init__(self, url: str, format_id: str, outtmpl: str, postprocessors: List[Dict[str, Any]]):
        super().__init__()
        self.url = url
        self.format_id = format_id
        self.outtmpl = outtmpl
        self.postprocessors = postprocessors
        self.ydl = YtDlpWrapper()
        self._is_running = True

    def run(self):
        try:
            self.status_signal.emit("Iniciando análise...")
            info = self.ydl.extract_info(self.url)
            
            self.status_signal.emit("Iniciando download...")
            
            # Retry logic
            max_retries = 3
            attempt = 0
            success = False
            
            while attempt < max_retries and not success:
                try:
                    self.ydl.download(self.url, self.format_id, self.outtmpl, self.postprocessors)
                    success = True
                except Exception as e:
                    attempt += 1
                    if attempt == max_retries:
                        raise e
                    time.sleep(2)
            
            self.finished_signal.emit(self.outtmpl)
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._is_running = False
        self.terminate()
