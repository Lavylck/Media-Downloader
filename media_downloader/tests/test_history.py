from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from media_downloader.history import HistoryService, HistoryStore, persistent_url
from media_downloader.queue import QueueItem
from media_downloader.tests.test_ui import wait_until


class TestHistory(unittest.TestCase):
    def test_persistence_search_filters_missing_file_and_remove_without_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"media.mp4"
            path.write_bytes(b"test media")
            item = QueueItem("https://example.com/video", tmp, title="Título 100% _ teste")
            item.path, item.state, item.size = str(path), "completed", 10
            store = HistoryStore(Path(tmp)/"history.sqlite3")
            store.save(asdict(item))
            store.close()
            store = HistoryStore(Path(tmp)/"history.sqlite3")
            result = store.query(search="100% _", container="MP4", status="completed")
            self.assertEqual(result["total"], 1)
            self.assertTrue(result["records"][0]["exists"])
            self.assertEqual(store.query(container="MP3")["total"], 0)
            renamed = path.with_name("moved.mp4")
            path.rename(renamed)
            self.assertFalse(store.query()["records"][0]["exists"])
            store.remove(item.id)
            self.assertTrue(renamed.exists())
            self.assertEqual(store.query()["total"], 0)
            store.close()

    def test_interrupted_recovery_and_no_credentials_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/"history.sqlite3"
            store = HistoryStore(file)
            item = QueueItem("https://example.com/video?token=private-secret", tmp, title="Protected URL")
            item.state = "downloading"
            item.error = "HTTP failed https://example.com/x?token=private-secret"
            store.save(asdict(item))
            records = store.recover()
            self.assertEqual(records[0]["state"], "interrupted")
            self.assertEqual(records[0]["url"], "")
            self.assertNotIn("private-secret", json.dumps(records))
            store.close()
            self.assertNotIn(b"private-secret", file.read_bytes())
            self.assertEqual(persistent_url("https://user:pass@example.com/x"), "")

    def test_async_service_flush_and_settings_restart(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/"history.sqlite3"
            service = HistoryService(path=file)
            events = []
            service.result.connect(lambda kind, data: events.append((kind, data)))
            wait_until(lambda: any(k == "restore" for k, d in events))
            item = QueueItem("https://example.com/video", tmp, title="queued")
            service.save(asdict(item))
            service.save_settings({"destination": tmp, "container": "MP3"})
            service.close()
            wait_until(lambda: service.is_closed)
            service.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            store = HistoryStore(file)
            self.assertEqual(store.settings()["container"], "MP3")
            self.assertEqual(store.recover()[0]["state"], "interrupted")
            store.close()

    def test_history_pagination(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = HistoryStore(Path(tmp)/"db.sqlite3")
            for index in range(61):
                store.save(asdict(QueueItem(f"https://example.com/{index}", tmp, title=str(index))))
            self.assertEqual(len(store.query(page=0)["records"]), 25)
            self.assertEqual(len(store.query(page=2)["records"]), 11)
            store.close()
