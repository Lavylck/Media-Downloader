import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread, Qt
from media_downloader.ui.download_worker import DownloadWorker
from media_downloader.downloader.yt_dlp_wrapper import YtDlpWrapper

# A mock YtDlpWrapper to test the worker without actual downloading
class MockYtDlpWrapper(YtDlpWrapper):
    def download(self, url, format_id, outtmpl, postprocessors=None, progress_hook=None):
        if progress_hook:
            # Simulate progress
            for i in range(0, 101, 20):
                # Use i as download_bytes, 100 as total_bytes
                progress_hook(1, "Mock Title", i, 100)
        return "mock_output"

def test_download_worker():
    app = QApplication(sys.argv)
    
    wrapper = MockYtDlpWrapper()
    worker = DownloadWorker(wrapper, "http://test.com", "1080p", "C:/test.mp4")
    thread = QThread()
    
    worker.moveToThread(thread)
    
    worker.finished.connect(lambda success: print(f"Finished: {success}"))
    worker.error.connect(lambda err: print(f"Error: {err}"))
    worker.progress.connect(lambda p: print(f"Progress: {p}%"))
    
    thread.started.connect(worker.run)
    thread.start()
    
    # Wait for completion (simple way for test)
    import time
    time.sleep(2)
    thread.quit()
    thread.wait()
    print("Test finished.")

if __name__ == "__main__":
    test_download_worker()
