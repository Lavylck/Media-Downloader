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
                time.sleep(0.1)
        return "mock_output"

    def extract_info(self, url, download=False):
        time.sleep(0.5) # Simulate network delay
        return {
            "title": "Mock Video",
            "duration": 120,
            "formats": [{"format_id": "1080p", "height": 1080, "filesize": 1000}]
        }

def test_analysis_worker():
    app = QApplication(sys.argv)
    
    win = MainWindow()
    win.ydl = MockYdl()
    
    win.url_edit.setText("http://test.com")
    win.dest_edit.setText("C:/test")
    win.format_combo.setCurrentText("MP4")
    win.best_format = {'format_id': '1080p'}
    
    print("Starting test...")
    win.analyze_url()
    
    print(f"Analysis in progress: {win.analysis_in_progress}")
    assert win.analysis_in_progress is True
    assert win.analyze_btn.isEnabled() is False
    
    # Process events until info is received
    for i in range(100):
        QCoreApplication.processEvents()
        if win.title_label.text() == "Título: Mock Video":
            break
        if i % 10 == 0:
            print(f"Iteration {i}...")
        
    print(f"Title label: {win.title_label.text()}")
    assert win.title_label.text() == "Título: Mock Video"
    assert win.analysis_in_progress is False
    assert win.analyze_btn.isEnabled() is True
    
    print("Analysis test passed.")

if __name__ == "__main__":
    import time
    try:
        test_analysis_worker()
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
