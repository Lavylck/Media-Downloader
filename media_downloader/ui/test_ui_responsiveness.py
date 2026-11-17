import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread, QCoreApplication
from media_downloader.ui.main_window import MainWindow
from media_downloader.downloader.yt_dlp_wrapper import YtDlpWrapper

class MockYdl(YtDlpWrapper):
    def download(self, url, format_id, outtmpl, postprocessors=None, progress_hook=None):
        if progress_hook:
            for i in range(0, 101, 20):
                progress_hook(1, "Mock", i, 100)
        return "mock_output"

def test_ui_responsiveness():
    app = QApplication(sys.argv)
    
    win = MainWindow()
    win.ydl = MockYdl()
    
    win.url_edit.setText("http://test.com")
    win.dest_edit.setText("C:/test")
    win.format_combo.setCurrentText("MP4")
    win.best_format = {'format_id': '1080p'}
    
    win.start_download()
    
    print("Download started...")
    
    # Use a loop to process events
    for i in range(100):
        QCoreApplication.processEvents()
        if win.progress.value() > 0:
            print(f"Progress: {win.progress.value()}%")
            break
        if i % 10 == 0:
            print(f"Waiting... {i}")
        
    assert win.progress.value() > 0
    
    # Wait for completion
    for i in range(100):
        QCoreApplication.processEvents()
        if not win.download_in_progress:
            break
    
    print("Download finished.")
    assert win.download_in_progress is False
    print("SUCCESS: Test Passed")
    sys.exit(0)


if __name__ == "__main__":
    try:
        test_ui_responsiveness()
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
