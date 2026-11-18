import logging
from logging.handlers import RotatingFileHandler

from .history import redact
from .paths import data_dir


class PrivateFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


def configure_logging():
    directory = data_dir() / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / "application.log", maxBytes=1_000_000,
                                  backupCount=3, encoding="utf-8")
    handler.setFormatter(PrivateFormatter("%(asctime)s %(levelname)s %(message)s"))
    logger = logging.getLogger("media_downloader")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger
