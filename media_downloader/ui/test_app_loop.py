import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

app = QApplication(sys.argv)
print("App started")
QCoreApplication.processEvents()
print("Events processed")
sys.exit(0)
