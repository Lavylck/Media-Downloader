"""Per-item temporary files and HTTP byte-resume contract (never serialized)."""

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

import yt_dlp
from yt_dlp.networking.exceptions import HTTPError


class TransferPaused(Exception):
    pass


class Transfer:
    def __init__(self):
        self.pause = Event()
        self.directory = None
        self.partial = None
        self.offset = 0
        self.validator = None
        self.total = None
        self.format_id = None

    def workspace(self, destination):
        if self.directory is None:
            Path(destination).mkdir(parents=True, exist_ok=True)
            self.directory = TemporaryDirectory(prefix=".md-transfer-", dir=destination)
        return self.directory.name

    def discard(self):
        if self.directory is not None:
            self.directory.cleanup()
            self.directory = None


class TransferDL(yt_dlp.YoutubeDL):
    """Observe the actual media response, not extractor hints or a HEAD probe."""

    transfer = None
    media_url = None
    resumable = False

    def urlopen(self, request):
        transfer = self.transfer
        direct = transfer is not None and getattr(request, "url", None) == self.media_url
        if direct and transfer.offset:
            if request.headers.get("Range") != f"bytes={transfer.offset}-":
                raise ValueError("Não é possível continuar do byte salvo. Tente novamente do início.")
            request.headers["If-Range"] = transfer.validator
        try:
            response = super().urlopen(request)
        except HTTPError as exc:
            if direct and transfer.offset:
                exc.close()
                raise ValueError("A fonte recusou a retomada. Tente novamente do início.") from exc
            raise
        if direct:
            headers = response.headers
            validator = headers.get("ETag")
            if not validator or validator.startswith("W/"):
                validator = headers.get("Last-Modified")
            if transfer.offset:
                if (response.status != 206 or validator != transfer.validator or
                        headers.get("Content-Range") !=
                        f"bytes {transfer.offset}-{transfer.total - 1}/{transfer.total}"):
                    response.close()
                    raise ValueError("A fonte mudou ou recusou a retomada. Tente novamente do início.")
                transfer.offset = 0
                self.resumable = True
            elif response.status == 200:
                size = headers.get("Content-Length", "")
                self.resumable = bool(validator and size.isdigit() and
                                      headers.get("Accept-Ranges", "").lower() == "bytes" and
                                      headers.get("Content-Encoding", "identity") == "identity")
                if self.resumable:
                    transfer.total, transfer.validator = int(size), validator
        return response
