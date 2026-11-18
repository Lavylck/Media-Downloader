from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidgetItem, QProgressBar, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from .preview import ThumbnailView
from .card_list import CardList
from ..queue import ACTIVE

STATE_NAMES = {
    "pending": "Na fila", "analyzing": "Analisando", "downloading": "Baixando",
    "converting": "Convertendo", "completed": "Concluído", "failed": "Erro",
    "cancelled": "Cancelado", "cancelling": "Cancelando", "interrupted": "Interrompido",
    "pausing": "Pausando", "paused": "Pausado",
}


class QueueCard(QFrame):
    def __init__(self, item, queue, thumbnails):
        super().__init__()
        self.setObjectName("queueCard")
        self.item = item
        self.thumbnails = thumbnails
        self.key = f"queue-{item.id}-{id(self)}"
        self.image_url = None
        layout = QHBoxLayout(self)
        self.image = ThumbnailView(compact=True)
        self.image.setFixedSize(96, 76)
        layout.addWidget(self.image)
        content = QVBoxLayout()
        self.title = QLabel()
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setWordWrap(True)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.description = QLabel()
        self.description.setTextFormat(Qt.TextFormat.PlainText)
        self.description.setWordWrap(True)
        self.description.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.description.setObjectName("muted")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        content.addWidget(self.title)
        content.addWidget(self.description)
        content.addWidget(self.progress)
        actions = QGridLayout()
        self.cancel = QPushButton("Cancelar")
        self.pause = QPushButton("Pausar")
        self.pause.clicked.connect(lambda: (queue.resume if item.state == "paused" else queue.pause)(item.id))
        self.retry = QPushButton("Tentar novamente")
        remove = QPushButton("Remover")
        self.cancel.clicked.connect(lambda: queue.cancel(item.id))
        self.retry.clicked.connect(lambda: queue.retry(item.id))
        remove.clicked.connect(lambda: queue.remove(item.id))
        actions.addWidget(self.cancel, 0, 0)
        actions.addWidget(self.pause, 0, 1)
        actions.addWidget(remove, 0, 1)
        self.remove_button = remove
        actions.addWidget(self.retry, 1, 0, 1, 2)
        content.addLayout(actions)
        layout.addLayout(content, 1)
        thumbnails.ready.connect(self._image)
        thumbnails.failed.connect(self._failed)
        self.refresh()

    def _image(self, key, image):
        if key == self.key:
            self.image.set_image(image)

    def _failed(self, key):
        if key == self.key:
            self.image.placeholder("SEM\nIMAGEM")

    def refresh(self):
        item = self.item
        self.title.setText(item.title or item.url)
        text = f"{item.container} • {item.quality_text} • {STATE_NAMES.get(item.state, item.state)}"
        if item.progress >= 0:
            text += f" • {item.progress}%"
        if item.speed:
            text += f" • {item.speed / 1048576:.2f} MiB/s"
        if item.eta is not None:
            text += f" • faltam {int(item.eta)} s"
        if item.error:
            text += f"\n{item.error}"
        self.description.setText(text)
        self.progress.setRange(0, 0 if item.progress < 0 and item.state in ACTIVE else 100)
        self.progress.setValue(max(0, item.progress))
        self.cancel.setEnabled(item.state in ACTIVE and item.state != "cancelling")
        self.pause.setVisible(item.state in ACTIVE)
        self.pause.setText("Retomar" if item.state == "paused" else "Pausar")
        self.pause.setEnabled(item.state in ("pending", "paused") or
                              (item.state == "downloading" and item.resumable))
        self.pause.setToolTip("Antes do início ou em transferência HTTP com retomada por bytes.")
        self.remove_button.setVisible(item.state not in ACTIVE)
        self.retry.setEnabled(item.state not in ACTIVE and bool(item.url))
        if self.image_url != item.thumbnail:
            self.image_url = item.thumbnail
            self.thumbnails.request(self.key, item.thumbnail)

    def dispose(self):
        self.thumbnails.cancel(self.key)


class QueuePanel(QWidget):
    PAGE_SIZE = 25

    def __init__(self, queue, thumbnails):
        super().__init__()
        self.queue, self.thumbnails = queue, thumbnails
        self.page = 0
        self.cards = {}
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.summary = QLabel("Fila sequencial")
        self.summary.setWordWrap(True)
        cancel = QPushButton("Cancelar toda a fila")
        cancel.clicked.connect(queue.cancel_all)
        header.addWidget(self.summary, 1)
        header.addWidget(cancel)
        layout.addLayout(header)
        self.list = CardList()
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setSpacing(8)
        layout.addWidget(self.list, 1)
        pages = QHBoxLayout()
        self.previous = QPushButton("Anterior")
        self.next = QPushButton("Próxima")
        self.previous.clicked.connect(lambda: self.change_page(-1))
        self.next.clicked.connect(lambda: self.change_page(1))
        pages.addWidget(self.previous)
        pages.addWidget(self.next)
        layout.addLayout(pages)
        queue.structure_changed.connect(self.render)
        queue.item_changed.connect(self.update_item)
        queue.active_changed.connect(self.update_summary)
        self.render()

    def change_page(self, delta):
        self.page = max(0, self.page + delta)
        self.render()

    def update_summary(self):
        self.summary.setText(f"Fila sequencial • {len(self.queue.items)} itens • "
                             f"{sum(i.state in ACTIVE for i in self.queue.items)} pendentes/ativos")

    def render(self):
        for card in self.cards.values():
            card.dispose()
        self.cards.clear()
        self.list.clear()
        self.page = min(self.page, max(0, (len(self.queue.items)-1) // self.PAGE_SIZE))
        items = self.queue.items[self.page*self.PAGE_SIZE:(self.page+1)*self.PAGE_SIZE]
        for item in items:
            card = QueueCard(item, self.queue, self.thumbnails)
            row = QListWidgetItem()
            row.setSizeHint(card.sizeHint())
            self.list.addItem(row)
            self.list.setItemWidget(row, card)
            self.cards[item.id] = card
        self.previous.setEnabled(self.page > 0)
        self.next.setEnabled((self.page+1)*self.PAGE_SIZE < len(self.queue.items))
        self.list.fit_rows()
        self.update_summary()

    def update_item(self, item_id):
        if item_id in self.cards:
            self.cards[item_id].refresh()
            self.list.fit_rows()
        self.update_summary()
