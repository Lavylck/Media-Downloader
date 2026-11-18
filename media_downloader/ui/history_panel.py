from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidgetItem, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from .preview import ThumbnailView
from .card_list import CardList
from .queue_panel import STATE_NAMES
from ..queue import ACTIVE, QueueItem


class HistoryCard(QFrame):
    def __init__(self, record, panel):
        super().__init__()
        self.setObjectName("historyCard")
        self.record, self.panel = record, panel
        self.key = f"history-{record['id']}-{id(self)}"
        layout = QHBoxLayout(self)
        self.image = ThumbnailView(compact=True)
        self.image.setFixedSize(96, 76)
        layout.addWidget(self.image)
        content = QVBoxLayout()
        title = QLabel(record["title"])
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        content.addWidget(title)
        date = datetime.fromisoformat(record["created"]).astimezone().strftime("%d/%m/%Y %H:%M") if record["created"] else ""
        size = f"{record['size'] / 1048576:.2f} MiB" if record["size"] is not None else "tamanho não informado"
        text = f"{record['container']} • {record['quality_text']} • {date} • {size}\n"
        text += STATE_NAMES.get(record["state"], record["state"])
        if record["path"] and not record["exists"]:
            text += " • arquivo movido ou apagado"
        text += "\n" + (record["path"] or record["error"] or "Arquivo ainda não produzido")
        detail = QLabel(text)
        detail.setObjectName("muted")
        detail.setTextFormat(Qt.TextFormat.PlainText)
        detail.setWordWrap(True)
        detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        content.addWidget(detail)
        actions = QGridLayout()
        open_file = QPushButton("Abrir")
        open_folder = QPushButton("Pasta")
        repeat = QPushButton("Repetir")
        remove = QPushButton("Remover registro")
        open_file.setEnabled(record["exists"])
        open_folder.setEnabled(bool(record["path"]))
        repeat.setEnabled(bool(record["url"]))
        repeat.setToolTip("Links com credenciais/assinaturas não são persistidos; informe uma nova URL.")
        remove.setEnabled(record["state"] not in ACTIVE)
        open_file.clicked.connect(lambda: panel.open_path(record["path"]))
        open_folder.clicked.connect(lambda: panel.open_path(str(Path(record["path"]).parent)))
        repeat.clicked.connect(lambda: panel.repeat(record))
        remove.clicked.connect(lambda: panel.history.remove(record["id"]))
        for index, button in enumerate((open_file, open_folder, repeat, remove)):
            actions.addWidget(button, index // 2, index % 2)
        content.addLayout(actions)
        layout.addLayout(content, 1)
        panel.thumbnails.ready.connect(self._image)
        panel.thumbnails.failed.connect(self._failed)
        panel.thumbnails.request(self.key, record["thumbnail"])

    def _image(self, key, image):
        if key == self.key:
            self.image.set_image(image)

    def _failed(self, key):
        if key == self.key:
            self.image.placeholder("SEM\nIMAGEM")


class HistoryPanel(QWidget):
    def __init__(self, history, queue, thumbnails):
        super().__init__()
        self.history, self.queue, self.thumbnails = history, queue, thumbnails
        self.page, self.request_id = 0, 0
        self.cards = []
        layout = QVBoxLayout(self)
        filters = QGridLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Pesquisar título…")
        self.format = QComboBox()
        self.format.addItems(["Todos os formatos", "MP4", "MP3"])
        self.status = QComboBox()
        self.status.addItem("Todos os estados", "")
        for key, value in STATE_NAMES.items():
            self.status.addItem(value, key)
        for combo in (self.format, self.status):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(8)
        self.search.setAccessibleName("Pesquisar histórico por título")
        self.format.setAccessibleName("Filtrar histórico por formato")
        self.status.setAccessibleName("Filtrar histórico por estado")
        refresh = QPushButton("Atualizar")
        filters.addWidget(self.search, 0, 0, 1, 2)
        filters.addWidget(refresh, 0, 2)
        filters.addWidget(self.format, 1, 0)
        filters.addWidget(self.status, 1, 1, 1, 2)
        layout.addLayout(filters)
        self.message = QLabel("Carregando histórico…")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.list = CardList()
        self.list.setSpacing(8)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.list, 1)
        controls = QHBoxLayout()
        self.previous = QPushButton("Anterior")
        self.next = QPushButton("Próxima")
        controls.addWidget(self.previous)
        controls.addWidget(self.next)
        layout.addLayout(controls)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(self.filters_changed)
        self.format.currentIndexChanged.connect(self.filters_changed)
        self.status.currentIndexChanged.connect(self.filters_changed)
        refresh.clicked.connect(self.refresh)
        self.previous.clicked.connect(lambda: self.change_page(-1))
        self.next.clicked.connect(lambda: self.change_page(1))
        history.result.connect(self._result)
        history.error.connect(self.message.setText)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def filters_changed(self):
        self.page = 0
        self.timer.start()

    def change_page(self, delta):
        self.page = max(0, self.page + delta)
        self.refresh()

    def refresh(self):
        self.request_id += 1
        self.history.query(self.request_id, search=self.search.text().strip(),
                           container=self.format.currentText() if self.format.currentIndex() else "",
                           status=self.status.currentData(), page=self.page)

    @Slot(str, object)
    def _result(self, kind, result):
        if kind in ("saved", "removed") and self.isVisible():
            self.timer.start()
        if kind != "query" or result["request"] != self.request_id:
            return
        for card in self.cards:
            self.thumbnails.cancel(card.key)
        self.cards.clear()
        self.list.clear()
        for record in result["records"]:
            card = HistoryCard(record, self)
            row = QListWidgetItem()
            row.setSizeHint(card.sizeHint())
            self.list.addItem(row)
            self.list.setItemWidget(row, card)
            self.cards.append(card)
        self.list.fit_rows()
        self.message.setText(f"{result['total']} registros • página {self.page + 1}. "
                             "Remover registro não apaga o arquivo.")
        self.previous.setEnabled(self.page > 0)
        self.next.setEnabled((self.page+1)*25 < result["total"])

    def open_path(self, path):
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            self.message.setText("Não foi possível abrir. O arquivo ou a pasta pode ter sido movido.")

    def repeat(self, record):
        item = QueueItem(record["url"], record["destination"], record["container"],
                         record["quality"], record["quality_text"], record["title"], record["thumbnail"])
        added = self.queue.add([item])
        self.message.setText("Adicionado à fila." if added else "Esse download já está na fila.")
