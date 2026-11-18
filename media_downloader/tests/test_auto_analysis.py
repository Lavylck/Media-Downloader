"""User-input regression tests; real Qt event loop and background workers."""

import threading
import time
import unittest

from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from media_downloader.tests.test_ui import INFO, TestUI, wait_until


def run_events(milliseconds):
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


class TestAutoAnalysis(TestUI):
    # Reuse setup/cleanup helpers, not the inherited V1 test methods.
    def setUp(self):
        super().setUp()
        self.win.url_edit.clear()
        self.win.analysis_timer.setInterval(80)

    def paste(self, url):
        clipboard = QApplication.clipboard()
        previous = clipboard.text()
        try:
            clipboard.setText(url)
            self.win.url_edit.setFocus()
            self.win.url_edit.selectAll()
            QTest.keyClick(self.win.url_edit, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        finally:
            clipboard.setText(previous)

    def settled(self):
        return not (self.win.busy or self.win.analysis_timer.isActive() or self.win._auto_pending)

    def test_paste_triggers_analysis_without_click(self):
        self.win.analysis_timer.setInterval(600)
        started = time.monotonic()
        before = self.ticks
        self.paste("https://example.com/pasted")
        self.assertFalse(self.win.busy)
        run_events(200)
        self.assertEqual(self.wrapper.analysis_calls, 0)
        wait_until(self.settled)
        self.assertGreaterEqual(time.monotonic() - started, 0.55)
        self.assertEqual(self.wrapper.analysis_calls, 1)
        self.assertIsNotNone(self.win.media_info)
        self.assertIsNone(self.win.quality_combo.currentData())
        self.assertTrue(self.win.download_btn.isEnabled())
        self.assertGreater(self.ticks - before, 20)

    def test_typing_debounces_valid_prefixes(self):
        for suffix in ("a", "ab", "abc"):
            self.win.url_edit.setText("https://example.com/" + suffix)
            run_events(30)
        wait_until(self.settled)
        self.assertEqual(self.wrapper.analysis_calls, 1)
        self.assertEqual(self.win.analyzed_url, "https://example.com/abc")

    def test_same_url_and_whitespace_do_not_repeat_but_manual_does(self):
        self.paste("https://example.com/same")
        wait_until(self.settled)
        self.paste("https://example.com/same")
        self.win.url_edit.setText("  https://example.com/same  ")
        run_events(250)
        self.assertEqual(self.wrapper.analysis_calls, 1)
        self.assertTrue(self.win.download_btn.isEnabled())
        self.win.analyze_btn.click()
        wait_until(self.settled)
        self.assertEqual(self.wrapper.analysis_calls, 2)

    def test_new_url_waits_for_old_thread_and_discards_old_signals(self):
        urls = []
        active = 0
        maximum = 0
        entered = threading.Event()

        def network(url, **kwargs):
            nonlocal active, maximum
            urls.append(url)
            active += 1
            maximum = max(maximum, active)
            entered.set()
            time.sleep(0.35)  # Ignore cancellation until the socket call returns.
            active -= 1
            return {**INFO, "title": url}

        self.wrapper.extract_info = network
        self.paste("https://example.com/old")
        wait_until(entered.is_set)
        old_id = self.win._active_request_id
        self.assertTrue(self.win.url_edit.isEnabled())
        self.paste("https://example.com/intermediate")
        run_events(20)
        self.paste("https://example.com/latest")
        self.win._on_analysis_info(old_id, {**INFO, "title": "STALE"})
        self.win._on_analysis_error(old_id, "stale error")
        self.assertIsNone(self.win.media_info)
        self.assertNotIn("stale", self.win.status_label.text())
        wait_until(self.settled)
        self.assertEqual(urls, ["https://example.com/old", "https://example.com/latest"])
        self.assertEqual(maximum, 1)
        self.assertIn("latest", self.win.title_label.text())
        self.win._on_analysis_info(old_id, {**INFO, "title": "STALE"})
        self.win._on_analysis_status(old_id, "STALE")
        self.assertIn("latest", self.win.title_label.text())
        self.assertNotIn("STALE", self.win.status_label.text())

    def test_invalid_replacement_cancels_and_does_not_start(self):
        self.paste("https://example.com/old")
        wait_until(lambda: self.wrapper.analysis_calls == 1)
        self.win.url_edit.setText("https://")
        wait_until(self.settled)
        run_events(200)
        self.assertEqual(self.wrapper.analysis_calls, 1)
        self.assertIsNone(self.win.media_info)
        self.assertFalse(self.win.download_btn.isEnabled())

    def test_error_does_not_auto_retry_forever(self):
        self.wrapper.analysis_error = "offline"
        self.paste("https://example.com/offline")
        wait_until(self.settled)
        run_events(250)
        self.assertEqual(self.wrapper.analysis_calls, 1)
        self.assertIn("offline", self.win.status_label.text())
        self.wrapper.analysis_error = None
        self.win.analyze_btn.click()
        wait_until(self.settled)
        self.assertTrue(self.win.download_btn.isEnabled())

    def test_cancel_debounce_and_manual_restart(self):
        self.paste("https://example.com/cancel")
        self.win.cancel_btn.click()
        run_events(200)
        self.assertEqual(self.wrapper.analysis_calls, 0)
        self.assertFalse(self.win.url_edit.text())
        self.paste("https://example.com/cancel")
        self.win.analyze_btn.click()
        wait_until(self.settled)
        self.assertEqual(self.wrapper.analysis_calls, 1)
        self.assertNotIn("cancelada", self.win.status_label.text())
        self.assertTrue(self.win.download_btn.isEnabled())

    def test_cancel_queued_replacement(self):
        self.paste("https://example.com/first")
        wait_until(lambda: self.wrapper.analysis_calls == 1)
        self.paste("https://example.com/next")
        self.win.cancel_operation()
        wait_until(self.settled)
        run_events(200)
        self.assertEqual(self.wrapper.analysis_calls, 1)
        self.assertIsNone(self.win.media_info)

    def test_close_during_debounce_never_starts_hidden_work(self):
        self.paste("https://example.com/close")
        self.win.close()
        run_events(200)
        self.assertFalse(self.win.isVisible())
        self.assertFalse(self.win.busy)
        self.assertEqual(self.wrapper.analysis_calls, 0)

    def test_missing_destination_disables_cta(self):
        self.paste("https://example.com/video")
        wait_until(self.settled)
        self.win.dest_edit.clear()
        self.assertFalse(self.win.download_btn.isEnabled())
        self.win.dest_edit.setText("C:/Downloads")
        self.assertTrue(self.win.download_btn.isEnabled())

    def test_cta_size_center_and_loading_feedback(self):
        run_events(50)
        button = self.win.download_btn
        self.assertGreaterEqual(button.height(), 64)
        self.assertGreaterEqual(button.width(), 300)
        content = self.win.form_widget
        center = button.mapTo(content, button.rect().center()).x()
        self.assertLess(abs(center - content.width() / 2), 4)
        self.assertFalse(button.isEnabled())
        self.paste("https://example.com/loading")
        wait_until(lambda: self.wrapper.analysis_calls == 1)
        self.assertIn("Analisando", button.text())
        self.assertTrue(button.property("busy"))
        wait_until(self.settled)
        self.assertFalse(button.property("busy"))
        self.assertTrue(button.isEnabled())
        self.assertEqual(button.text(), "Baixar")
        self.assertEqual(self.win.add_link_btn.text(), "+")
        self.assertTrue(self.win.add_link_btn.isEnabled())
        self.win.start_download()
        self.assertEqual(button.text(), "Analisando")
        wait_until(lambda: button.text() == "Baixando...")
        self.assertTrue(self.win.url_edit.isEnabled())
        wait_until(self.settled)
        self.assertEqual(self.win.status_label.property("tone"), "success")
        self.assertEqual(self.win.progress_caption.text(), "100%")

    def test_theme_error_state_and_long_text_small_window(self):
        self.wrapper.extract_info = lambda *a, **k: {**INFO, "title": "Título longo " * 40}
        self.win.resize(620, 520)
        self.paste("https://example.com/long-title")
        wait_until(self.settled)
        scroll = self.win.scroll_area
        self.assertLessEqual(scroll.widget().width(), scroll.viewport().width())
        self.assertTrue(self.win.title_label.wordWrap())
        self.win._on_error("Falha de rede: tente novamente")
        self.assertEqual(self.win.status_label.property("tone"), "error")
        self.assertIn("Falha de rede", self.win.status_label.text())
        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)

    def test_new_link_can_be_analyzed_and_queued_during_download(self):
        self.paste("https://example.com/first")
        wait_until(self.settled)
        self.win.start_download()
        self.paste("https://example.com/second")
        wait_until(lambda: self.win.media_info is not None and not self.win.analysis_in_progress)
        self.assertTrue(self.win.queue.busy)
        self.assertTrue(self.win.download_btn.isEnabled())
        self.win.start_download()
        self.assertEqual(len(self.win.queue.items), 2)
        wait_until(self.settled)
        self.assertTrue(all(item.state == "completed" for item in self.win.queue.items))


def load_tests(loader, tests, pattern):
    # Only tests introduced here; the V1 cases run once in test_ui.
    names = [name for name in TestAutoAnalysis.__dict__ if name.startswith("test_")]
    return unittest.TestSuite(TestAutoAnalysis(name) for name in names)
