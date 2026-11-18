"""Synchronous media operations. Call from a worker, never from a GUI slot."""

from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
from itertools import islice
from ..paths import tool_path

import yt_dlp
from yt_dlp.postprocessor import PostProcessor
from yt_dlp.postprocessor.ffmpeg import FFmpegVideoConvertorPP, FFmpegVideoRemuxerPP
from yt_dlp.utils import PostProcessingError


class OperationCancelled(Exception):
    """Cooperative cancellation at the next safe network/processing boundary."""


def check_cancelled(event):
    if event is not None and event.is_set():
        raise OperationCancelled("Operação cancelada.")


def validate_url(url):
    try:
        parts = urlsplit(url)
        valid = (parts.scheme in ("http", "https") and parts.hostname
                 and not parts.username and not parts.password
                 and not any(c.isspace() for c in url) and parts.port != 0)
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Informe uma URL HTTP ou HTTPS válida.")
    return url


class _Logger:
    def __init__(self, cancel_event, status):
        self.cancel_event = cancel_event
        self.status = status

    def debug(self, message):
        check_cancelled(self.cancel_event)

    info = debug

    def warning(self, message):
        check_cancelled(self.cancel_event)
        if self.status:
            self.status(f"Aviso: {message}")

    def error(self, message):
        check_cancelled(self.cancel_event)


class _EnsureMP4(PostProcessor):
    """Prefer lossless remux; transcode only if the source codecs require it."""

    def run(self, info):
        try:
            return FFmpegVideoRemuxerPP(self._downloader, preferedformat="mp4").run(info)
        except PostProcessingError:
            self.to_screen("Remux indisponível; convertendo para MP4 (sem aumentar qualidade).")
            return FFmpegVideoConvertorPP(self._downloader, preferedformat="mp4").run(info)


class _FinalPath(PostProcessor):
    def __init__(self, downloader, paths):
        super().__init__(downloader)
        self.paths = paths

    def run(self, info):
        self.paths.append(info["filepath"])
        return [], info


class YtDlpWrapper:
    @staticmethod
    def quality_label(fmt):
        """Use extractor labels, never infer a YouTube class from aspect ratio."""
        for key in ("quality_label", "format_note", "format"):
            match = re.search(r"(?<!\w)(\d{2,4})p(?:\d{2,3})?(?!\w)", str(fmt.get(key) or ""))
            if match:
                return f"{match[1]}p"
        return None

    def _options(self, cancel_event=None, status_hook=None):
        runtimes = {}
        for name in ("deno", "node"):
            executable = tool_path(name)
            if executable:
                runtimes[name] = {"path": executable}
        opts = {
            "quiet": True,
            "noprogress": True,
            "noplaylist": True,
            "extract_flat": "in_playlist",
            "lazy_playlist": True,
            "ignoreerrors": False,
            "socket_timeout": 15,
            "retries": 2,
            "fragment_retries": 2,
            "extractor_retries": 2,
            "skip_unavailable_fragments": False,
            "windowsfilenames": True,
            "overwrites": False,
            "continuedl": True,
            "cachedir": False,
            "js_runtimes": runtimes,
            "logger": _Logger(cancel_event, status_hook),
        }
        ffmpeg = tool_path("ffmpeg")
        if ffmpeg:
            opts["ffmpeg_location"] = str(Path(ffmpeg).parent)
        return opts

    @staticmethod
    def _single_media(info):
        if not info:
            raise ValueError("A fonte não retornou informações da mídia.")
        if info.get("_type") in ("playlist", "multi_video") or "entries" in info:
            raise ValueError("Use uma mídia individual ou selecione os itens no modo Playlist.")
        if info.get("is_live"):
            raise ValueError("Transmissões ao vivo não são suportadas nesta versão.")
        if info.get("has_drm"):
            raise ValueError("Mídia protegida por DRM não é suportada.")
        return info

    def extract_info(self, url, *, cancel_event=None, status_hook=None):
        validate_url(url)
        check_cancelled(cancel_event)
        opts = self._options(cancel_event, status_hook)
        opts["playlist_items"] = "1:101"
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and (info.get("_type") in ("playlist", "multi_video") or "entries" in info):
                return self._playlist_result(info, url, 0, 100, cancel_event)
        check_cancelled(cancel_event)
        return self._single_media(info)

    @staticmethod
    def _playlist_result(info, url, offset, limit, cancel_event):
        entries = []
        for entry in islice(info.get("entries") or [], limit + 1):
            check_cancelled(cancel_event)
            entry = entry or {}
            # Generic playlist entries can inherit the parent's webpage_url;
            # their own url identifies the actual item and must take precedence.
            target = entry.get("url") or entry.get("webpage_url") or ""
            if not target.startswith(("http://", "https://")) and entry.get("ie_key") == "Youtube":
                target = "https://www.youtube.com/watch?v=" + str(entry.get("id") or target)
            available = (target.startswith(("http://", "https://"))
                         and entry.get("availability") not in ("private", "needs_auth", "premium_only", "subscriber_only"))
            thumbnails = entry.get("thumbnails") or []
            entries.append({
                "url": target, "title": entry.get("title") or "Item indisponível",
                "thumbnail": entry.get("thumbnail") or (thumbnails[-1].get("url") if thumbnails else ""),
                "available": bool(available), "duration": entry.get("duration"),
                "index": entry.get("playlist_index") or offset + len(entries) + 1,
            })
        return {"_type": "playlist", "title": info.get("title") or "Playlist",
                "webpage_url": url, "entries": entries[:limit], "offset": offset,
                "thumbnail": info.get("thumbnail") or next((e["thumbnail"] for e in entries if e["thumbnail"]), ""),
                "playlist_count": info.get("playlist_count") or info.get("n_entries"),
                "has_more": len(entries) > limit}

    def playlist_page(self, url, offset=0, limit=100, *, cancel_event=None, status_hook=None):
        validate_url(url)
        opts = self._options(cancel_event, status_hook)
        opts.update({"noplaylist": False, "extract_flat": True,
                     "playlist_items": f"{offset + 1}:{offset + limit + 1}"})
        check_cancelled(cancel_event)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info or "entries" not in info:
                raise ValueError("Esta URL não retornou uma playlist.")
            return self._playlist_result(info, url, offset, limit, cancel_event)

    @staticmethod
    def formats(info, kind):
        formats = info.get("formats") or [info]
        codec = "vcodec" if kind == "video" else "acodec"
        return [f for f in formats if f.get("format_id") is not None
                and not f.get("has_drm") and f.get(codec) != "none"]

    def select_best_format(self, info, format_type="best"):
        kind = "audio" if format_type == "audio" else "video"
        formats = self.formats(info, kind)
        if not formats:
            return {}
        keys = ("abr", "asr", "audio_channels", "tbr") if kind == "audio" else ("height", "fps", "tbr")
        # yt-dlp sorts worst to best; preserve its ordering for equal/unknown fields.
        return max(enumerate(formats),
                   key=lambda item: (*(item[1].get(k) or 0 for k in keys), item[0]))[1]

    def quality_choices(self, info, container):
        if info.get("_type") == "playlist":
            if container == "MP3":
                return [("Melhor áudio de cada item", None),
                        ("Fonte até 128 kb/s (quando informado)", {"audio_ceiling": 128})]
            return [("Melhor disponível em cada item", None)] + [
                (f"Limite por item: até {n}p / linhas", {"ceiling": n}) for n in (2160, 1440, 1080, 720, 480, 360)]
        kind = "video" if container == "MP4" else "audio"
        formats = self.formats(info, kind)
        if not formats:
            return []
        choices = [("Melhor disponível (automático)", None)]
        if kind == "video":
            heights = sorted({f["height"] for f in formats if f.get("height")}, reverse=True)
            for height in heights:
                selected = self.select_best_format(
                    {"formats": [f for f in formats if f.get("height") == height]}, "video")
                width = selected.get("width")
                dimensions = f"{width:g} × {height:g}" if width else f"{height:g} px de altura"
                name = self.quality_label(selected)
                choices.append((f"{name} — {dimensions}" if name else dimensions, height))
        else:
            rates = sorted({f["abr"] for f in formats if f.get("abr")}, reverse=True)
            choices.extend((f"Fonte: {rate:g} kb/s", rate) for rate in rates)
        return choices

    def download_selection(self, info, container, quality=None):
        kind = "video" if container == "MP4" else "audio"
        formats = self.formats(info, kind)
        field = "height" if kind == "video" else "abr"
        if isinstance(quality, dict):
            ceiling = quality.get("ceiling") if kind == "video" else quality.get("audio_ceiling")
            def level(fmt):
                label = self.quality_label(fmt) if kind == "video" else None
                return int(label[:-1]) if label else (fmt.get(field) or 0)
            if ceiling:
                formats = [f for f in formats if level(f) <= ceiling]
        elif quality is not None:
            formats = [f for f in formats if f.get(field) == quality]
        best = self.select_best_format({"formats": formats}, kind) if formats else {}
        if not best:
            raise ValueError("Não há um formato compatível com esta seleção.")
        format_id = str(best["format_id"])
        if container == "MP3":
            return format_id, [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
                                "preferredquality": "0"}]
        if best.get("acodec") == "none":
            audio = [f for f in self.formats(info, "audio") if f.get("vcodec") == "none"]
            if audio:
                audio_best = self.select_best_format({"formats": audio}, "audio")
                format_id += "+" + str(audio_best["format_id"])
        return format_id, []

    @staticmethod
    def output_template(destination, container, quality=None):
        # Escape literal percent signs in directory names from yt-dlp templating.
        directory = str(Path(destination).resolve()).replace("%", "%%")
        label = ("best" if quality is None else f"limit-{next(iter(quality.values()))}"
                 if isinstance(quality, dict) else f"{quality:g}")
        return str(Path(directory) / f"%(title).100s [%(id).40s] [{container.lower()}-{label}].%(ext)s")

    def download(self, url, format_id, outtmpl, postprocessors=None, progress_hook=None,
                 *, cancel_event=None, status_hook=None):
        validate_url(url)
        check_cancelled(cancel_event)
        if not tool_path("ffmpeg") or not tool_path("ffprobe"):
            raise RuntimeError("FFmpeg e FFprobe precisam estar no PATH. Consulte o README.")
        audio = any(p.get("key") == "FFmpegExtractAudio" for p in postprocessors or [])
        target_ext = ".mp3" if audio else ".mp4"
        paths = []

        def progress(data):
            check_cancelled(cancel_event)
            if progress_hook:
                progress_hook(data)

        def postprocess(data):
            check_cancelled(cancel_event)
            if status_hook and data.get("status") == "started":
                status_hook("Processando mídia com FFmpeg…")

        opts = self._options(cancel_event, status_hook)
        opts.update({
            "format": format_id,
            "outtmpl": outtmpl,
            "merge_output_format": "mkv",
            "postprocessors": postprocessors or [],
            "progress_hooks": [progress],
            "postprocessor_hooks": [postprocess],
        })
        with yt_dlp.YoutubeDL(opts) as ydl:
            if not audio:
                ydl.add_post_processor(_EnsureMP4(ydl))
            ydl.add_post_processor(_FinalPath(ydl, paths), when="after_move")
            info = self._single_media(ydl.extract_info(url, download=False))
            check_cancelled(cancel_event)
            target = Path(ydl.prepare_filename(info)).with_suffix(target_ext)
            if target.is_file() and target.stat().st_size > 0:
                if status_hook:
                    status_hook("Arquivo já existente; preservado.")
                return str(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            ydl.process_ie_result(info, download=True)
        check_cancelled(cancel_event)
        if not paths:
            raise RuntimeError("O download terminou sem informar um arquivo final.")
        result = Path(paths[-1])
        if result.suffix.lower() != target_ext or not result.is_file() or result.stat().st_size == 0:
            raise RuntimeError("O arquivo final esperado não foi produzido.")
        return str(result.resolve())
