"""SQLite persistence, serialized on a dedicated Qt worker thread."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot

from .paths import data_dir

SENSITIVE = re.compile(
    r"token|secret|password|signature|credential|auth|api.?key|session|^sig$|^lsig$|"
    r"^expires?$|^policy$|^key-pair-id$|^jwt$", re.I)


def persistent_url(url):
    """Do not persist signed URLs or credentials. In-memory downloads still work."""
    try:
        parts = urlsplit(url or "")
        if parts.scheme not in ("http", "https") or parts.username or parts.password:
            return ""
        if any(SENSITIVE.search(key) for key, value in parse_qsl(parts.query)):
            return ""
        return url
    except ValueError:
        return ""


def redact(message):
    def clean(match):
        try:
            parts = urlsplit(match[0])
            return urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, "", ""))
        except ValueError:
            return "[URL]"
    return re.sub(r"https?://[^\s<>\"']+", clean, str(message))[:2000]


class HistoryStore:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=10)
        self.connection.row_factory = sqlite3.Row
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            self.connection.close()
            raise RuntimeError("Banco criado por uma versão mais recente; não será alterado.")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS downloads (
                id TEXT PRIMARY KEY, title TEXT, container TEXT, quality_text TEXT,
                status TEXT, path TEXT, destination TEXT, url TEXT, thumbnail TEXT,
                quality TEXT, created TEXT, updated TEXT, size INTEGER, error TEXT, group_key TEXT
            );
            CREATE INDEX IF NOT EXISTS history_status ON downloads(status, updated);
            CREATE INDEX IF NOT EXISTS history_format ON downloads(container);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            PRAGMA user_version=1;
        """)

    def save(self, record):
        values = (record["id"], redact(record.get("title", "")), record.get("container", "MP4"),
                  record.get("quality_text", ""), record.get("state", "pending"),
                  record.get("path", ""), record.get("destination", ""),
                  persistent_url(record.get("url")), persistent_url(record.get("thumbnail")),
                  json.dumps(record.get("quality")), record.get("created"),
                  datetime.now(timezone.utc).isoformat(), record.get("size"),
                  redact(record.get("error", "")), persistent_url(record.get("group")))
        with self.connection:
            self.connection.execute("""
                INSERT INTO downloads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title, status=excluded.status,
                path=excluded.path, updated=excluded.updated, size=excluded.size,
                error=excluded.error, thumbnail=excluded.thumbnail
            """, values)

    @staticmethod
    def _record(row, check_file=True):
        item = dict(row)
        item["quality"] = json.loads(item["quality"])
        item["state"] = item.pop("status")
        item["group"] = item.pop("group_key")
        item["exists"] = bool(item["path"] and Path(item["path"]).is_file()) if check_file else None
        return item

    def query(self, search="", container="", status="", page=0):
        conditions, values = [], []
        if search:
            conditions.append("title LIKE ? ESCAPE '\\'")
            values.append("%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
        if container:
            conditions.append("container=?")
            values.append(container)
        if status:
            conditions.append("status=?")
            values.append(status)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        total = self.connection.execute("SELECT COUNT(*) FROM downloads" + where, values).fetchone()[0]
        rows = self.connection.execute(
            "SELECT * FROM downloads" + where + " ORDER BY updated DESC LIMIT 25 OFFSET ?",
            [*values, max(0, page)*25]).fetchall()
        return {"records": [self._record(row) for row in rows], "total": total}

    def recover(self):
        with self.connection:
            self.connection.execute("""UPDATE downloads SET status='interrupted'
                WHERE status IN ('pending','analyzing','downloading','converting','cancelling')""")
        rows = self.connection.execute(
            "SELECT * FROM downloads WHERE status='interrupted' ORDER BY created LIMIT 1000").fetchall()
        return [self._record(row, False) for row in rows]

    def remove(self, item_id):
        with self.connection:
            self.connection.execute("DELETE FROM downloads WHERE id=?", (item_id,))

    def settings(self, values=None):
        if values is not None:
            with self.connection:
                self.connection.executemany("INSERT OR REPLACE INTO settings VALUES (?,?)",
                                            [(k, json.dumps(v)) for k, v in values.items()])
        return {row["key"]: json.loads(row["value"])
                for row in self.connection.execute("SELECT * FROM settings")}

    def close(self):
        self.connection.close()


class _HistoryWorker(QObject):
    result = Signal(str, object)
    error = Signal(str)
    finished = Signal()

    def __init__(self, path):
        super().__init__()
        self.path, self.store = path, None

    @Slot()
    def initialize(self):
        try:
            self.store = HistoryStore(self.path)
            self.result.emit("restore", self.store.recover())
            self.result.emit("settings", self.store.settings())
        except Exception as exc:
            self.error.emit(f"Histórico indisponível: {redact(exc)}")

    @Slot(str, object)
    def execute(self, command, payload):
        try:
            if command == "close":
                if self.store:
                    self.store.close()
                self.finished.emit()
                return
            if self.store is None:
                raise RuntimeError("Banco não inicializado.")
            if command == "save":
                self.store.save(payload)
                self.result.emit("saved", payload["id"])
            elif command == "query":
                self.result.emit("query", {**self.store.query(**payload["filters"]), "request": payload["request"]})
            elif command == "remove":
                self.store.remove(payload)
                self.result.emit("removed", payload)
            elif command == "settings":
                self.store.settings(payload)
        except Exception as exc:
            self.error.emit(redact(exc))
            if command == "close":
                self.finished.emit()


class HistoryService(QObject):
    command = Signal(str, object)
    result = Signal(str, object)
    error = Signal(str)
    closed = Signal()

    def __init__(self, parent=None, path=None):
        super().__init__(parent)
        self.is_closed, self.closing = False, False
        self.thread = QThread(self)
        self.worker = _HistoryWorker(path or data_dir() / "history.sqlite3")
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.initialize)
        self.command.connect(self.worker.execute, Qt.ConnectionType.QueuedConnection)
        self.worker.result.connect(self.result, Qt.ConnectionType.QueuedConnection)
        self.worker.error.connect(self.error, Qt.ConnectionType.QueuedConnection)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._stopped, Qt.ConnectionType.QueuedConnection)
        # Let the owner connect result slots before initialization can finish.
        QTimer.singleShot(0, self, self.thread.start)

    @Slot(dict)
    def save(self, record):
        if not self.closing:
            self.command.emit("save", record)

    def query(self, request, **filters):
        if not self.closing:
            self.command.emit("query", {"request": request, "filters": filters})

    def remove(self, item_id):
        self.command.emit("remove", item_id)

    def save_settings(self, values):
        if not self.closing:
            self.command.emit("settings", values)

    def close(self):
        if not self.closing:
            self.closing = True
            self.command.emit("close", None)

    @Slot()
    def _stopped(self):
        if not self.thread.wait(0):
            QTimer.singleShot(10, self, self._stopped)
            return
        self.thread.deleteLater()
        self.worker = self.thread = None
        self.is_closed = True
        self.closed.emit()
