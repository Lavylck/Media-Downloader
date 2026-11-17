"""Local dependency checks: python -m media_downloader.diagnostics."""

from importlib.metadata import version, PackageNotFoundError
import shutil
import subprocess
import sys


def main():
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Virtual environment: {sys.prefix != sys.base_prefix}")
    missing = False
    for package in ("PySide6", "yt-dlp", "yt-dlp-ejs"):
        try:
            print(f"{package}: {version(package)}")
        except PackageNotFoundError:
            print(f"{package}: AUSENTE")
            missing = True
    runtime = False
    for tool in ("ffmpeg", "ffprobe", "deno", "node"):
        path = shutil.which(tool)
        if not path:
            print(f"{tool}: ausente")
            missing |= tool in ("ffmpeg", "ffprobe")
            continue
        try:
            result = subprocess.run(
                [path, "-version" if tool.startswith("ff") else "--version"],
                capture_output=True, text=True, timeout=10, check=True)
            text = result.stdout.splitlines()[0]
            print(f"{tool}: {text} ({path})")
            if tool in ("deno", "node"):
                numbers = tuple(int(n) for n in text.split()[-1].lstrip("v").split(".")[:3])
                runtime |= numbers >= ((2, 3, 0) if tool == "deno" else (22, 0, 0))
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            print(f"{tool}: falha: {exc}")
            missing |= tool in ("ffmpeg", "ffprobe")
    print(f"Runtime JavaScript compatível: {runtime}")
    from media_downloader.ui.main_window import MainWindow
    from media_downloader.ui.analysis_worker import AnalysisWorker
    from media_downloader.ui.download_worker import DownloadWorker
    print("Imports: OK")
    return int(missing or not runtime)


if __name__ == "__main__":
    raise SystemExit(main())
