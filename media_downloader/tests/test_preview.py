import tempfile
from pathlib import Path
import unittest
from PySide6.QtCore import QBuffer, QIODevice, QCoreApplication, QEvent
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication

from media_downloader.tests.test_ui import wait_until
from media_downloader.tests.test_auto_analysis import run_events
from media_downloader.ui.preview import ThumbnailService, ThumbnailView
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import time


class TestPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_landscape_portrait_square_fit_without_crop(self):
        view = ThumbnailView()
        view.resize(320, 280)
        for width, height in ((1920, 814), (400, 900), (500, 500)):
            image = QImage(width, height, QImage.Format.Format_RGB32)
            image.fill(QColor("purple"))
            view.set_image(image)
            rect = view.image_rect()
            self.assertLessEqual(rect.width(), view.width()-24)
            self.assertLessEqual(rect.height(), view.height()-24)
            self.assertAlmostEqual(rect.width()/rect.height(), width/height, delta=0.02)
        view.close()
        view.deleteLater()

    def test_http_cache_and_stale_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = QImage(300, 500, QImage.Format.Format_RGB32)
            image.fill(QColor("purple"))
            image.save(str(root/"image.png"))
            requests = []

            class Handler(SimpleHTTPRequestHandler):
                def log_message(self, *args):
                    pass

                def end_headers(self):
                    self.send_header("Cache-Control", "max-age=3600")
                    super().end_headers()

                def do_GET(self):
                    requests.append(self.path)
                    if "slow" in self.path:
                        time.sleep(0.25)
                        self.path = "/image.png"
                    try:
                        super().do_GET()
                    except (ConnectionError, BrokenPipeError):
                        pass

            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=tmp))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            service = ThumbnailService(cache_dir=root/"cache")
            results, failures = [], []
            service.ready.connect(lambda key, img: results.append((key, img.size())))
            service.failed.connect(failures.append)
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                service.request("preview", base+"/slow.png")
                service.request("preview", base+"/image.png")
                wait_until(lambda: len(results) == 1)
                run_events(350)
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0][1].height(), 500)
                before = requests.count("/image.png")
                service.request("cache-hit", base+"/image.png")
                wait_until(lambda: len(results) == 2)
                self.assertEqual(requests.count("/image.png"), before)
                service.request("none", "")
                self.assertIn("none", failures)
                for attempt in range(2):
                    service.request("private", base+"/image.png?sig=secret")
                    wait_until(lambda: len(results) == 3 + attempt)
                self.assertEqual(requests.count("/image.png?sig=secret"), 2)
                self.assertFalse(service.generation)
                self.assertFalse(service.requests)
            finally:
                service.close()
                service.manager.cache().clear()
                service.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                server.shutdown()
                server.server_close()
                thread.join()
