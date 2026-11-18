from PySide6.QtCore import QEvent, QSize
from PySide6.QtWidgets import QListWidget


class CardList(QListWidget):
    """Keep wrapped card contents and actions inside each list row."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.viewport().installEventFilter(self)

    def fit_rows(self):
        width = max(1, self.viewport().width() - 2 * self.spacing())
        for index in range(self.count()):
            row = self.item(index)
            card = self.itemWidget(row)
            if card is None:
                continue
            height = max(card.minimumSizeHint().height(),
                         card.layout().totalHeightForWidth(width))
            size = QSize(width, height)
            if size != row.sizeHint():
                row.setSizeHint(size)

    def eventFilter(self, watched, event):
        if watched is self.viewport() and event.type() == QEvent.Type.Resize:
            self.fit_rows()
        return super().eventFilter(watched, event)
