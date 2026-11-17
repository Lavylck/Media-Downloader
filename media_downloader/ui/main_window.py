from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, Slot
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from ..downloader.yt_dlp_wrapper import YtDlpWrapper, validate_url
from .analysis_worker import AnalysisWorker
from .download_worker import DownloadWorker


class MainWindow(QMainWindow):
    def __init__(self, ydl_wrapper=None):
        super().__init__()
        self.setWindowTitle("Media Downloader V1")
        self.resize(720, 440)
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
        self.init_ui()
        self._update_controls()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        url_layout = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("URL da mídia (HTTP ou HTTPS)")
        self.url_edit.textChanged.connect(self._invalidate_analysis)
        self.url_edit.returnPressed.connect(self.analyze_url)
        self.analyze_btn = QPushButton("Analisar")
        self.analyze_btn.clicked.connect(self.analyze_url)
        url_layout.addWidget(self.url_edit)
        url_layout.addWidget(self.analyze_btn)
        layout.addLayout(url_layout)
        self.title_label = QLabel("Título: —")
        self.duration_label = QLabel("Duração: —")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.duration_label)
        fmt_layout = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4", "MP3"])
        self.format_combo.currentTextChanged.connect(self._update_qualities)
        self.quality_combo = QComboBox()
        fmt_layout.addWidget(QLabel("Formato:"))
        fmt_layout.addWidget(self.format_combo)
        fmt_layout.addWidget(QLabel("Qualidade da fonte:"))
        fmt_layout.addWidget(self.quality_combo, 1)
        layout.addLayout(fmt_layout)
        self.quality_note = QLabel("Conversão não aumenta a qualidade original.")
        layout.addWidget(self.quality_note)
        dest_layout = QHBoxLayout()
        self.dest_edit = QLineEdit(str(Path.home() / "Downloads"))
        self.dest_edit.setPlaceholderText("Pasta de destino")
        self.dest_btn = QPushButton("Escolher…")
        self.dest_btn.clicked.connect(self.choose_dest)
        dest_layout.addWidget(self.dest_edit)
        dest_layout.addWidget(self.dest_btn)
        layout.addLayout(dest_layout)
        buttons = QHBoxLayout()
        self.download_btn = QPushButton("Baixar")
        self.download_btn.clicked.connect(self.start_download)
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self.cancel_operation)
        buttons.addWidget(self.download_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.status_label = QLabel("Informe uma URL e clique em Analisar.")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status_label)
        for label in (self.title_label, self.duration_label, self.status_label):
            label.setTextFormat(Qt.TextFormat.PlainText)

    @property
    def busy(self):
        # Keep operations exclusive until QThread.finished, not worker.finished.
        return self.analysis_thread is not None or self.download_thread is not None

    def _update_controls(self):
        idle = not self.busy and not self._closing
        self.analyze_btn.setEnabled(idle)
        for widget in (self.url_edit, self.format_combo, self.dest_edit, self.dest_btn):
            widget.setEnabled(idle)
        self.quality_combo.setEnabled(idle and self.quality_combo.count() > 0)
        self.download_btn.setEnabled(idle and self.media_info is not None
                                     and self.quality_combo.count() > 0)
        self.cancel_btn.setEnabled(self.busy and not self._cancelling and not self._closing)

    @Slot()
    def _invalidate_analysis(self):
        self.media_info = None
        self.analyzed_url = None
        self.title_label.setText("Título: —")
        self.duration_label.setText("Duração: —")
        self.quality_combo.clear()
        self._update_controls()

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
        worker.moveToThread(thread)
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
        url = self.url_edit.text().strip()
        self._invalidate_analysis()
        try:
            validate_url(url)
        except ValueError as exc:
            self._on_error(str(exc))
            return
        self.analyzed_url = url
        self.last_output = None
        self.progress.setRange(0, 0)
        self.status_label.setText("Analisando URL…")
        worker = AnalysisWorker(self.ydl, url)
        worker.info_received.connect(self._on_analysis_info, Qt.ConnectionType.QueuedConnection)
        self._start_worker("analysis", worker)

    @Slot(dict)
    def _on_analysis_info(self, info):
        if self._closing or self._cancelling:
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
        self.status_label.setText("Análise concluída. Selecione formato, qualidade e destino."
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
        self.status_label.setText("Iniciando download…")
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

    @Slot(str)
    def _on_download_completed(self, path):
        if not self._closing and not self._cancelling:
            self.last_output = path
            self.status_label.setText(f"Concluído: {path}")

    @Slot(str)
    def _on_status(self, message):
        if not self._closing and not self._cancelling:
            self.status_label.setText(message)

    @Slot(str)
    def _on_error(self, message):
        if not self._closing and not self._cancelling:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.status_label.setText(f"Erro: {message}")

    @Slot()
    def _on_cancelled(self):
        if not self._closing:
            self.status_label.setText("Operação cancelada. Arquivos parciais podem ser retomados.")

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
        self._cancelling = False
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
        self._update_controls()
        if self._closing and not self.busy:
            QTimer.singleShot(0, self.close)

    @Slot()
    def _analysis_stopped(self):
        self._stopped("analysis")

    @Slot()
    def _download_stopped(self):
        self._stopped("download")

    @Slot()
    def cancel_operation(self):
        self._cancelling = True
        for worker in (self.analysis_worker, self.download_worker):
            if worker is not None:
                worker.cancel()
        self.status_label.setText("Cancelando… aguardando a etapa de rede/FFmpeg terminar.")
        self._update_controls()

    def closeEvent(self, event):
        if self.busy:
            self._closing = True
            self.cancel_operation()
            self.status_label.setText("Encerrando com segurança… aguardando rede/FFmpeg.")
            event.ignore()
        else:
            event.accept()
