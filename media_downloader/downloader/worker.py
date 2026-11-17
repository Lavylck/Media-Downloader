"""Compatibility import; the only worker implementation lives in ui."""

from ..ui.download_worker import DownloadWorker

__all__ = ["DownloadWorker"]
