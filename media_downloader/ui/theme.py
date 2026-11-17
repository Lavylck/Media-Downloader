"""Small, local-only theme loader. No fonts or assets fetched at runtime."""

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def neon_stylesheet():
    directory = Path(__file__).with_name("themes")
    return (directory / "neon.qss").read_text(encoding="utf-8").replace(
        "@THEME_DIR@", directory.as_posix())


def apply_theme(window):
    window.setStyleSheet(neon_stylesheet())


def set_style_property(widget, name, value):
    """Repolish only on state transitions, not on each progress event."""
    if widget.property(name) != value:
        widget.setProperty(name, value)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
