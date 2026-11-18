import time
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QCoreApplication, QEvent

from media_downloader.queue import DownloadQueue, QueueItem
from media_downloader.downloader.yt_dlp_wrapper import YtDlpWrapper, check_cancelled
from media_downloader.tests.test_ui import INFO, wait_until
from media_downloader.ui.playlist_panel import PlaylistPanel


class QueueSource(YtDlpWrapper):
    def __init__(self):
        self.active = 0
        self.maximum = 0
        self.calls = []

    def extract_info(self, url, **kwargs):
        return {**INFO, "title": url}

    def download(self, url, format_id, outtmpl, postprocessors=None, progress_hook=None, **kwargs):
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        self.calls.append(url)
        try:
            for n in range(3):
                time.sleep(0.06)
                check_cancelled(kwargs.get("cancel_event"))
                progress_hook({"status": "downloading", "downloaded_bytes": n*30,
                               "total_bytes": 100, "speed": 1000, "eta": 1})
            if "fail" in url:
                raise RuntimeError("Fonte indisponível")
            return "C:/result.mp4"
        finally:
            self.active -= 1


class TestQueuePlaylist(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.source = QueueSource()
        self.queue = DownloadQueue(self.source)

    def tearDown(self):
        self.queue.close()
        wait_until(lambda: not self.queue.busy)
        self.queue.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def item(self, name):
        return QueueItem(f"https://example.com/{name}", "C:/Downloads")

    def test_sequential_independent_progress_and_duplicate_protection(self):
        first, second = self.item("first"), self.item("second")
        self.assertEqual(len(self.queue.add([first, self.item("first"), second])), 2)
        wait_until(lambda: first.progress > 0)
        self.assertEqual(second.progress, 0)
        wait_until(lambda: not self.queue.busy)
        self.assertEqual(self.source.maximum, 1)
        self.assertEqual([i.state for i in self.queue.items], ["completed", "completed"])
        self.assertEqual(first.speed, 1000)
        self.assertEqual(first.eta, 1)

    def test_failed_item_does_not_stop_queue(self):
        bad, good = self.item("fail"), self.item("good")
        self.queue.add([bad, good])
        wait_until(lambda: not self.queue.busy)
        self.assertEqual(bad.state, "failed")
        self.assertEqual(good.state, "completed")

    def test_only_waiting_item_can_pause_without_resume_capability(self):
        first, second = self.item("first"), self.item("second")
        self.queue.add([first, second])
        self.queue.pause(second.id)
        wait_until(lambda: first.state == "downloading")
        self.queue.pause(first.id)
        self.assertEqual(first.state, "downloading")
        wait_until(lambda: not self.queue.busy)
        self.assertEqual(second.state, "paused")
        self.assertEqual(self.source.calls, [first.url])
        self.queue.resume(second.id)
        wait_until(lambda: not self.queue.busy)
        self.assertEqual(second.state, "completed")

    def test_cancel_pending_and_active_removes_both(self):
        first, second = self.item("first"), self.item("second")
        self.queue.add([first, second])
        self.queue.cancel(second.id)
        self.queue.cancel(first.id)
        wait_until(lambda: not self.queue.busy)
        self.assertEqual(self.queue.items, [])
        self.assertEqual([first.state, second.state], ["cancelled", "cancelled"])
        self.queue.retry(second.id)
        wait_until(lambda: not self.queue.busy)
        self.assertEqual(second.state, "cancelled")

    def test_playlist_group_cancel_and_remove(self):
        items = [self.item(str(n)) for n in range(3)]
        for item in items:
            item.group = "playlist"
        self.queue.add(items)
        self.queue.cancel_group("playlist")
        wait_until(lambda: not self.queue.busy)
        self.assertTrue(all(i.state == "cancelled" for i in items))
        self.queue.remove(items[1].id)
        self.assertEqual(len(self.queue.items), 0)

    def test_playlist_selection_and_unavailable_entries(self):
        panel = PlaylistPanel()
        page = {"webpage_url": "https://example.com/list", "title": "List", "offset": 0,
                "playlist_count": 3, "has_more": False, "entries": [
                    {"index": n, "url": f"https://example.com/{n}", "title": str(n),
                     "available": n != 2} for n in range(1, 4)]}
        panel.set_page(page)
        self.assertEqual(len(panel.selected), 0)
        panel.select_all()
        self.assertEqual(len(panel.selected), 2)
        panel.table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
        self.assertEqual(len(panel.selected), 1)
        panel.close()
        panel.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    @patch("media_downloader.downloader.yt_dlp_wrapper.yt_dlp.YoutubeDL")
    def test_playlist_is_bounded_and_single_mode_is_default(self, factory):
        consumed = []
        def entries():
            for n in range(10000):
                consumed.append(n)
                yield {"url": f"https://example.com/{n}", "title": str(n)}
        factory.return_value.__enter__.return_value.extract_info.return_value = {
            "_type": "playlist", "title": "Large", "entries": entries()}
        info = YtDlpWrapper().extract_info("https://example.com/list")
        self.assertEqual(len(info["entries"]), 100)
        self.assertEqual(len(consumed), 101)
        self.assertTrue(info["has_more"])
        self.assertTrue(factory.call_args.args[0]["noplaylist"])

    def test_playlist_ceiling_uses_extractor_class_without_upscaling(self):
        info = {"formats": [
            {"format_id": "cinema", "height": 814, "width": 1920, "format_note": "1080p"},
            {"format_id": "lower", "height": 542, "width": 1280, "format_note": "720p"}]}
        self.assertEqual(YtDlpWrapper().download_selection(info, "MP4", {"ceiling": 720})[0], "lower")
