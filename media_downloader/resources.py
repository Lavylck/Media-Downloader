from PySide6.QtGui import QIcon

from pathlib import Path

ICON_DIR = Path(__file__).resolve().parents[1] / "assets" / "icons"
ICON_PNG = ICON_DIR / "media_downloader_icone_neon_transparente.png"
ICON_ICO = ICON_DIR / "media_downloader_icone_oficial.ico"


def app_icon():
    return QIcon(str(ICON_ICO))
