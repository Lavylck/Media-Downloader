import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading
import time
import unittest

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QObject, QThread, QTimer, Slot
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from media_downloader.downloader.yt_dlp_wrapper import YtDlpWrapper, check_cancelled
from media_downloader.ui.main_window import MainWindow


INFO = {
    "title": "Mídia <teste>", "duration": 125.4,
    "formats": [
        {"format_id": "360", "height": 360, "vcodec": "h264", "acodec": "aac", "abr": 96},
        {"format_id": "1080", "height": 1080, "vcodec": "h264", "acodec": "none"},
        {"format_id": "audio", "vcodec": "none", "acodec": "opus", "abr": 128},
    ],
}


def wait_until(predicate, timeout=4000):
    # A timed event loop exercises real queued signals and deferred deletion.
    if predicate():
        return
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(10)
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    poll.start()
    deadline.start(timeout)
    loop.exec()
    poll.stop()
    deadline.stop()
    if not predicate():
        raise AssertionError(f"Condition not reached in {timeout} ms")


class DelayedWrapper(YtDlpWrapper):
    def __init__(self):
        self.analysis_calls = 0
        self.download_calls = 0
        self.thread_ids = []
        self.analysis_error = None
        self.download_error = None
        self.last_selection = None

    def extract_info(self, url, *, cancel_event=None, status_hook=None):
        self.analysis_calls += 1
        self.thread_ids.append(threading.get_ident())
        for _ in range(25):
            time.sleep(0.01)
            check_cancelled(cancel_event)
        if self.analysis_error:
            raise RuntimeError(self.analysis_error)
        return INFO.copy()

    def download(self, url, format_id, outtmpl, postprocessors=None, progress_hook=None,
                 *, cancel_event=None, status_hook=None):
        self.download_calls += 1
        self.last_selection = (format_id, postprocessors)
        self.thread_ids.append(threading.get_ident())
        for i in range(1, 6):
            time.sleep(0.12)
            check_cancelled(cancel_event)
            progress_hook({"status": "downloading", "downloaded_bytes": i * 20, "total_bytes": 100})
        if self.download_error:
            raise RuntimeError(self.download_error)
        progress_hook({"status": "finished"})
        return "C:/test/result.mp3" if postprocessors else "C:/test/result.mp4"


class Observer(QObject):
    def __init__(self):
        super().__init__()
        self.slot_threads = []
        self.progress_values = []

    @Slot(int, dict)
    def record_info(self, request_id, info):
        self.slot_threads.append(QThread.currentThread())

    @Slot(int)
    def record_progress(self, value):
        self.slot_threads.append(QThread.currentThread())
        self.progress_values.append(value)

class TestUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.wrapper = DelayedWrapper()
        self.win = MainWindow(self.wrapper)
        self.observer = Observer()
        self.win.show()
        self.win.url_edit.setText("https://example.com/video")
        self.ticks = 0
        self.timer = QTimer()
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def tick(self):
        self.ticks += 1

    def tearDown(self):
        if self.win.busy:
            self.win.cancel_operation()
            wait_until(lambda: not self.win.busy)
        self.timer.stop()
        self.win.close()
        self.win.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def analyze(self):
        self.win.analyze_url()
        wait_until(lambda: not self.win.busy)

    def test_startup(self):
        self.assertTrue(self.win.isVisible())
        self.assertFalse(self.win.download_btn.isEnabled())
        self.assertTrue(self.win.analyze_btn.isEnabled())

    def test_invalid_url_does_not_start_thread(self):
        for url in ("", "garbage", "file:///C:/private", "https://", "https://bad host"):
            self.win.url_edit.setText(url)
            self.win.analyze_url()
            self.assertFalse(self.win.busy)
            self.assertIn("Erro:", self.win.status_label.text())
        self.assertEqual(self.wrapper.analysis_calls, 0)

    def test_analysis_delay_responsiveness_and_cleanup(self):
        before = self.ticks
        self.win.analyze_btn.click()
        worker, thread = self.win.analysis_worker, self.win.analysis_thread
        worker.info_received.connect(self.observer.record_info)
        self.assertFalse(self.win.analyze_btn.isEnabled())
        self.assertEqual(self.win.progress.maximum(), 0)
        self.win.analyze_url()
        self.win.start_download()
        wait_until(lambda: not self.win.busy)
        self.assertGreaterEqual(self.ticks - before, 5)
        self.assertEqual(self.wrapper.analysis_calls, 1)
        self.assertEqual(self.wrapper.download_calls, 0)
        self.assertEqual(self.win.title_label.text(), "Título: Mídia <teste>")
        self.assertEqual(self.win.duration_label.text(), "Duração: 00:02:05")
        self.assertEqual(self.win.quality_combo.count(), 3)
        self.assertIsNone(self.win.quality_combo.currentData())
        self.assertTrue(self.win.download_btn.isEnabled())
        self.assertNotEqual(self.wrapper.thread_ids[0], threading.get_ident())
        self.assertTrue(self.observer.slot_threads)
        self.assertTrue(all(t == self.app.thread() for t in self.observer.slot_threads))
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(isValid(worker))
        self.assertFalse(isValid(thread))
        self.analyze()
        self.assertEqual(self.wrapper.analysis_calls, 2)

    def test_analysis_error_and_retry(self):
        self.wrapper.analysis_error = "network timeout"
        self.analyze()
        self.assertIn("network timeout", self.win.status_label.text())
        self.assertFalse(self.win.download_btn.isEnabled())
        self.assertTrue(self.win.analyze_btn.isEnabled())
        self.wrapper.analysis_error = None
        self.analyze()
        self.assertTrue(self.win.download_btn.isEnabled())

    def test_changed_url_invalidates_formats(self):
        self.analyze()
        self.win.url_edit.setText("https://example.org/other")
        self.assertFalse(self.win.download_btn.isEnabled())
        self.win.start_download()
        self.assertEqual(self.wrapper.download_calls, 0)

    def test_download_progress_exclusivity_and_gui_thread(self):
        self.analyze()
        before = self.ticks
        self.win.start_download()
        worker, thread = self.win.download_worker, self.win.download_thread
        worker.progress.connect(self.observer.record_progress)
        self.win.start_download()
        self.win.analyze_url()
        self.assertFalse(self.win.download_btn.isEnabled())
        self.assertFalse(self.win.analyze_btn.isEnabled())
        wait_until(lambda: not self.win.busy)
        self.assertEqual(self.wrapper.download_calls, 1)
        self.assertEqual(self.wrapper.analysis_calls, 1)
        self.assertGreaterEqual(self.ticks - before, 10)
        self.assertTrue(any(0 < n < 100 for n in self.observer.progress_values))
        self.assertEqual(self.win.progress.value(), 100)
        self.assertEqual(self.win.last_output, "C:/test/result.mp4")
        self.assertEqual(self.wrapper.last_selection[0], "1080+audio")
        self.assertTrue(all(t == self.app.thread() for t in self.observer.slot_threads))
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(isValid(worker))
        self.assertFalse(isValid(thread))

    def test_lower_quality_and_audio_selection(self):
        self.analyze()
        self.win.quality_combo.setCurrentIndex(2)
        self.win.start_download()
        wait_until(lambda: not self.win.busy)
        self.assertEqual(self.wrapper.last_selection[0], "360")
        self.win.format_combo.setCurrentText("MP3")
        self.win.start_download()
        wait_until(lambda: not self.win.busy)
        self.assertEqual(self.wrapper.last_selection[0], "audio")
        self.assertEqual(self.wrapper.last_selection[1][0]["preferredcodec"], "mp3")

    def test_download_failure_never_completes(self):
        self.analyze()
        self.wrapper.download_error = "connection lost"
        self.win.start_download()
        wait_until(lambda: not self.win.busy)
        self.assertIn("connection lost", self.win.status_label.text())
        self.assertIsNone(self.win.last_output)
        self.assertNotEqual(self.win.progress.value(), 100)
        self.assertTrue(self.win.download_btn.isEnabled())

    def test_cancel_analysis(self):
        self.win.analyze_url()
        self.win.cancel_btn.click()
        wait_until(lambda: not self.win.busy)
        self.assertIsNone(self.win.media_info)
        self.assertIn("cancelada", self.win.status_label.text())

    def test_close_during_analysis_is_nonblocking(self):
        self.win.analyze_url()
        start = time.monotonic()
        self.win.close()
        self.assertLess(time.monotonic() - start, 0.15)
        self.assertTrue(self.win.isVisible())
        wait_until(lambda: not self.win.isVisible())
        self.assertFalse(self.win.busy)

    def test_close_during_download_is_nonblocking(self):
        self.analyze()
        self.win.start_download()
        wait_until(lambda: self.wrapper.download_calls == 1)
        start = time.monotonic()
        self.win.close()
        self.assertLess(time.monotonic() - start, 0.15)
        wait_until(lambda: not self.win.isVisible())
        self.assertIsNone(self.win.last_output)
        self.assertFalse(self.win.busy)

    def test_close_waits_responsively_for_uncancellable_network_step(self):
        entered = threading.Event()

        def slow_network(url, **kwargs):
            entered.set()
            time.sleep(0.4)  # Simulate a socket call with no cancellation hook.
            return INFO.copy()

        self.wrapper.extract_info = slow_network
        self.win.analyze_url()
        wait_until(entered.is_set)
        before = self.ticks
        self.win.close()
        self.assertTrue(self.win.isVisible())
        wait_until(lambda: not self.win.isVisible())
        self.assertGreater(self.ticks - before, 10)
        self.assertIsNone(self.win.media_info)
        self.assertFalse(self.win.busy)


if __name__ == "__main__":
    unittest.main()
