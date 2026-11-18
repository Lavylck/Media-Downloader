import sys
import argparse
import ctypes
from PySide6.QtCore import QCoreApplication, QEvent, QLockFile
from PySide6.QtWidgets import QApplication, QMessageBox
from media_downloader.ui.main_window import MainWindow
from media_downloader.logging_setup import configure_logging
from media_downloader.paths import data_dir
from media_downloader.resources import app_icon


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-report")
    parser.add_argument("--smoke-url")
    parser.add_argument("--smoke-playlist", action="store_true")
    parser.add_argument("--smoke-history", action="store_true")
    args = parser.parse_args()
    logger = configure_logging()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Media Downloader")
    app.setOrganizationName("MediaDownloader")
    app.setWindowIcon(app_icon())
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MediaDownloader.Cyberpunk.3")
    lock = QLockFile(str(data_dir() / "application.lock"))
    if not lock.tryLock(0):
        if not args.smoke_report:
            QMessageBox.information(None, "Media Downloader", "O aplicativo já está aberto para este usuário.")
        return 1
    def exception_hook(kind, value, traceback):
        logger.error("Exceção não tratada", exc_info=(kind, value, traceback))
        app.exit(2)
    sys.excepthook = exception_hook
    win = MainWindow()
    win.show()
    logger.info("Aplicativo iniciado")
    smoke = None
    if args.smoke_report:
        from media_downloader.smoke import SmokeRun
        smoke = SmokeRun(win, args.smoke_report, args.smoke_url,
                         args.smoke_history, args.smoke_playlist)
    result = app.exec()
    if smoke and not smoke.report["success"]:
        result = 2
    win.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    lock.unlock()
    logger.info("Aplicativo encerrado")
    return result


if __name__ == "__main__":
    sys.exit(main())
