import yt_dlp
import os
import subprocess
from typing import List, Dict, Any

class YtDlpWrapper:
    def __init__(self):
        self.ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "no_warnings": True,
            "cache_filename": "yt_dlp_cache.txt",
        }

    def extract_info(self, url: str) -> Dict[str, Any]:
        """Extract video information using yt-dlp."""
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return info

    def select_best_format(self, info: Dict[str, Any], format_type: str) -> Dict[str, Any]:
        """Select the best format based on type.
        format_type: 'video' or 'audio' or 'best'
        """
        formats = info.get("formats", [])
        if not formats:
            return {}
        if format_type == "video":
            # filter video formats
            video_formats = [f for f in formats if f.get("vcodec", "none") != "none" and f.get("acodec", "none") == "none"]
            if not video_formats:
                return {}
            # sort by resolution and filesize
            video_formats.sort(key=lambda f: (f.get("height", 0), f.get("filesize", 0)), reverse=True)
            return video_formats[0]
        elif format_type == "audio":
            audio_formats = [f for f in formats if f.get("acodec", "none") != "none" and f.get("vcodec", "none") == "none"]
            if not audio_formats:
                return {}
            audio_formats.sort(key=lambda f: (f.get("abr", 0), f.get("filesize", 0)), reverse=True)
            return audio_formats[0]
        else:
            # best: choose format with highest quality and minimal conversion
            best = None
            best_score = -1
            for f in formats:
                score = 0
                if f.get("vcodec", "none") != "none":
                    score += (f.get("height", 0) or 0) * 2
                if f.get("acodec", "none") != "none":
                    score += f.get("abr", 0) or 0
                if score > best_score:
                    best_score = score
                    best = f
            return best if best else {}

    def download(self, url: str, format_id: str, outtmpl: str, postprocessors: List[Dict[str, Any]] = None, progress_hook=None) -> str:
        """Download the video or audio using yt-dlp."""
        # Prevent duplicate downloads
        if os.path.exists(outtmpl):
            return outtmpl
        
        opts = {
            "format": format_id,
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
        }
        if postprocessors:
            opts["postprocessors"] = postprocessors
        if progress_hook:
            opts["progress_hooks"] = [progress_hook]
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            # yt_dlp.YoutubeDL.download returns a list of info dicts
            # we catch errors here if needed.
            ydl.download([url])
        return outtmpl
