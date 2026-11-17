import unittest
from unittest.mock import Mock
from threading import Event

from media_downloader.ui.analysis_worker import AnalysisWorker
from media_downloader.ui.download_worker import DownloadWorker
from media_downloader.downloader.yt_dlp_wrapper import OperationCancelled, YtDlpWrapper


class TestWorkers(unittest.TestCase):
    def test_analysis_exception_emits_error_then_finished_once(self):
        wrapper = Mock()
        wrapper.extract_info.side_effect = RuntimeError("network error")
        worker = AnalysisWorker(wrapper, "https://example.com")
        events = []
        worker.error.connect(lambda error: events.append(("error", error)))
        worker.finished.connect(lambda ok: events.append(("finished", ok)))
        worker.run()
        self.assertEqual(events, [("error", "network error"), ("finished", False)])

    def test_download_exception_emits_no_success(self):
        wrapper = Mock()
        wrapper.download.side_effect = RuntimeError("conversion failed")
        worker = DownloadWorker(wrapper, "https://example.com", "best", "unused")
        errors, completed, finished = [], [], []
        worker.error.connect(errors.append)
        worker.completed.connect(completed.append)
        worker.finished.connect(finished.append)
        worker.run()
        self.assertEqual(errors, ["conversion failed"])
        self.assertEqual(completed, [])
        self.assertEqual(finished, [False])

    def test_progress_dictionary_unknown_size_and_finished(self):
        worker = DownloadWorker(Mock(), "https://example.com", "best", "unused")
        values = []
        worker.progress.connect(values.append)
        worker._progress({"status": "downloading", "downloaded_bytes": 100})
        worker._last_update = 0
        worker._progress({"status": "downloading", "downloaded_bytes": 50, "total_bytes_estimate": 100})
        worker._progress({"status": "finished"})
        self.assertEqual(values, [-1, 50, -1])

    def test_cancellation_before_network(self):
        event = Event()
        event.set()
        with self.assertRaises(OperationCancelled):
            YtDlpWrapper().extract_info("https://example.com", cancel_event=event)
