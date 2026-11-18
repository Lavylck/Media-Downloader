"""Reproducible Windows onedir + optional Inno installer build (local only)."""
import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from media_downloader.paths import VERSION, tool_path
from media_downloader.resources import ICON_ICO, ICON_PNG


def download(url, target):
    if not target.is_file():
        with urllib.request.urlopen(url, timeout=60) as response:
            target.write_bytes(response.read())


def prepare_notices(build, tools):
    notices = build / "licenses"
    notices.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "distribution/THIRD_PARTY_NOTICE.md", notices)
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        if name.lower() in {"pip", "setuptools", "pyinstaller", "pillow", "ffmpeg-python", "future"}:
            continue
        for file in dist.files or []:
            if any(word in str(file).lower() for word in ("license", "copying", "copyright")) and file.suffix in ("", ".txt", ".md"):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    destination = notices / name / file.name
                    destination.parent.mkdir(exist_ok=True)
                    shutil.copy2(source, destination)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        shutil.copy2(python_license, notices / "PYTHON-LICENSE.txt")
    ffmpeg_root = Path(tools["ffmpeg"]).parent.parent
    for name in ("LICENSE", "README.txt"):
        source = ffmpeg_root / name
        if not source.is_file():
            raise RuntimeError(f"Proveniência/licença do FFmpeg ausente: {source}")
        shutil.copy2(source, notices / ("FFMPEG-" + name))
    node_version = subprocess.check_output([tools["node"], "--version"], text=True).strip()
    download(f"https://raw.githubusercontent.com/nodejs/node/{node_version}/LICENSE",
             notices / "NODE-LICENSE.txt")
    manifest = {
        "application": VERSION, "python": sys.version,
        "icons": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ICON_PNG, ICON_ICO)},
        "sources": {str(path.relative_to(ROOT)).replace("\\", "/"):
                    hashlib.sha256(path.read_bytes()).hexdigest()
                    for folder in (ROOT / "media_downloader", ROOT / "scripts")
                    for path in folder.rglob("*")
                    if path.is_file() and path.suffix in (".py", ".qss", ".svg")
                    and "tests" not in path.parts and "__pycache__" not in path.parts},
        "packages": {name: metadata.version(name) for name in ("PySide6", "yt-dlp", "yt-dlp-ejs", "pyinstaller")},
        "tools": {name: {"sha256": hashlib.file_digest(Path(path).open("rb"), "sha256").hexdigest(),
                         "version": subprocess.check_output([path, "-version" if name.startswith("ff") else "--version"],
                                                            text=True).splitlines()[0]}
                  for name, path in tools.items()},
    }
    (notices / "build-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return notices


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise RuntimeError("Execute o build no Windows.")
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    tools = {name: tool_path(name) for name in ("ffmpeg", "ffprobe", "node")}
    if not all(tools.values()):
        raise RuntimeError("FFmpeg, FFprobe e Node precisam estar disponíveis para montar o pacote.")
    licenses = prepare_notices(build, tools)
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
               "--windowed", "--name", "MediaDownloader", "--noupx",
               "--distpath", str(ROOT / "dist"), "--workpath", str(build / "pyinstaller"),
               "--specpath", str(build), "--paths", str(ROOT),
               "--icon", str(ICON_ICO), "--hidden-import", "PySide6.QtSvg",
               "--collect-submodules", "yt_dlp", "--collect-data", "yt_dlp",
               "--collect-all", "yt_dlp_ejs", "--copy-metadata", "yt-dlp",
               "--copy-metadata", "yt-dlp-ejs", "--collect-data", "certifi",
               "--exclude-module", "media_downloader.tests",
               "--add-data", f"{ICON_PNG}:assets/icons", "--add-data", f"{ICON_ICO}:assets/icons",
               "--add-data", f"{ROOT / 'media_downloader/ui/themes'}:media_downloader/ui/themes",
               "--add-data", f"{licenses}:licenses"]
    for tool in tools.values():
        command.extend(["--add-binary", f"{tool}:bin"])
    command.append(str(ROOT / "scripts/run_app.py"))
    subprocess.run(command, cwd=ROOT, check=True)
    output = ROOT / "dist/MediaDownloader"
    shutil.copy2(ROOT / "distribution/README_WINDOWS.md", output / "LEIA-ME.md")
    if args.installer:
        compiler = ROOT / ".build-tools/InnoSetup/ISCC.exe"
        if not compiler.exists():
            subprocess.run([sys.executable, str(ROOT / "scripts/bootstrap_inno.py")], check=True)
        subprocess.run([str(compiler), str(ROOT / "distribution/MediaDownloader.iss")], check=True)
        binaries = [output / "MediaDownloader.exe", ROOT / f"dist/installer/MediaDownloader-{VERSION}-Setup-x64.exe"]
        lines = []
        for binary in binaries:
            with binary.open("rb") as f:
                lines.append(f"{hashlib.file_digest(f, 'sha256').hexdigest()}  {binary.relative_to(ROOT / 'dist').as_posix()}")
        (ROOT / "dist/SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"EXECUTABLE: {output / 'MediaDownloader.exe'}")


if __name__ == "__main__":
    main()
