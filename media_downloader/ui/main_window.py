from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from PySide6.QtCore import QThread, QTimer, Qt, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QBoxLayout, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QInputDialog, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)

from ..downloader.yt_dlp_wrapper import YtDlpWrapper, validate_url
from .analysis_worker import AnalysisWorker
from .download_worker import DownloadWorker
from .theme import apply_theme, set_style_property
from .preview import PreviewPanel, ThumbnailService
from ..resources import app_icon, ICON_PNG
from ..queue import DownloadQueue, QueueItem
from .queue_panel import QueuePanel, STATE_NAMES
from .playlist_panel import PlaylistPanel
from ..history import HistoryService
from .history_panel import HistoryPanel


class MainWindow(QMainWindow):
    def __init__(self, ydl_wrapper=None, *, analysis_debounce_ms=600):
        super().__init__()
        self.setWindowTitle("Media Downloader V3 · Cyberpunk Edition")
        self.setMinimumSize(620, 520)
        self.resize(1180, min(860, self.screen().availableGeometry().height() - 70))
        self.setWindowIcon(app_icon())
        self.thumbnails = ThumbnailService(self)
        self.ydl = ydl_wrapper or YtDlpWrapper()
        self.queue = DownloadQueue(self.ydl, self)
        self.history = HistoryService(self)
        self.analysis_in_progress = False
        self.download_in_progress = False
        self.analysis_thread = None
        self.analysis_worker = None
        self.download_thread = None
        self.download_worker = None
        self.media_info = None
        self.analyzed_url = None
        self.last_output = None
        self._closing = False
        self._cancelling = False
        self._input_url = ""
        self._url_revision = 0
        self._analysis_revision = None
        self._request_serial = 0
        self._active_request_id = None
        self._attempted_revision = None
        self._auto_pending = False
        self._cancel_requested = False
        self._playlist_pending_offset = None
        self._format_edited = False
        self._resetting = False
        self._reset_item = None
        self._form_cleared = False
        self.analysis_timer = QTimer(self)
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.setInterval(analysis_debounce_ms)
        self.analysis_timer.timeout.connect(self._auto_analyze)
        self.init_ui()
        apply_theme(self)
        self.queue.active_changed.connect(self._queue_changed)
        self.queue.item_changed.connect(self._queue_item_changed)
        self.queue.item_finished.connect(self._queue_finished)
        self.queue.persist.connect(self.history.save)
        self.history.result.connect(self._history_result)
        self.history.error.connect(self._history_error)
        self.history.closed.connect(self._history_closed)
        self._update_controls()

    def init_ui(self):
        def label(text, name):
            widget = QLabel(text)
            widget.setObjectName(name)
            widget.setTextFormat(Qt.TextFormat.PlainText)
            return widget

        def card():
            frame = QFrame()
            frame.setObjectName("card")
            box = QVBoxLayout(frame)
            box.setContentsMargins(18, 14, 18, 14)
            box.setSpacing(10)
            layout.addWidget(frame)
            return box

        scroll = QScrollArea()
        self.scroll_area = scroll
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.addTab(scroll, "Mídia")
        self.queue_panel = QueuePanel(self.queue, self.thumbnails)
        self.tabs.addTab(self.queue_panel, "Fila")
        self.history_panel = HistoryPanel(self.history, self.queue, self.thumbnails)
        self.tabs.addTab(self.history_panel, "Histórico")
        central = QWidget()
        central.setObjectName("appSurface")
        scroll.setWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(14)
        header = QHBoxLayout()
        mark = label("", "brandMark")
        mark.setFixedSize(50, 50)
        mark.setPixmap(QIcon(str(ICON_PNG)).pixmap(mark.size(), self.devicePixelRatioF()))
        mark.setAccessibleName("Media Downloader")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(mark)
        brand = QVBoxLayout()
        brand.setSpacing(2)
        for text, name in (("MEDIA DOWNLOADER", "brandTitle"),
                           ("Sua mídia. Na melhor qualidade.", "subtitle")):
            heading = label(text, name)
            heading.setWordWrap(True)
            brand.addWidget(heading)
        header.addLayout(brand, 1)
        layout.addLayout(header)
        self.content_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        layout.addLayout(self.content_layout)
        self.form_widget = QWidget()
        self.content_layout.addWidget(self.form_widget, 7)
        self.preview = PreviewPanel(self.thumbnails)
        self.content_layout.addWidget(self.preview, 3)
        layout = QVBoxLayout(self.form_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        source = card()
        source.addWidget(label("LINK DA MÍDIA", "sectionLabel"))
        url_layout = QHBoxLayout()
        url_layout.setSpacing(10)
        self.url_edit = QLineEdit()
        self.url_edit.setObjectName("urlInput")
        self.url_edit.setAccessibleName("URL da mídia")
        self.url_edit.setPlaceholderText("Cole seu link aqui…")
        self.url_edit.setClearButtonEnabled(True)
        self.paste_action = self.url_edit.addAction(
            QIcon(str(Path(__file__).parent / "themes/paste.svg")), QLineEdit.ActionPosition.TrailingPosition)
        self.paste_action.setText("Colar URL")
        self.paste_action.setToolTip("Colar URL da área de transferência")
        self.paste_action.triggered.connect(self.url_edit.paste)
        self.url_edit.textChanged.connect(lambda text: self.paste_action.setVisible(not text))
        self.url_edit.setMinimumHeight(44)
        self.url_edit.textChanged.connect(self._on_url_changed)
        self.url_edit.returnPressed.connect(self.analyze_url)
        self.analyze_btn = QPushButton("Analisar")
        self.analyze_btn.setMinimumHeight(44)
        self.analyze_btn.setToolTip("Analisar novamente, mesmo se o link não mudou (Enter).")
        self.analyze_btn.clicked.connect(self.analyze_url)
        self.add_link_btn = QPushButton("+")
        self.add_link_btn.setObjectName("addButton")
        self.add_link_btn.setAccessibleName("Adicionar links à fila")
        self.add_link_btn.setToolTip("Adicionar um ou vários links à fila, mesmo durante um download.")
        self.add_link_btn.clicked.connect(self.add_links_dialog)
        url_layout.addWidget(self.url_edit, 1)
        url_layout.addWidget(self.analyze_btn)
        url_layout.addWidget(self.add_link_btn)
        source.addLayout(url_layout)
        source_note = label("Análise automática ao colar ou pausar a digitação. Enter para antecipar.", "muted")
        source_note.setWordWrap(True)
        source.addWidget(source_note)
        mode_row = QHBoxLayout()
        mode_row.addWidget(label("Analisar como", "fieldLabel"))
        self.source_mode = QComboBox()
        self.source_mode.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.source_mode.setMinimumContentsLength(12)
        self.source_mode.addItem("Mídia individual (padrão)", "single")
        self.source_mode.addItem("Playlist — selecionar itens", "playlist")
        self.source_mode.currentIndexChanged.connect(self._mode_changed)
        mode_row.addWidget(self.source_mode, 1)
        source.addLayout(mode_row)
        self.playlist_hint = label("O link contém vídeo e playlist. O padrão analisa só o vídeo; escolha Playlist para abrir a lista.", "muted")
        self.playlist_hint.setWordWrap(True)
        self.playlist_hint.hide()
        source.addWidget(self.playlist_hint)
        self.playlist_panel = PlaylistPanel()
        self.playlist_panel.page_requested.connect(self._request_playlist_page)
        self.playlist_panel.selection_changed.connect(self._update_controls)
        self.playlist_panel.cancel_group.connect(self.queue.cancel_group)
        layout.addWidget(self.playlist_panel)

        media = card()
        media.addWidget(label("CONFIGURE SEU DOWNLOAD", "sectionLabel"))
        self.title_label = label("Título: —", "mediaTitle")
        self.duration_label = label("Duração: —", "muted")
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        media.addWidget(self.title_label)
        media.addWidget(self.duration_label)
        fmt_layout = QHBoxLayout()
        fmt_layout.setSpacing(14)
        self.format_combo = QComboBox()
        self.format_combo.setAccessibleName("Formato de saída")
        self.format_combo.addItems(["MP4", "MP3"])
        self.format_combo.currentTextChanged.connect(self._update_qualities)
        self.quality_combo = QComboBox()
        self.quality_combo.setAccessibleName("Qualidade da fonte")
        self.quality_combo.setMinimumWidth(210)
        for text, widget, stretch in (("Formato", self.format_combo, 1),
                                      ("Qualidade da fonte", self.quality_combo, 3)):
            column = QVBoxLayout()
            column.setSpacing(5)
            caption = label(text, "fieldLabel")
            caption.setBuddy(widget)
            column.addWidget(caption)
            column.addWidget(widget)
            fmt_layout.addLayout(column, stretch)
        media.addLayout(fmt_layout)
        self.quality_note = label("Melhor fonte por padrão. Conversão não aumenta a qualidade original.", "muted")
        self.quality_note.setWordWrap(True)
        media.addWidget(self.quality_note)
        media.addWidget(label("Salvar em", "fieldLabel"))
        dest_layout = QHBoxLayout()
        self.dest_edit = QLineEdit(str(Path.home() / "Downloads"))
        self.dest_edit.setAccessibleName("Pasta de destino")
        self.dest_edit.setPlaceholderText("Pasta de destino")
        self.dest_edit.textChanged.connect(self._update_controls)
        self.dest_btn = QPushButton("Escolher…")
        self.dest_btn.clicked.connect(self.choose_dest)
        dest_layout.addWidget(self.dest_edit)
        dest_layout.addWidget(self.dest_btn)
        media.addLayout(dest_layout)

        buttons = QHBoxLayout()
        self.download_btn = QPushButton("↓  Baixar MP4")
        self.download_btn.setObjectName("downloadButton")
        self.download_btn.setAccessibleName("Baixar mídia")
        self.download_btn.setMinimumHeight(64)
        self.download_btn.setMinimumWidth(300)
        self.download_btn.setMaximumWidth(500)
        self.download_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.download_btn.clicked.connect(self.start_download)
        buttons.addStretch(1)
        buttons.addWidget(self.download_btn, 4)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setObjectName("cancelButton")
        self.cancel_btn.setToolTip("Cancelar a operação atual e qualquer análise pendente.")
        self.cancel_btn.clicked.connect(self.cancel_operation)
        layout.addWidget(self.cancel_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        progress_header = QHBoxLayout()
        self.phase_label = label("AGUARDANDO LINK", "phase")
        self.progress_caption = label("0%", "progressCaption")
        progress_header.addWidget(self.phase_label)
        progress_header.addStretch()
        progress_header.addWidget(self.progress_caption)
        layout.addLayout(progress_header)
        self.progress = QProgressBar()
        self.progress.setAccessibleName("Progresso do download")
        self.progress.setTextVisible(False)
        self.progress.setValue(0)
        self.progress.valueChanged.connect(self._update_progress_caption)
        layout.addWidget(self.progress)
        self.status_label = label("Cole um link para começar. A melhor qualidade será selecionada.", "statusMessage")
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status_label)
        layout.addStretch()
        self.setTabOrder(self.url_edit, self.analyze_btn)
        self.setTabOrder(self.analyze_btn, self.format_combo)
        self.setTabOrder(self.format_combo, self.quality_combo)
        self.setTabOrder(self.quality_combo, self.dest_edit)
        self.setTabOrder(self.dest_edit, self.dest_btn)
        self.setTabOrder(self.dest_btn, self.download_btn)
        self.setTabOrder(self.download_btn, self.cancel_btn)
        self.url_edit.setFocus()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "content_layout"):
            self.content_layout.setDirection(QBoxLayout.Direction.LeftToRight if self.width() >= 1000
                                             else QBoxLayout.Direction.TopToBottom)

    def _set_status(self, message, tone="info"):
        self.status_label.setText(message)
        set_style_property(self.status_label, "tone", tone)

    @Slot()
    def _update_progress_caption(self):
        self.progress_caption.setText("EM ANDAMENTO" if self.progress.maximum() == 0
                                      else f"{max(0, self.progress.value())}%")

    @property
    def busy(self):
        return self.analysis_thread is not None or self.queue.busy

    def _update_controls(self):
        editable = not (self._closing or self._resetting)
        idle = self.analysis_thread is None and editable
        self.analyze_btn.setEnabled(idle)
        self.format_combo.setEnabled(idle)
        for widget in (self.url_edit, self.dest_edit, self.dest_btn):
            widget.setEnabled(editable)
        self.add_link_btn.setEnabled(editable and bool(self.dest_edit.text().strip()))
        self.source_mode.setEnabled(editable)
        self.quality_combo.setEnabled(idle and self.quality_combo.count() > 0)
        self.download_btn.setEnabled(idle and self.media_info is not None
                                     and self.analyzed_url == self.url_edit.text().strip()
                                     and bool(self.dest_edit.text().strip())
                                     and self.quality_combo.count() > 0
                                     and (self.media_info.get("_type") != "playlist"
                                          or bool(self.playlist_panel.selected)))
        self.cancel_btn.setEnabled(editable)
        if self._closing:
            phase, caption = "ENCERRANDO", "Encerrando…"
        elif self._resetting or self._cancelling and self.busy:
            phase, caption = "AGUARDANDO TAREFA ATUAL", "Aguarde…"
        elif self.analysis_in_progress:
            phase, caption = "ANALISANDO FONTE", "Analisando…"
        elif self.analysis_timer.isActive() or self._auto_pending:
            phase, caption = "ANÁLISE AUTOMÁTICA AGENDADA", "Preparando análise…"
        else:
            phase = "PRONTO PARA BAIXAR" if self.download_btn.isEnabled() else "AGUARDANDO CONFIGURAÇÃO"
            caption = (f"+  Adicionar à fila ({len(self.playlist_panel.selected)})"
                       if self.media_info and self.media_info.get("_type") == "playlist"
                       else f"{'+  Adicionar' if self.queue.busy else '↓  Baixar'} {self.format_combo.currentText()}")
            if self.queue.current and not self._form_cleared:
                phase = f"FILA • {STATE_NAMES.get(self.queue.current.state, '')}"
                caption = f"{STATE_NAMES.get(self.queue.current.state, 'Na fila')} · + Adicionar"
            elif self.last_output:
                phase = "DOWNLOAD CONCLUÍDO"
                caption = f"✓ Concluído · Baixar {self.format_combo.currentText()}"
        self.phase_label.setText(phase)
        self.download_btn.setText(caption)
        set_style_property(self.download_btn, "busy", self.analysis_in_progress)
        self._update_progress_caption()

    @Slot()
    def _invalidate_analysis(self):
        self.preview.clear()
        self.playlist_panel.reset()
        self._playlist_pending_offset = None
        self.media_info = None
        self.analyzed_url = None
        self.title_label.setText("Título: —")
        self.duration_label.setText("Duração: —")
        self.quality_combo.clear()
        self._update_controls()

    @Slot(str)
    def _on_url_changed(self, text):
        url = text.strip()
        if url == self._input_url or self._closing:
            return
        self._input_url = url
        if url:
            self._form_cleared = False
        try:
            query = parse_qs(urlsplit(url).query) if url.startswith(("http://", "https://")) else {}
        except ValueError:
            query = {}
        self.playlist_hint.setVisible(bool(query.get("list") and query.get("v")))
        self._url_revision += 1
        self._cancel_requested = False
        self.analysis_timer.stop()
        self._auto_pending = False
        self.last_output = None
        self._invalidate_analysis()
        if self.analysis_worker is not None:
            self._cancelling = True
            self.analysis_worker.cancel()
        if not self.download_in_progress:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
        try:
            validate_url(url)
        except ValueError:
            self._set_status("Cole um link HTTP ou HTTPS completo.")
        else:
            self._set_status("Link detectado. A análise começará automaticamente…")
            self.analysis_timer.start()
        self._update_controls()

    @Slot()
    def _auto_analyze(self):
        if self._closing or self._attempted_revision == self._url_revision:
            return
        self._auto_pending = True
        self._run_pending_analysis()

    @Slot()
    def _run_pending_analysis(self):
        if self._closing or not self._auto_pending:
            return
        if self.analysis_thread is not None:
            self._set_status("Novo link pronto. Aguardando a análise anterior encerrar…")
            self._update_controls()
            return
        self._auto_pending = False
        if self._attempted_revision != self._url_revision:
            self.analyze_url()

    @Slot()
    def _update_qualities(self):
        self._format_edited = True
        self.quality_combo.clear()
        if self.media_info is not None:
            choices = self.ydl.quality_choices(self.media_info, self.format_combo.currentText())
            for label, value in choices:
                self.quality_combo.addItem(label, value)
        self._update_controls()

    def _start_worker(self, kind, worker):
        thread = QThread(self)
        setattr(self, f"{kind}_thread", thread)
        setattr(self, f"{kind}_worker", worker)
        setattr(self, f"{kind}_in_progress", True)
        self._cancelling = False
        self._cancel_requested = False
        worker.moveToThread(thread)
        if kind == "analysis":
            worker.status.connect(self._on_analysis_status, Qt.ConnectionType.QueuedConnection)
            worker.error.connect(self._on_analysis_error, Qt.ConnectionType.QueuedConnection)
            worker.cancelled.connect(self._on_analysis_cancelled, Qt.ConnectionType.QueuedConnection)
        else:
            worker.status.connect(self._on_status, Qt.ConnectionType.QueuedConnection)
            worker.error.connect(self._on_error, Qt.ConnectionType.QueuedConnection)
            worker.cancelled.connect(self._on_cancelled, Qt.ConnectionType.QueuedConnection)
        # The GUI event loop remains alive during close/cancel. Queue quit to
        # the QThread owner and delete the worker at the thread's finish boundary.
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.started.connect(worker.run)
        if kind == "analysis":
            thread.finished.connect(self._analysis_stopped, Qt.ConnectionType.QueuedConnection)
        else:
            thread.finished.connect(self._download_stopped, Qt.ConnectionType.QueuedConnection)
        self._update_controls()
        thread.start()

    @Slot()
    def analyze_url(self):
        if self.analysis_thread is not None or self._closing:
            return
        self.analysis_timer.stop()
        self._auto_pending = False
        self._attempted_revision = self._url_revision
        url = self.url_edit.text().strip()
        self._invalidate_analysis()
        try:
            validate_url(url)
        except ValueError as exc:
            self._on_error(str(exc))
            return
        self.analyzed_url = url
        self._analysis_revision = self._url_revision
        self._request_serial += 1
        self._active_request_id = self._request_serial
        self.last_output = None
        self.progress.setRange(0, 0)
        self._set_status("Analisando URL…")
        worker = AnalysisWorker(self.ydl, url, self._active_request_id,
                                mode=self.source_mode.currentData())
        worker.info_received.connect(self._on_analysis_info, Qt.ConnectionType.QueuedConnection)
        self._start_worker("analysis", worker)

    def _current_analysis(self, request_id):
        return (request_id == self._active_request_id
                and self._url_revision == self._analysis_revision
                and not self._closing)

    @Slot(int, str)
    def _on_analysis_status(self, request_id, message):
        if self._current_analysis(request_id):
            self._on_status(message)

    @Slot(int, str)
    def _on_analysis_error(self, request_id, message):
        if self._current_analysis(request_id):
            self.playlist_panel.loading_failed()
            self._on_error(message)

    @Slot(int)
    def _on_analysis_cancelled(self, request_id):
        if self._current_analysis(request_id):
            self.playlist_panel.loading_failed()
            self._on_cancelled()

    @Slot(int, dict)
    def _on_analysis_info(self, request_id, info):
        if not self._current_analysis(request_id) or self._cancelling:
            return
        previous_quality = self.quality_combo.currentData() if info.get("offset", 0) else None
        self.media_info = info
        self.preview.show_info(info)
        if info.get("_type") == "playlist":
            self.playlist_panel.set_page(info)
        self.title_label.setText(f"Título: {info.get('title') or 'Não informado'}")
        duration = info.get("duration")
        if duration is not None:
            hours, rest = divmod(max(0, int(duration)), 3600)
            mins, secs = divmod(rest, 60)
            self.duration_label.setText(f"Duração: {hours:02}:{mins:02}:{secs:02}")
        else:
            self.duration_label.setText("Duração: não informada pela fonte")
        self._update_qualities()
        if previous_quality is not None:
            self.quality_combo.setCurrentIndex(max(0, self.quality_combo.findData(previous_quality)))
        if not self.quality_combo.count() and self.format_combo.currentText() == "MP4":
            self.format_combo.setCurrentText("MP3")
        self._set_status("Selecione os itens da playlist para adicionar à fila."
                         if info.get("_type") == "playlist" else
                         "Análise concluída. Selecione formato, qualidade e destino."
                         if self.quality_combo.count() else "Nenhum formato disponível.")

    @Slot()
    def _mode_changed(self):
        self._input_url = ""
        self._on_url_changed(self.url_edit.text())

    @Slot(int)
    def _request_playlist_page(self, offset):
        if offset < 0:
            self._playlist_pending_offset = None
            if self.analysis_worker:
                self._cancelling = True
                self.analysis_worker.cancel()
            self.playlist_panel.loading_failed()
            return
        if self.analysis_thread:
            self._playlist_pending_offset = offset
            return
        if self._closing or not self.playlist_panel.source:
            return
        self._request_serial += 1
        self._active_request_id = self._request_serial
        self._analysis_revision = self._url_revision
        worker = AnalysisWorker(self.ydl, self.playlist_panel.source, self._active_request_id,
                                mode="playlist", offset=offset)
        worker.info_received.connect(self._on_analysis_info, Qt.ConnectionType.QueuedConnection)
        self._start_worker("analysis", worker)

    @Slot()
    def choose_dest(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecione a pasta", self.dest_edit.text())
        if folder:
            self.dest_edit.setText(folder)

    @Slot()
    def start_download(self):
        if self.analysis_thread is not None or self._closing:
            return
        if self.media_info is None or self.analyzed_url != self.url_edit.text().strip():
            self._on_error("Analise a URL antes de baixar.")
            return
        destination = self.dest_edit.text().strip()
        if not destination:
            self._on_error("Selecione uma pasta de destino.")
            return
        try:
            container = self.format_combo.currentText()
            quality = self.quality_combo.currentData()
            text = self.quality_combo.currentText()
            if self.media_info.get("_type") == "playlist":
                items = [QueueItem(entry["url"], destination, container, quality, text,
                                   entry["title"], entry.get("thumbnail") or "",
                                   group=self.playlist_panel.source)
                         for entry in self.playlist_panel.selected.values()]
            else:
                format_id, postprocessors = self.ydl.download_selection(
                    self.media_info, container, quality)
                items = [QueueItem(self.analyzed_url, destination, container, quality, text,
                                   self.media_info.get("title") or self.analyzed_url,
                                   self.media_info.get("thumbnail") or "", format_id=format_id,
                                   postprocessors=postprocessors)]
        except (ValueError, OSError) as exc:
            self._on_error(str(exc))
            return
        self.last_output = None
        added = self.queue.add(items)
        self._set_status(f"{len(added)} item(ns) adicionado(s) à fila."
                         if added else "Nenhum item novo: selecione itens ou verifique duplicatas na fila.")
        self._update_controls()

    @Slot()
    def add_links_dialog(self):
        text, ok = QInputDialog.getMultiLineText(
            self, "Adicionar links", "Um link de mídia por linha. Formato atual; melhor qualidade por item.\n"
            "Para selecionar uma playlist, use o campo principal e o modo Playlist.")
        if ok:
            self.add_urls(text.splitlines())

    def add_urls(self, urls):
        if self._closing or not self.dest_edit.text().strip():
            return []
        items = []
        invalid = 0
        for url in urls:
            url = url.strip()
            if not url:
                continue
            try:
                validate_url(url)
            except ValueError:
                invalid += 1
                continue
            items.append(QueueItem(url, self.dest_edit.text().strip(),
                                   self.format_combo.currentText(), title=url))
        added = self.queue.add(items)
        self._set_status(f"{len(added)} links adicionados; {invalid} inválidos.")
        self.tabs.setCurrentWidget(self.queue_panel)
        return added

    @Slot()
    def _queue_changed(self):
        if self.queue.current:
            self.last_output = None
        self.download_thread = self.queue.thread
        self.download_worker = self.queue.worker
        self.download_in_progress = self.queue.busy
        self.tabs.setTabText(1, f"Fila ({len(self.queue.items)})")
        self._update_controls()
        if self._closing and not self.busy:
            QTimer.singleShot(0, self, self.close)

    @Slot(str)
    def _queue_item_changed(self, item_id):
        item = self.queue.get(item_id)
        if item is self.queue.current and not (self.analysis_in_progress or self._resetting or self._form_cleared):
            self._on_progress(item.progress)
            if item.state == "failed":
                self._on_error(item.error)
            else:
                self._on_status(f"{STATE_NAMES.get(item.state, item.state)}: {item.title}")
        self._update_controls()

    @Slot(str)
    def _queue_finished(self, item_id):
        if self._resetting:
            if self._reset_item == item_id:
                self._reset_item = None
            self._finish_reset()
            return
        if self._form_cleared:
            return
        item = self.queue.get(item_id)
        if item and item.state == "completed":
            self.last_output = item.path
            if not self.analysis_in_progress:
                self._on_download_completed(item.path)

    @Slot(str, object)
    def _history_result(self, kind, data):
        if kind == "restore":
            fields = QueueItem.__dataclass_fields__
            existing = {item.id for item in self.queue.items}
            for record in data:
                if record["id"] not in existing:
                    self.queue.items.append(QueueItem(**{k: v for k, v in record.items() if k in fields}))
            self.queue.structure_changed.emit()
        elif kind == "settings":
            if (not self.dest_edit.isModified()
                    and self.dest_edit.text() == str(Path.home() / "Downloads")
                    and data.get("destination")):
                self.dest_edit.setText(data["destination"])
            if (not self._format_edited and data.get("container") in ("MP4", "MP3")
                    and self.media_info is None):
                self.format_combo.setCurrentText(data["container"])

    @Slot(str)
    def _history_error(self, message):
        self._set_status(message, "error")

    @Slot()
    def _history_closed(self):
        if self._closing:
            QTimer.singleShot(0, self, self.close)

    @Slot(int)
    def _on_progress(self, value):
        if self._closing or self._cancelling:
            return
        self.progress.setRange(0, 0 if value < 0 else 100)
        if value >= 0:
            self.progress.setValue(value)
        self._update_progress_caption()

    @Slot(str)
    def _on_download_completed(self, path):
        if not self._closing and not self._cancelling:
            self.last_output = path
            self._set_status(f"Concluído: {path}", "success")

    @Slot(str)
    def _on_status(self, message):
        if not self._closing and not self._cancelling:
            self._set_status(message)

    @Slot(str)
    def _on_error(self, message):
        if not self._closing and not self._cancelling:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self._set_status(f"Erro: {message}", "error")
            self._update_progress_caption()

    @Slot()
    def _on_cancelled(self):
        if not self._closing:
            self._set_status("Operação cancelada. Arquivos parciais podem ser retomados.")

    def _stopped(self, kind):
        thread = getattr(self, f"{kind}_thread")
        # Qt emits finished before native thread-local cleanup completes.
        # Retain both Python wrappers until that cleanup has actually ended.
        # wait(0) is a NON-BLOCKING probe; never wait for network/FFmpeg here.
        if not thread.wait(0):
            QTimer.singleShot(10, self, self._analysis_stopped if kind == "analysis"
                              else self._download_stopped)
            return
        thread.deleteLater()
        setattr(self, f"{kind}_worker", None)
        setattr(self, f"{kind}_thread", None)
        setattr(self, f"{kind}_in_progress", False)
        if kind == "analysis":
            self._active_request_id = None
        if self._cancel_requested:
            self._on_cancelled()
        self._cancel_requested = False
        self._cancelling = False
        if self._resetting:
            self._finish_reset()
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
        self._update_controls()
        if self._closing and not self.busy:
            QTimer.singleShot(0, self, self.close)
        elif self._auto_pending:
            QTimer.singleShot(0, self, self._run_pending_analysis)
        elif self._playlist_pending_offset is not None:
            offset = self._playlist_pending_offset
            self._playlist_pending_offset = None
            QTimer.singleShot(0, self, lambda: self._request_playlist_page(offset))

    @Slot()
    def _analysis_stopped(self):
        self._stopped("analysis")

    @Slot()
    def _download_stopped(self):
        self._stopped("download")

    @Slot()
    def cancel_operation(self):
        if self._closing or self._resetting:
            return
        self._resetting = True
        self.analysis_timer.stop()
        self._auto_pending = False
        self._attempted_revision = self._url_revision
        self._playlist_pending_offset = None
        self.playlist_panel.auto_all = False
        self._cancel_requested = bool(self.analysis_in_progress)
        self._cancelling = bool(self.analysis_in_progress)
        self._active_request_id = None
        if self.analysis_worker:
            self.analysis_worker.cancel()
        current = self.queue.current
        self._reset_item = current.id if current else None
        if current:
            self.queue.cancel(current.id)
        self._set_status("Cancelando… aguardando o encerramento da tarefa.")
        self._finish_reset()
        self._update_controls()

    def _finish_reset(self):
        if self.analysis_thread is not None or self._reset_item is not None:
            return
        self.url_edit.clear()
        self._invalidate_analysis()
        self.last_output = None
        self._resetting = self._cancelling = self._cancel_requested = False
        self._form_cleared = True
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._set_status("Operação cancelada. Cole um novo link.")
        self._update_controls()

    def closeEvent(self, event):
        self._closing = True
        self.analysis_timer.stop()
        self._auto_pending = False
        self._playlist_pending_offset = None
        self.queue.close()
        if self.busy:
            if self.analysis_worker:
                self.analysis_worker.cancel()
            self._set_status("Encerrando com segurança… aguardando rede/FFmpeg.")
            event.ignore()
        else:
            self.thumbnails.close()
            if not self.history.is_closed:
                self.history.save_settings({"destination": self.dest_edit.text().strip(),
                                            "container": self.format_combo.currentText()})
                self.history.close()
                event.ignore()
            else:
                event.accept()
