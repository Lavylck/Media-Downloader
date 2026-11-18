"""Real localhost transfers and FFmpeg processing; no Internet or mocks."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import Thread
import unittest

from media_downloader.downloader.yt_dlp_wrapper import YtDlpWrapper
from media_downloader.tests.test_ui import wait_until
from media_downloader.ui.main_window import MainWindow
from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        try:
            super().do_GET()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            # The generic extractor intentionally closes its metadata probe
            # before consuming the whole response; this is expected on Windows.
            pass


def probe(path):
    result = subprocess.run(
        [shutil.which("ffprobe"), "-v", "error", "-show_format", "-show_streams",
         "-of", "json", str(path)], check=True, capture_output=True, text=True, timeout=20)
    return json.loads(result.stdout)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/FFprobe required")
class TestRealMedia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        temp_root = Path.home() / "AppData/Local/Temp/opencode"
        cls.temp = tempfile.TemporaryDirectory(
            prefix="media-downloader-test-", dir=temp_root if temp_root.exists() else None)
        cls.root = Path(cls.temp.name)
        cls.source = cls.root / "source"
        cls.source.mkdir()
        ffmpeg = shutil.which("ffmpeg")
        inputs = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                  "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24",
                  "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "1.5"]
        subprocess.run([*inputs, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                        str(cls.source / "sample.mp4")], check=True, capture_output=True, timeout=30)
        # HuffYUV cannot be remuxed to MP4; exercise the real transcode fallback.
        subprocess.run([*inputs, "-c:v", "huffyuv", "-c:a", "pcm_s16le",
                        str(cls.source / "convert.mkv")], check=True, capture_output=True, timeout=30)
        # A real MPEG-DASH manifest offers separate video/audio tracks.
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(cls.source / "sample.mp4"), "-map", "0", "-c", "copy",
                        "-f", "dash", "manifest.mpd"],
                       cwd=cls.source, check=True, capture_output=True, timeout=30)
        (cls.source / "index.html").write_text(
            '<html><head><title>Teste: nome &quot;inválido&quot; / Windows?</title></head>'
            '<body><video controls src="sample.mp4"></video></body></html>', encoding="utf-8")
        (cls.source / "playlist.html").write_text(
            '<html><head><title>Playlist local de validação</title></head><body>'
            '<video src="sample.mp4?item=1"></video>'
            '<video src="missing.mp4"></video>'
            '<video src="sample.mp4?item=3"></video></body></html>', encoding="utf-8")
        (cls.source / "large-playlist.html").write_text(
            "<html><head><title>103 items</title></head><body>" +
            "".join(f'<video src="sample.mp4?item={i}"></video>' for i in range(103)) +
            "</body></html>", encoding="utf-8")
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(QuietHandler, directory=str(cls.source)))
        cls.server.daemon_threads = True
        cls.server_thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}/"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=5)
        cls.temp.cleanup()

    def setUp(self):
        self.previous_data = os.environ.get("MEDIA_DOWNLOADER_DATA_DIR")
        os.environ["MEDIA_DOWNLOADER_DATA_DIR"] = str(self.root / self._testMethodName / "data")
        self.wrapper = YtDlpWrapper()
        self.dest = self.root / self._testMethodName
        self.dest.mkdir()

    def tearDown(self):
        if self.previous_data is None:
            os.environ.pop("MEDIA_DOWNLOADER_DATA_DIR", None)
        else:
            os.environ["MEDIA_DOWNLOADER_DATA_DIR"] = self.previous_data

    def download(self, filename, container="MP4"):
        url = self.base_url + filename
        info = self.wrapper.extract_info(url)
        selection, pp = self.wrapper.download_selection(info, container)
        events = []
        path = self.wrapper.download(
            url, selection, self.wrapper.output_template(self.dest, container), pp,
            progress_hook=lambda data: events.append(data.copy()))
        return Path(path), events

    def test_http_mp4_audio_and_duplicate_preservation(self):
        path, events = self.download("sample.mp4")
        media = probe(path)
        self.assertEqual({s["codec_type"] for s in media["streams"]}, {"video", "audio"})
        self.assertGreater(float(media["format"]["duration"]), 1)
        self.assertEqual(path.parent, self.dest)
        self.assertEqual(path.suffix, ".mp4")
        self.assertTrue(any(e["status"] == "downloading" for e in events))
        before = path.stat().st_mtime_ns
        second, events = self.download("sample.mp4")
        self.assertEqual(second, path)
        self.assertEqual(path.stat().st_mtime_ns, before)
        self.assertEqual(events, [])

    def test_http_extract_mp3(self):
        path, _ = self.download("sample.mp4", "MP3")
        media = probe(path)
        self.assertEqual(path.suffix, ".mp3")
        self.assertEqual([s["codec_name"] for s in media["streams"]], ["mp3"])
        self.assertGreater(float(media["format"]["duration"]), 1)

    def test_destination_that_is_a_file_fails(self):
        self.dest = self.dest / "not-a-directory"
        self.dest.write_text("preserve this file", encoding="utf-8")
        with self.assertRaises(OSError):
            self.download("sample.mp4")
        self.assertEqual(self.dest.read_text(encoding="utf-8"), "preserve this file")

    def test_convert_incompatible_codecs_to_mp4(self):
        path, _ = self.download("convert.mkv")
        media = probe(path)
        self.assertEqual(path.suffix, ".mp4")
        self.assertEqual({s["codec_type"] for s in media["streams"]}, {"video", "audio"})
        self.assertNotIn("huffyuv", [s["codec_name"] for s in media["streams"]])

    def test_dash_merges_real_separate_streams(self):
        url = self.base_url + "manifest.mpd"
        info = self.wrapper.extract_info(url)
        selection, pp = self.wrapper.download_selection(info, "MP4")
        self.assertIn("+", selection)
        path = self.wrapper.download(url, selection, self.wrapper.output_template(self.dest, "MP4"), pp)
        self.assertEqual({s["codec_type"] for s in probe(path)["streams"]}, {"video", "audio"})

    def test_windows_filename_and_percent_in_destination(self):
        self.dest = self.dest / "100% teste"
        path, _ = self.download("index.html")
        self.assertEqual(path.parent, self.dest)
        self.assertFalse(any(c in path.name for c in '<>:"/\\|?*'))
        self.assertTrue(path.is_file())

    def test_http_404_raises(self):
        with self.assertRaises(Exception):
            self.wrapper.extract_info(self.base_url + "missing.mp4")

    def test_complete_gui_http_flow_mp4_and_mp3(self):
        win = MainWindow()
        win.show()
        ticks = []
        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.append(1))
        timer.start()
        try:
            clipboard = QApplication.clipboard()
            previous = clipboard.text()
            try:
                clipboard.setText(self.base_url + "sample.mp4")
                QTest.keyClick(win.url_edit, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
            finally:
                clipboard.setText(previous)
            win.dest_edit.setText(str(self.dest))
            wait_until(lambda: not (win.busy or win.analysis_timer.isActive() or win._auto_pending), 20000)
            self.assertIsNotNone(win.media_info, win.status_label.text())
            for container in ("MP4", "MP3"):
                before = len(ticks)
                win.format_combo.setCurrentText(container)
                win.download_btn.click()
                wait_until(lambda: not win.busy, 30000)
                self.assertIsNotNone(win.last_output, win.status_label.text())
                self.assertGreater(len(ticks), before)
                self.assertEqual(Path(win.last_output).parent, self.dest)
                self.assertEqual(win.progress.value(), 100)
                self.assertEqual(Path(win.last_output).suffix, "." + container.lower())
                self.assertGreater(float(probe(win.last_output)["format"]["duration"]), 1)
        finally:
            if win.busy:
                win.cancel_operation()
                wait_until(lambda: not win.busy, 30000)
            timer.stop()
            win.close()
            wait_until(lambda: win.history.is_closed)
            win.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_real_playlist_selection_queue_failure_and_history(self):
        from media_downloader.history import HistoryStore
        from media_downloader.paths import data_dir
        win = MainWindow()
        win.show()
        try:
            win.dest_edit.setText(str(self.dest))
            win.source_mode.setCurrentIndex(1)
            win.url_edit.setText(self.base_url + "playlist.html")
            win.analyze_url()
            wait_until(lambda: not win.analysis_in_progress, 20000)
            self.assertEqual(win.media_info.get("_type"), "playlist", win.status_label.text())
            self.assertEqual(len(win.playlist_panel.loaded), 3)
            self.assertFalse(win.download_btn.isEnabled())
            win.playlist_panel.select_all()
            win.start_download()
            wait_until(lambda: not win.queue.busy, 40000)
            states = [item.state for item in win.queue.items]
            self.assertEqual(states, ["completed", "failed", "completed"])
            for item in win.queue.items:
                if item.state == "completed":
                    self.assertEqual({s["codec_type"] for s in probe(item.path)["streams"]}, {"audio", "video"})
            ids = {item.id for item in win.queue.items}
        finally:
            win.close()
            wait_until(lambda: win.history.is_closed, 20000)
            win.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        store = HistoryStore(data_dir() / "history.sqlite3")
        records = store.query()["records"]
        self.assertEqual(len([r for r in records if r["id"] in ids]), 3)
        store.close()

    def test_real_playlist_pagination_has_no_repeated_or_missing_items(self):
        url = self.base_url + "large-playlist.html"
        first = self.wrapper.playlist_page(url)
        second = self.wrapper.playlist_page(url, offset=100)
        self.assertEqual(len(first["entries"]), 100)
        self.assertTrue(first["has_more"])
        self.assertEqual(len(second["entries"]), 3)
        self.assertFalse(second["has_more"])
        entries = first["entries"] + second["entries"]
        self.assertEqual(len({entry["url"] for entry in entries}), 103)
        self.assertEqual([entry["index"] for entry in entries], list(range(1, 104)))
