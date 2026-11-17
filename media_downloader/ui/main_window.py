import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QComboBox, QProgressBar, QFileDialog,
    QMessageBox
)
from PySide6.QtCore import Slot, Qt, QThread
from ..downloader.yt_dlp_wrapper import YtDlpWrapper
from .download_worker import DownloadWorker
from .analysis_worker import AnalysisWorker
import os

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        print("MainWindow initialized")
        self.setWindowTitle("Media Downloader (MVP)")
        self.resize(600, 400)
        self.ydl = YtDlpWrapper()
        self.init_ui()
        self.download_in_progress = False
        self.analysis_in_progress = False

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout()
        central.setLayout(layout)

        # URL input
        url_layout = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Enter video URL")
        self.analyze_btn = QPushButton("Analisar")
        self.analyze_btn.clicked.connect(self.analyze_url)
        url_layout.addWidget(self.url_edit)
        url_layout.addWidget(self.analyze_btn)
        layout.addLayout(url_layout)

        # Video info labels
        self.title_label = QLabel("Título: ")
        self.duration_label = QLabel("Duração: ")
        layout.addWidget(self.title_label)
        layout.addWidget(self.duration_label)

        # Format and quality selection
        fmt_layout = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP4", "MP3"])
        fmt_layout.addWidget(QLabel("Formato: "))
        fmt_layout.addWidget(self.format_combo)
        layout.addLayout(fmt_layout)

        # Destination selection
        dest_layout = QHBoxLayout()
        self.dest_edit = QLineEdit()
        self.dest_edit.setPlaceholderText("Select destination folder")
        self.dest_btn = QPushButton("Escolher...")
        self.dest_btn.clicked.connect(self.choose_dest)
        dest_layout.addWidget(self.dest_edit)
        dest_layout.addWidget(self.dest_btn)
        layout.addLayout(dest_layout)

        # Download button
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.start_download)
        layout.addWidget(self.download_btn)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

    @Slot()
    def analyze_url(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Erro", "Informe uma URL válida.")
            return
        
        if self.analysis_in_progress:
            return

        self.analysis_in_progress = True
        self.analyze_btn.setEnabled(False)
        self.progress.setValue(0)
        
        self.analysis_thread = QThread()
        self.analysis_worker = AnalysisWorker(self.ydl, url)
        self.analysis_worker.moveToThread(self.analysis_thread)
        
        self.analysis_worker.info_received.connect(self._on_analysis_info)
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.error.connect(self._on_analysis_error)
        
        self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_thread.start()

    def _on_analysis_info(self, info):
        self.title_label.setText(f"Título: {info.get('title', 'N/A')}")
        duration = info.get('duration')
        if duration:
            mins, secs = divmod(duration, 60)
            self.duration_label.setText(f"Duração: {mins}m {secs}s")
        else:
            self.duration_label.setText("Duração: N/A")
        
        best_format = self.ydl.select_best_format(info, "best")
        self.best_format = best_format

    def _on_analysis_finished(self, success):
        self.analysis_in_progress = False
        self.analyze_btn.setEnabled(True)
        if not success:
            # Error handled by _on_analysis_error
            pass

    def _on_analysis_error(self, error_msg):
        self.analysis_in_progress = False
        self.analyze_btn.setEnabled(True)
        QMessageBox.critical(self, "Erro", f"Falha ao analisar: {error_msg}")
        
        if hasattr(self, 'analysis_thread') and self.analysis_thread.isRunning():
            self.analysis_thread.quit()
            self.analysis_thread.wait()

    @Slot()
    def choose_dest(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecione a pasta")
        if folder:
            self.dest_edit.setText(folder)

    @Slot()
    def start_download(self):
        if self.download_in_progress:
            QMessageBox.warning(self, "Aviso", "Download já em andamento.")
            return
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Erro", "Informe uma URL válida.")
            return
        dest = self.dest_edit.text().strip()
        if not dest:
            QMessageBox.warning(self, "Erro", "Selecione uma pasta de destino.")
            return
        fmt = self.format_combo.currentText()
        try:
            outtmpl = os.path.join(dest, "%(title)s.%(ext)s")
            format_id = self.best_format.get('format_id')
            
            if fmt == "MP4":
                postprocessors = []
            else:  # MP3
                postprocessors = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
            
            self.download_in_progress = True
            self.progress.setValue(0)
            
            self.thread = QThread()
            self.worker = DownloadWorker(
                self.ydl, url, format_id, outtmpl, postprocessors
            )
            self.worker.moveToThread(self.thread)
            
            self.worker.progress.connect(self.progress.setValue)
            self.worker.finished.connect(self._on_download_finished)
            self.worker.error.connect(self._on_download_error)
            
            self.thread.started.connect(self.worker.run)
            
            self.thread.start()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao iniciar download: {e}")
            self.download_in_progress = False

    def _on_download_finished(self, success):
        self.download_in_progress = False
        if success:
            QMessageBox.information(self, "Pronto", "Download concluído.")
        else:
            pass  # Error is handled by _on_download_error
        
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

    def _on_download_error(self, error_msg):
        self.download_in_progress = False
        QMessageBox.critical(self, "Erro", f"Falha no download: {error_msg}")
        
        # Cleanup thread resources
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

# End of MainWindow
