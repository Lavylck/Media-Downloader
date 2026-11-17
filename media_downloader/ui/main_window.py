from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, Slot
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from ..downloader.yt_dlp_wrapper import YtDlpWrapper, validate_url
from .analysis_worker import AnalysisWorker
from .download_worker import DownloadWorker
from .theme import apply_theme, set_style_property


class MainWindow(QMainWindow):
    def __init__(self, ydl_wrapper=None, *, analysis_debounce_ms=600):
        super().__init__()
        self.setWindowTitle("Media Downloader · Neon V2")
        self.setMinimumSize(620, 520)
        self.resize(840, min(790, self.screen().availableGeometry().height() - 70))
        self.ydl = ydl_wrapper or YtDlpWrapper()
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
        self.analysis_timer = QTimer(self)
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.setInterval(analysis_debounce_ms)
        self.analysis_timer.timeout.connect(self._auto_analyze)
        self.init_ui()
        apply_theme(self)
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
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCentralWidget(scroll)
        central = QWidget()
        central.setObjectName("appSurface")
        scroll.setWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(14)
        header = QHBoxLayout()
        mark = label("MD", "brandMark")
        mark.setFixedSize(50, 50)
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
        header.addWidget(label("NEON / V2", "edition"))
        layout.addLayout(header)

        source = card()
        source.addWidget(label("01 / LINK DA MÍDIA", "sectionLabel"))
        url_layout = QHBoxLayout()
        url_layout.setSpacing(10)
        self.url_edit = QLineEdit()
        self.url_edit.setObjectName("urlInput")
        self.url_edit.setAccessibleName("URL da mídia")
        self.url_edit.setPlaceholderText("Cole seu link aqui…")
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.setMinimumHeight(44)
        self.url_edit.textChanged.connect(self._on_url_changed)
        self.url_edit.returnPressed.connect(self.analyze_url)
        self.analyze_btn = QPushButton("Analisar")
        self.analyze_btn.setMinimumHeight(44)
        self.analyze_btn.setToolTip("Analisar novamente, mesmo se o link não mudou (Enter).")
        self.analyze_btn.clicked.connect(self.analyze_url)
        url_layout.addWidget(self.url_edit, 1)
        url_layout.addWidget(self.analyze_btn)
        source.addLayout(url_layout)
        source_note = label("Análise automática ao colar ou pausar a digitação. Enter para antecipar.", "muted")
        source_note.setWordWrap(True)
        source.addWidget(source_note)

        media = card()
        media.addWidget(label("02 / CONFIGURE SEU DOWNLOAD", "sectionLabel"))
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

    def _set_status(self, message, tone="info"):
        self.status_label.setText(message)
        set_style_property(self.status_label, "tone", tone)

    @Slot()
    def _update_progress_caption(self):
        self.progress_caption.setText("EM ANDAMENTO" if self.progress.maximum() == 0
                                      else f"{max(0, self.progress.value())}%")

    @property
    def busy(self):
        # Keep operations exclusive until QThread.finished, not worker.finished.
        return self.analysis_thread is not None or self.download_thread is not None

    def _update_controls(self):
        idle = not self.busy and not self._closing
        self.analyze_btn.setEnabled(idle)
        self.format_combo.setEnabled(idle)
        for widget in (self.url_edit, self.dest_edit, self.dest_btn):
            widget.setEnabled(not self.download_in_progress and not self._closing)
        self.quality_combo.setEnabled(idle and self.quality_combo.count() > 0)
        self.download_btn.setEnabled(idle and self.media_info is not None
                                     and self.analyzed_url == self.url_edit.text().strip()
                                     and bool(self.dest_edit.text().strip())
                                     and self.quality_combo.count() > 0)
        self.cancel_btn.setEnabled(not self._closing and (
            (self.busy and not self._cancelling) or self.analysis_timer.isActive()
            or self._auto_pending))
        if self._closing:
            phase, caption = "ENCERRANDO", "Encerrando…"
        elif self._cancelling and self.busy:
            phase, caption = "AGUARDANDO TAREFA ATUAL", "Aguarde…"
        elif self.download_in_progress:
            phase, caption = "DOWNLOAD / PROCESSAMENTO", "Baixando…"
        elif self.analysis_in_progress:
            phase, caption = "ANALISANDO FONTE", "Analisando…"
        elif self.analysis_timer.isActive() or self._auto_pending:
            phase, caption = "ANÁLISE AUTOMÁTICA AGENDADA", "Preparando análise…"
        else:
            phase = "PRONTO PARA BAIXAR" if self.download_btn.isEnabled() else "AGUARDANDO CONFIGURAÇÃO"
            caption = f"↓  Baixar {self.format_combo.currentText()}"
        self.phase_label.setText(phase)
        self.download_btn.setText(caption)
        set_style_property(self.download_btn, "busy", self.busy)
        self._update_progress_caption()

    @Slot()
    def _invalidate_analysis(self):
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
        if self.busy:
            self._set_status("Novo link pronto. Aguardando a análise anterior encerrar…")
            self._update_controls()
            return
        self._auto_pending = False
        if self._attempted_revision != self._url_revision:
            self.analyze_url()

    @Slot()
    def _update_qualities(self):
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
        if self.busy or self._closing:
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
        worker = AnalysisWorker(self.ydl, url, self._active_request_id)
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
            self._on_error(message)

    @Slot(int)
    def _on_analysis_cancelled(self, request_id):
        if self._current_analysis(request_id):
            self._on_cancelled()

    @Slot(int, dict)
    def _on_analysis_info(self, request_id, info):
        if not self._current_analysis(request_id) or self._cancelling:
            return
        self.media_info = info
        self.title_label.setText(f"Título: {info.get('title') or 'Não informado'}")
        duration = info.get("duration")
        if duration is not None:
            hours, rest = divmod(max(0, int(duration)), 3600)
            mins, secs = divmod(rest, 60)
            self.duration_label.setText(f"Duração: {hours:02}:{mins:02}:{secs:02}")
        else:
            self.duration_label.setText("Duração: não informada pela fonte")
        self._update_qualities()
        if not self.quality_combo.count() and self.format_combo.currentText() == "MP4":
            self.format_combo.setCurrentText("MP3")
        self._set_status("Análise concluída. Selecione formato, qualidade e destino."
                         if self.quality_combo.count() else "Nenhum formato disponível.")

    @Slot()
    def choose_dest(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecione a pasta", self.dest_edit.text())
        if folder:
            self.dest_edit.setText(folder)

    @Slot()
    def start_download(self):
        if self.busy or self._closing:
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
            format_id, postprocessors = self.ydl.download_selection(
                self.media_info, container, quality)
            outtmpl = self.ydl.output_template(destination, container, quality)
        except (ValueError, OSError) as exc:
            self._on_error(str(exc))
            return
        self.last_output = None
        self.progress.setRange(0, 0)
        self._set_status("Iniciando download…")
        worker = DownloadWorker(self.ydl, self.analyzed_url, format_id, outtmpl, postprocessors)
        worker.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        worker.completed.connect(self._on_download_completed, Qt.ConnectionType.QueuedConnection)
        self._start_worker("download", worker)

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
            QTimer.singleShot(10, self._analysis_stopped if kind == "analysis"
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
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
        self._update_controls()
        if self._closing and not self.busy:
            QTimer.singleShot(0, self.close)
        elif self._auto_pending:
            QTimer.singleShot(0, self._run_pending_analysis)

    @Slot()
    def _analysis_stopped(self):
        self._stopped("analysis")

    @Slot()
    def _download_stopped(self):
        self._stopped("download")

    @Slot()
    def cancel_operation(self):
        self.analysis_timer.stop()
        self._auto_pending = False
        self._attempted_revision = self._url_revision
        self._cancel_requested = True
        self._cancelling = True
        if self.analysis_in_progress:
            self._invalidate_analysis()
        for worker in (self.analysis_worker, self.download_worker):
            if worker is not None:
                worker.cancel()
        self._set_status("Cancelando… aguardando a etapa de rede/FFmpeg terminar."
                         if self.busy else "Análise automática cancelada. Use Analisar para tentar novamente.")
        if not self.busy:
            self._cancelling = False
        self._update_controls()

    def closeEvent(self, event):
        self._closing = True
        self.analysis_timer.stop()
        self._auto_pending = False
        if self.busy:
            self.cancel_operation()
            self._set_status("Encerrando com segurança… aguardando rede/FFmpeg.")
            event.ignore()
        else:
            event.accept()
