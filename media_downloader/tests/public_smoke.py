"""Opt-in public network validation; not part of automatic test discovery."""

import argparse
import json
from pathlib import Path
import time

from PySide6.QtCore import QObject, QTimer, Slot
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://www.w3schools.com/html/mov_bbb.mp4")
    parser.add_argument("--output", default="test-artifacts/public-smoke")
    parser.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--video-height", type=int, help="Choose an available source height")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    win = MainWindow()
    recorder = Recorder()
    win.show()
    ticks = []
    timer = QTimer()
    timer.setInterval(20)
    timer.timeout.connect(lambda: ticks.append(time.monotonic()))
    timer.start()
    report = {"url": args.url, "results": [], "warnings": recorder.messages}
    exit_code = 0
    try:
        win.url_edit.setText(args.url)
        win.dest_edit.setText(str(Path(args.output).resolve()))
        win.analyze_btn.click()
        win.analysis_worker.status.connect(recorder.status)
        wait_until(lambda: not win.busy, 120000)
        if not win.media_info:
            raise RuntimeError(win.status_label.text())
        report.update({
            "title": win.media_info.get("title"), "duration": win.media_info.get("duration"),
            "formats": len(win.media_info.get("formats") or []),
            "video_qualities": [win.quality_combo.itemText(i)
                               for i in range(win.quality_combo.count())],
        })
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
                win.download_worker.status.connect(recorder.status)
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
    report["max_tick_gap_seconds"] = round(max(
        (b - a for a, b in zip(ticks, ticks[1:])), default=0), 3)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
