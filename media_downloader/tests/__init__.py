"""Isolated test data: never write test history into the user's real database."""

import os
from pathlib import Path
import tempfile

_root = Path.home() / "AppData/Local/Temp/opencode"
_data = tempfile.TemporaryDirectory(prefix="media-test-data-", dir=_root if _root.exists() else None)
os.environ.setdefault("MEDIA_DOWNLOADER_DATA_DIR", _data.name)
