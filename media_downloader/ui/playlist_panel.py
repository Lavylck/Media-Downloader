from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QHeaderView


class PlaylistPanel(QFrame):
    page_requested = Signal(int)
    selection_changed = Signal()
    cancel_group = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.selected = {}
        self.loaded = {}
        self.source = ""
        self.offset = 0
        self.has_more = False
        self.auto_all = False
        self.loading = False
        self.pages = {}
        self.auto_timer = QTimer(self)
        self.auto_timer.setSingleShot(True)
        self.auto_timer.timeout.connect(self._continue_all)
        layout = QVBoxLayout(self)
        self.summary = QLabel("Playlist")
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Selecionar", "Mídia"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 90)
        self.table.setMinimumHeight(210)
        self.table.setMaximumHeight(320)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemChanged.connect(self._selection)
        layout.addWidget(self.table)
        controls = QHBoxLayout()
        self.all_btn = QPushButton("Selecionar todos")
        self.clear_btn = QPushButton("Limpar seleção")
        self.more_btn = QPushButton("Carregar mais")
        self.stop_btn = QPushButton("Parar carregamento")
        self.all_btn.clicked.connect(self.select_all)
        self.clear_btn.clicked.connect(self.clear_selection)
        self.more_btn.clicked.connect(self.more)
        self.stop_btn.clicked.connect(self.stop_loading)
        for button in (self.all_btn, self.clear_btn):
            controls.addWidget(button)
        layout.addLayout(controls)
        pages = QHBoxLayout()
        self.previous_btn = QPushButton("Página anterior")
        self.previous_btn.clicked.connect(self.previous)
        pages.addWidget(self.previous_btn)
        pages.addWidget(self.more_btn)
        layout.addLayout(pages)
        secondary = QHBoxLayout()
        secondary.addWidget(self.stop_btn)
        cancel = QPushButton("Cancelar esta playlist na fila")
        cancel.clicked.connect(lambda: self.cancel_group.emit(self.source))
        secondary.addWidget(cancel)
        layout.addLayout(secondary)
        self.selection_label = QLabel("Nenhum item selecionado")
        layout.addWidget(self.selection_label)
        self.hide()

    def reset(self):
        self.selected.clear()
        self.loaded.clear()
        self.pages.clear()
        self.auto_timer.stop()
        self.auto_all = False
        self.loading = False
        self.source = ""
        self.table.setRowCount(0)
        self.hide()

    def set_page(self, info):
        self.source = info["webpage_url"]
        self.pages[info["offset"]] = info
        self.offset = info["offset"]
        self.has_more = info["has_more"]
        self.loading = False
        self.table.blockSignals(True)
        self.table.setRowCount(len(info["entries"]))
        for row, entry in enumerate(info["entries"]):
            key = str(entry["index"])
            self.loaded[key] = entry
            if self.auto_all and entry["available"]:
                self.selected[key] = entry
            check = QTableWidgetItem()
            check.setData(Qt.ItemDataRole.UserRole, key)
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                           if entry["available"] else Qt.ItemFlag.NoItemFlags)
            check.setCheckState(Qt.CheckState.Checked if key in self.selected else Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, check)
            title = QTableWidgetItem(f"{entry['index']}. {entry['title']}"
                                    + ("" if entry["available"] else " [indisponível]"))
            title.setToolTip(title.text())
            self.table.setItem(row, 1, title)
        self.table.blockSignals(False)
        count = info.get("playlist_count")
        self.summary.setText(f"{info['title']} • {count if count else 'quantidade não informada'} itens"
                             f" • página {self.offset // 100 + 1}")
        self.more_btn.setEnabled(self.has_more)
        self.previous_btn.setEnabled(self.offset > 0)
        self.show()
        self._refresh_count()
        if self.auto_all and self.has_more:
            self.auto_timer.start(0)

    def _continue_all(self):
        if self.auto_all:
            self.more()

    def previous(self):
        self.auto_all = False
        self.auto_timer.stop()
        if self.offset - 100 in self.pages and not self.loading:
            self.set_page(self.pages[self.offset - 100])

    def _selection(self, item):
        if item.column() != 0:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self.selected[key] = self.loaded[key]
        else:
            self.selected.pop(key, None)
            self.auto_all = False
        self._refresh_count()

    def _refresh_count(self):
        self.selection_label.setText(f"{len(self.selected)} selecionados • {len(self.loaded)} carregados")
        self.selection_changed.emit()

    def select_all(self):
        self.auto_all = True
        self.selected = {key: entry for key, entry in self.loaded.items() if entry["available"]}
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            check = self.table.item(row, 0)
            if check.flags() & Qt.ItemFlag.ItemIsEnabled:
                check.setCheckState(Qt.CheckState.Checked)
        self.table.blockSignals(False)
        self._refresh_count()
        if self.has_more:
            self.more()

    def clear_selection(self):
        self.auto_all = False
        self.selected.clear()
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.CheckState.Unchecked)
        self._refresh_count()

    def more(self):
        if self.has_more and not self.loading:
            if self.offset + 100 in self.pages:
                self.set_page(self.pages[self.offset + 100])
                return
            self.loading = True
            self.more_btn.setEnabled(False)
            self.page_requested.emit(self.offset + 100)

    def stop_loading(self):
        self.auto_all = False
        self.auto_timer.stop()
        # MainWindow cancels the active analysis while keeping loaded entries.
        self.page_requested.emit(-1)

    def loading_failed(self):
        """Keep loaded pages/selection available for a manual retry."""
        self.auto_all = False
        self.auto_timer.stop()
        self.loading = False
        self.more_btn.setEnabled(self.has_more)
        self.previous_btn.setEnabled(self.offset > 0)
