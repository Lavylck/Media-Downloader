"""Regression cases found during the V3 state audit."""

from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QObject, Slot, Qt, QCoreApplication, QEvent

from media_downloader.history import HistoryStore
from media_downloader.tests.test_ui import TestUI, wait_until
from media_downloader.tests.test_auto_analysis import run_events
from media_downloader.ui.main_window import MainWindow


class RetryAtCompletion(QObject):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue
        self.attempted = False

    @Slot(str)
    def changed(self, item_id):
        item = self.queue.get(item_id)
        if item.state == "completed" and not self.attempted:
            self.attempted = True
            self.queue.retry(item_id)


class TestV3Regressions(TestUI):
    def page(self, offset=0):
        return {"_type": "playlist", "webpage_url": self.win.url_edit.text(),
                "title": "Playlist", "offset": offset, "has_more": offset == 0,
                "entries": [{"index": offset + 1, "title": "Item",
                             "url": "https://example.com/item", "available": True}]}

    def load_playlist(self):
        self.wrapper.playlist_page = lambda url, offset=0, **kwargs: self.page(offset)
        self.win.source_mode.setCurrentIndex(1)
        self.win.analyze_url()
        wait_until(lambda: not self.win.analysis_in_progress)

    def test_playlist_page_error_allows_retry_without_losing_selection(self):
        self.load_playlist()
        self.win.playlist_panel.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        def fail(*args, **kwargs):
            raise RuntimeError("page unavailable")
        self.wrapper.playlist_page = fail
        self.win.playlist_panel.more()
        wait_until(lambda: not self.win.analysis_in_progress)
        self.assertFalse(self.win.playlist_panel.loading)
        self.assertTrue(self.win.playlist_panel.more_btn.isEnabled())
        self.assertEqual(len(self.win.playlist_panel.selected), 1)
        self.wrapper.playlist_page = lambda url, offset=0, **kwargs: self.page(offset)
        self.win.playlist_panel.more_btn.click()
        wait_until(lambda: not self.win.analysis_in_progress)
        self.assertEqual(self.win.playlist_panel.offset, 100)

    def test_playlist_stop_reenables_more(self):
        self.load_playlist()
        self.win.playlist_panel.more()
        self.win.playlist_panel.stop_loading()
        wait_until(lambda: not self.win.analysis_in_progress)
        self.assertTrue(self.win.playlist_panel.more_btn.isEnabled())
        self.assertEqual(self.win.playlist_panel.offset, 0)

    def test_retry_cannot_mutate_item_before_native_cleanup(self):
        self.analyze()
        observer = RetryAtCompletion(self.win.queue)
        self.win.queue.item_changed.connect(observer.changed)
        self.win.start_download()
        wait_until(lambda: not self.win.busy)
        self.assertTrue(observer.attempted)
        self.assertEqual(self.win.queue.items[0].state, "completed")
        self.assertEqual(self.wrapper.download_calls, 1)

    def test_closed_queue_rejects_new_work(self):
        self.win.queue.close()
        self.assertEqual(self.win.add_urls(["https://example.com/new"]), [])
        self.assertFalse(self.win.queue.busy)

    def test_delayed_settings_do_not_override_user_format(self):
        self.win.format_combo.setCurrentText("MP3")
        self.win._history_result("settings", {"container": "MP4"})
        self.assertEqual(self.win.format_combo.currentText(), "MP3")

    def test_close_callback_is_discarded_after_window_destruction(self):
        window = MainWindow(self.wrapper)
        errors = []
        with patch("sys.excepthook", lambda *args: errors.append(args)):
            window.close()
            wait_until(lambda: window.history.is_closed)
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            run_events(50)
        self.assertEqual(errors, [])

    def test_queue_failure_does_not_show_previous_success(self):
        from media_downloader.queue import QueueItem
        original = self.wrapper.download
        def download(url, *args, **kwargs):
            if url.endswith("/bad"):
                raise RuntimeError("unavailable")
            return original(url, *args, **kwargs)
        self.wrapper.download = download
        self.win.queue.add([QueueItem("https://example.com/good", "C:/test"),
                            QueueItem("https://example.com/bad", "C:/test")])
        wait_until(lambda: not self.win.busy)
        self.assertEqual(self.win.status_label.property("tone"), "error")
        self.assertNotIn("CONCLUÍDO", self.win.phase_label.text())
        self.assertNotIn("Concluído", self.win.download_btn.text())

    def test_queue_and_history_fit_small_window(self):
        self.win.resize(620, 520)
        self.analyze()
        self.win.start_download()
        wait_until(lambda: not self.win.busy)
        for panel in (self.win.queue_panel, self.win.history_panel):
            self.win.tabs.setCurrentWidget(panel)
            run_events(250)
            self.assertLessEqual(panel.minimumSizeHint().width(), self.win.width())
            for row in range(panel.list.count()):
                card = panel.list.itemWidget(panel.list.item(row))
                self.assertLessEqual(card.minimumSizeHint().width(), panel.list.viewport().width())
                self.assertGreaterEqual(panel.list.item(row).sizeHint().height(),
                                        card.layout().totalHeightForWidth(card.width()))


class TestHistoryPrivacy(unittest.TestCase):
    def test_url_title_and_error_do_not_persist_credentials(self):
        from media_downloader.queue import QueueItem
        with tempfile.TemporaryDirectory() as tmp:
            url = "https://example.com/video?sig=private-secret"
            item = QueueItem(url, tmp, title=url, thumbnail=url)
            item.error = "Failed https://user:private-password@example.com/x?token=secret"
            store = HistoryStore(Path(tmp) / "history.sqlite3")
            try:
                store.save(asdict(item))
                record = store.query()["records"][0]
                self.assertEqual(record["url"], "")
                self.assertEqual(record["thumbnail"], "")
                self.assertNotIn("private-secret", str(record))
                self.assertNotIn("private-password", str(record))
            finally:
                store.close()


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name in TestV3Regressions.__dict__:
        if name.startswith("test_"):
            suite.addTest(TestV3Regressions(name))
    suite.addTests(loader.loadTestsFromTestCase(TestHistoryPrivacy))
    return suite
