"""Opt-in executable validation driven by the real Qt event loop.

No test framework or venv is imported. Reports are explicit user-requested files.
"""

import json
from pathlib import Path
import subprocess
import time

from PySide6.QtCore import QObject, QTimer

from .paths import VERSION, tool_path


class SmokeRun(QObject):
    def __init__(self, window, report_path, url=None, history_only=False, playlist=False):
        super().__init__(window)
        self.window = window
        self.report_path = Path(report_path)
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report = {"version": VERSION, "success": False, "outputs": [], "warnings": [],
                       "mode": "history" if history_only else "playlist" if playlist else "media"}
        self.started = time.monotonic()
        self.ticks = []
        self.phase = "history" if history_only else "analysis"
        self.playlist = playlist
        self.query_pending = False
        self.history_only = history_only
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.tick)
        window.history.result.connect(self.history_result)
        self.initial_records = None
        if not history_only:
            window.dest_edit.setText(str(self.report_path.parent / "downloads"))
            if playlist:
                window.source_mode.setCurrentIndex(1)
            window.url_edit.setText(url)
        self.timer.start()

    def history_result(self, kind, data):
        if kind == "query" and data["request"] == -999:
            self.report["history_total"] = data["total"]
            self.report["history_states"] = [record["state"] for record in data["records"]]
            if self.history_only:
                if data["total"] < 2:
                    self.fail("Persistência após reinício não confirmou os downloads.")
                else:
                    self.finish()
            else:
                self.finish()

    def tick(self):
        self.ticks.append(time.monotonic())
        win = self.window
        if time.monotonic() - self.started > 150:
            self.fail("Timeout de 150 s")
            return
        if self.phase == "history":
            if not self.query_pending:
                self.query_pending = True
                win.tabs.setCurrentWidget(win.history_panel)
                win.history.query(-999)
            return
        if self.phase == "analysis":
            if win.analysis_timer.isActive() or win.analysis_thread is not None or win._auto_pending:
                return
            if not win.media_info:
                self.fail(win.status_label.text())
                return
            self.report["title"] = win.media_info.get("title")
            self.report["qualities"] = [win.quality_combo.itemText(i) for i in range(win.quality_combo.count())]
            if self.playlist:
                # Explicitly select a bounded sample, never a whole public playlist.
                for row in range(min(3, win.playlist_panel.table.rowCount())):
                    check = win.playlist_panel.table.item(row, 0)
                    from PySide6.QtCore import Qt
                    if check.flags() & Qt.ItemFlag.ItemIsEnabled:
                        check.setCheckState(Qt.CheckState.Checked)
            win.grab().save(str(self.report_path.with_suffix(".png")))
            win.format_combo.setCurrentText("MP4")
            win.start_download()
            self.phase = "mp4"
            return
        if win.queue.busy:
            return
        if self.phase == "mp4":
            if not any(item.state == "completed" for item in win.queue.items):
                self.fail("Nenhum MP4 concluído: " + "; ".join(i.error for i in win.queue.items))
                return
            win.format_combo.setCurrentText("MP3")
            win.start_download()
            self.phase = "mp3"
        elif self.phase == "mp3":
            self.report["queue_states"] = [item.state for item in win.queue.items]
            for item in win.queue.items:
                if item.state != "completed":
                    continue
                self.report["outputs"].append({"path": item.path, "container": item.container,
                                                "bytes": item.size, "progress": item.progress})
            if not any(item.container == "MP3" and item.state == "completed" for item in win.queue.items):
                self.fail("Nenhum MP3 concluído.")
                return
            self.phase = "history"

    def fail(self, error):
        self.report["error"] = str(error)
        self.finish(False)

    def finish(self, success=True):
        self.timer.stop()
        self.phase = "done"
        self.window.grab().save(str(self.report_path.with_name("final.png")))
        self.window.tabs.setCurrentWidget(self.window.queue_panel)
        self.window.grab().save(str(self.report_path.with_name("queue.png")))
        self.report["success"] = success
        self.report["qt_ticks"] = len(self.ticks)
        self.report["max_tick_gap"] = round(max(
            (b-a for a, b in zip(self.ticks, self.ticks[1:])), default=0), 4)
        self.report["tools"] = {name: tool_path(name) for name in ("ffmpeg", "ffprobe", "node")}
        self.report_path.write_text(json.dumps(self.report, indent=2, ensure_ascii=True), encoding="utf-8")
        self.window.close()
