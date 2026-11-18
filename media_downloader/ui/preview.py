"""Asynchronous Qt networking with a bounded per-user thumbnail disk cache."""

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, QRectF, QSize, Qt, QUrl, Signal, QVariantAnimation
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter, QPainterPath, QPen
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkDiskCache, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..paths import data_dir
from ..history import persistent_url


class ThumbnailService(QObject):
    ready = Signal(str, QImage)
    failed = Signal(str)
    MAX_BYTES = 8 * 1024 * 1024

    def __init__(self, parent=None, cache_dir=None):
        super().__init__(parent)
        self.manager = QNetworkAccessManager(self)
        cache = QNetworkDiskCache(self)
        cache.setCacheDirectory(str(cache_dir or data_dir() / "cache/thumbnails"))
        cache.setMaximumCacheSize(50 * 1024 * 1024)
        self.manager.setCache(cache)
        self.requests = {}
        self.generation = {}
        self.serial = 0

    def cancel(self, key):
        self.generation.pop(key, None)
        reply = self.requests.pop(key, None)
        if reply:
            reply.abort()

    def request(self, key, url):
        self.cancel(key)
        self.serial += 1
        generation = self.serial
        target = QUrl(url or "")
        if target.scheme() not in ("http", "https") or not target.host() or target.userInfo():
            self.failed.emit(key)
            return
        self.generation[key] = generation
        request = QNetworkRequest(target)
        request.setTransferTimeout(12000)
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        # Do not persist signed/private image URLs with credential-like parameters.
        if not persistent_url(url):
            request.setAttribute(QNetworkRequest.Attribute.CacheSaveControlAttribute, False)
            request.setAttribute(QNetworkRequest.Attribute.CacheLoadControlAttribute,
                                 QNetworkRequest.CacheLoadControl.AlwaysNetwork)
        reply = self.manager.get(request)
        self.requests[key] = reply
        reply.setReadBufferSize(self.MAX_BYTES + 1)
        received = bytearray()

        def read():
            received.extend(bytes(reply.readAll()))
            if len(received) > self.MAX_BYTES:
                reply.abort()

        def finished():
            read()
            current = self.generation.get(key) == generation
            if current:
                self.requests.pop(key, None)
                self.generation.pop(key, None)
                image = QImage()
                if reply.error() == QNetworkReply.NetworkError.NoError and len(received) <= self.MAX_BYTES:
                    buffer = QBuffer()
                    buffer.setData(QByteArray(received))
                    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
                    reader = QImageReader(buffer)
                    size = reader.size()
                    # Bound decoding work/memory; do not decode decompression bombs.
                    if size.isValid() and size.width() * size.height() <= 32_000_000:
                        if max(size.width(), size.height()) > 960:
                            reader.setScaledSize(size.scaled(QSize(960, 960), Qt.AspectRatioMode.KeepAspectRatio))
                        image = reader.read()
                if image.isNull():
                    self.failed.emit(key)
                else:
                    self.ready.emit(key, image)
            reply.deleteLater()

        reply.readyRead.connect(read)
        reply.finished.connect(finished)

    def close(self):
        for key in list(self.requests):
            self.cancel(key)


class ThumbnailView(QWidget):
    def __init__(self, parent=None, compact=False):
        super().__init__(parent)
        self.image = QImage()
        self.message = "PRÉVIA DA MÍDIA\nAguardando um link"
        self.setMinimumSize(80 if compact else 230, 60 if compact else 250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.opacity = 1.0
        self.fade = QVariantAnimation(self)
        self.fade.setDuration(180)
        self.fade.valueChanged.connect(self._fade)

    def _fade(self, value):
        self.opacity = float(value)
        self.update()

    def placeholder(self, message):
        self.fade.stop()
        self.image = QImage()
        self.message = message
        self.update()

    def set_image(self, image):
        self.image = image
        self.fade.setStartValue(0.3)
        self.fade.setEndValue(1.0)
        self.fade.start()
        self.update()

    def image_rect(self):
        if self.image.isNull():
            return QRectF()
        available = self.rect().adjusted(12, 12, -12, -12)
        size = self.image.size().scaled(available.size(), Qt.AspectRatioMode.KeepAspectRatio)
        return QRectF((self.width() - size.width()) / 2, (self.height() - size.height()) / 2,
                      size.width(), size.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        painter.setBrush(QColor("#090610"))
        painter.setPen(QPen(QColor("#714594"), 1))
        painter.drawRoundedRect(rect, 10, 10)
        painter.setPen(QPen(QColor("#cf91ff"), 3))
        for x, y, dx, dy in ((5, 5, 1, 1), (self.width()-5, 5, -1, 1),
                             (5, self.height()-5, 1, -1),
                             (self.width()-5, self.height()-5, -1, -1)):
            painter.drawLine(x, y, x + 20 * dx, y)
            painter.drawLine(x, y, x, y + 20 * dy)
        if not self.image.isNull():
            painter.setOpacity(self.opacity)
            painter.drawImage(self.image_rect(), self.image)
        else:
            painter.setPen(QColor("#c4abd9"))
            painter.drawText(self.rect().adjusted(20, 20, -20, -20),
                             Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.message)


class PreviewPanel(QFrame):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.setObjectName("previewPanel")
        self.service = service
        self.key = f"preview-{id(self)}"
        layout = QVBoxLayout(self)
        label = QLabel("PRÉVIA")
        label.setObjectName("sectionLabel")
        layout.addWidget(label)
        self.view = ThumbnailView()
        layout.addWidget(self.view, 1)
        note = QLabel("Imagem completa • proporção original")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        service.ready.connect(self._ready)
        service.failed.connect(self._failed)
        self.setMaximumHeight(470)

    def clear(self):
        self.service.cancel(self.key)
        self.view.placeholder("PRÉVIA DA MÍDIA\nAguardando um link")

    def show_info(self, info):
        url = info.get("thumbnail")
        if not url:
            thumbnails = info.get("thumbnails") or []
            url = thumbnails[-1].get("url") if thumbnails else None
        self.view.placeholder("CARREGANDO PRÉVIA…" if url else "SEM MINIATURA\nA fonte não forneceu uma imagem")
        self.service.request(self.key, url)

    def _ready(self, key, image):
        if key == self.key:
            self.view.set_image(image)

    def _failed(self, key):
        if key == self.key:
            self.view.placeholder("SEM MINIATURA\nImagem indisponível")
