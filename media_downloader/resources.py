from PySide6.QtGui import QIcon

from .paths import resource_path


def app_icon():
    # The supplied SVG is TEMPORARY, not an approved final brand.
    for extension in ("ico", "png", "svg"):
        path = resource_path("assets", f"icon.{extension}")
        if path.is_file():
            return QIcon(str(path))
    return QIcon()
