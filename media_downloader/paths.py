"""Per-user writable locations and read-only bundled resources."""

import os
from pathlib import Path
import shutil
import sys

VERSION = "3.0.0"


def data_dir():
    override = os.environ.get("MEDIA_DOWNLOADER_DATA_DIR")
    root = Path(override) if override else Path(
        os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "MediaDownloader"
    root.mkdir(parents=True, exist_ok=True)
    return root


def resource_path(*parts):
    return Path(__file__).resolve().parent.joinpath(*parts)


def tool_path(name):
    if getattr(sys, "frozen", False):
        candidate = Path(sys._MEIPASS) / "bin" / f"{name}.exe"
        if candidate.is_file():
            return str(candidate)
    return shutil.which(name)
