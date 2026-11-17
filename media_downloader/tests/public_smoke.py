"""Opt-in public network validation; not part of automatic test discovery."""

import argparse
import json
from pathlib import Path
import time

from PySide6.QtCore import QObject, QTimer, Slot, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from media_downloader.tests.test_real_media import probe
from media_downloader.tests.test_ui import wait_until
from media_downloader.ui.main_window import MainWindow


class Recorder(QObject):
    def __init__(self):
        super().__init__()
        self.messages = []

    @Slot(str)
    def status(self, message):
        if message.startswith("Aviso:"):
            self.messages.append(message)

    @Slot(int, str)
    def analysis_status(self, request_id, message):
        self.status(message)


class RecordedWindow(MainWindow):
    """Attach observers before workers start, so early warnings are not missed."""

    def __init__(self, recorder):
        self.recorder = recorder
        self.analysis_requests = 0
        super().__init__()

    def _start_worker(self, kind, worker):
        if kind == "analysis":
            self.analysis_requests += 1
            worker.status.connect(self.recorder.analysis_status)
        else:
            worker.status.connect(self.recorder.status)
        super()._start_worker(kind, worker)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://www.w3schools.com/html/mov_bbb.mp4")
    parser.add_argument("--output", default="test-artifacts/public-smoke")
    parser.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--video-height", type=int, help="Choose an available source height")
    parser.add_argument("--manual", action="store_true", help="Use Analisar instead of automatic paste")
    parser.add_argument("--screenshot", help="Save the analyzed window as a PNG")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    recorder = Recorder()
    win = RecordedWindow(recorder)
    win.show()
    ticks = []
    timer = QTimer()
    timer.setInterval(20)
    timer.timeout.connect(lambda: ticks.append(time.monotonic()))
    timer.start()
    report = {"url": args.url, "results": [], "warnings": recorder.messages}
    exit_code = 0
    try:
        clipboard = QApplication.clipboard()
        previous = clipboard.text()
        try:
            clipboard.setText(args.url)
            QTest.keyClick(win.url_edit, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
        finally:
            clipboard.setText(previous)
        win.dest_edit.setText(str(Path(args.output).resolve()))
        if args.manual:
            win.analyze_btn.click()
        wait_until(lambda: not (win.busy or win.analysis_timer.isActive() or win._auto_pending), 120000)
        if not win.media_info:
            raise RuntimeError(win.status_label.text())
        report.update({
            "title": win.media_info.get("title"), "duration": win.media_info.get("duration"),
            "formats": len(win.media_info.get("formats") or []),
            "video_qualities": [win.quality_combo.itemText(i)
                               for i in range(win.quality_combo.count())],
        })
        if args.screenshot:
            image = Path(args.screenshot)
            image.parent.mkdir(parents=True, exist_ok=True)
            if not win.grab().save(str(image)):
                raise RuntimeError("Could not save screenshot")
        if not args.analyze_only:
            for container in ("MP4", "MP3"):
                win.format_combo.setCurrentText(container)
                if container == "MP4" and args.video_height:
                    index = win.quality_combo.findData(args.video_height)
                    if index < 0:
                        raise RuntimeError("Requested height is not available")
                    win.quality_combo.setCurrentIndex(index)
                win.download_btn.click()
                if win.download_worker is None:
                    raise RuntimeError(win.status_label.text())
                wait_until(lambda: not win.busy, 120000)
                if not win.last_output:
                    raise RuntimeError(win.status_label.text())
                media = probe(win.last_output)
                report["results"].append({
                    "container": container, "path": win.last_output,
                    "bytes": Path(win.last_output).stat().st_size,
                    "duration": media["format"].get("duration"),
                    "codecs": [stream["codec_name"] for stream in media["streams"]],
                    "video_heights": [s["height"] for s in media["streams"] if "height" in s],
                    "progress": win.progress.value(),
                })
    except Exception as exc:
        report["error"] = str(exc)
        exit_code = 1
    finally:
        if win.busy:
            win.cancel_operation()
            wait_until(lambda: not win.busy, 60000)
        timer.stop()
        win.close()
    report["qt_timer_ticks"] = len(ticks)
    report["analysis_mode"] = "manual" if args.manual else "automatic paste"
    report["analysis_requests"] = win.analysis_requests
    report["max_tick_gap_seconds"] = round(max(
        (b - a for a, b in zip(ticks, ticks[1:])), default=0), 3)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
