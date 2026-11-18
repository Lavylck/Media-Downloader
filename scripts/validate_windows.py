"""Exercise frozen builds and the per-user installer with real local media.

Uses a fresh artifact/data directory, a restricted child PATH, and refuses to
replace an existing user installation. Run sequentially with other native tests.
"""

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import winreg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from media_downloader.tests.test_real_media import TestRealMedia

UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{E0899E09-1DE4-4305-A491-53299A937351}_is1"


def registered():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            return winreg.QueryValueEx(key, "InstallLocation")[0]
    except FileNotFoundError:
        return None


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", action="store_true")
    parser.add_argument("--public-url", help="Optional real public media smoke; requires Internet")
    args = parser.parse_args()
    artifact = ROOT / "test-artifacts" / ("windows-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    artifact.mkdir(parents=True)
    env = os.environ.copy()
    env.update(PATH=str(Path(os.environ["SYSTEMROOT"]) / "System32"),
               QT_QPA_PLATFORM="windows", MEDIA_DOWNLOADER_DATA_DIR=str(artifact / "user-data"))
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "QT_PLUGIN_PATH"):
        env.pop(name, None)
    result = {"success": False, "artifact": str(artifact), "runs": []}
    exe = ROOT / "dist/MediaDownloader/MediaDownloader.exe"
    installer = ROOT / "dist/installer/MediaDownloader-3.0.0-Setup-x64.exe"
    shortcut = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Media Downloader.lnk"
    if args.installer and (registered() or shortcut.exists()):
        raise RuntimeError("Existe instalação/atalho do usuário; validação não irá substituí-los.")
    result["exe_sha256"] = digest(exe)
    if args.installer:
        result["installer_sha256"] = digest(installer)

    def run(binary, name, *options):
        report = artifact / name / "report.json"
        subprocess.run([str(binary), "--smoke-report", str(report), *options],
                       cwd=artifact, env=env, check=True, timeout=210)
        data = json.loads(report.read_text(encoding="utf-8"))
        assert data["success"], data
        for tool in data["tools"].values():
            assert Path(tool).is_relative_to(binary.parent / "_internal/bin"), tool
        for output in data["outputs"]:
            media = json.loads(subprocess.check_output([
                data["tools"]["ffprobe"], "-v", "error", "-show_streams", "-show_format",
                "-of", "json", output["path"]], text=True, timeout=30))
            kinds = {stream["codec_type"] for stream in media["streams"]}
            assert kinds == ({"audio", "video"} if output["container"] == "MP4" else {"audio"}), media
            assert float(media["format"]["duration"]) > 1
            assert output["progress"] == 100 and output["bytes"] > 0
            output["probe"] = media
        result["runs"].append({"name": name, **data})
        return data

    installed = False
    TestRealMedia.setUpClass()
    try:
        base = TestRealMedia.base_url
        run(exe, "portable", "--smoke-url", base + "sample.mp4")
        run(exe, "portable-restart", "--smoke-history")
        playlist = run(exe, "playlist", "--smoke-url", base + "playlist.html", "--smoke-playlist")
        assert playlist["queue_states"] == ["completed", "failed", "completed"] * 2, playlist
        if args.installer:
            install_dir = artifact / "installed"
            install_args = [str(installer), "/CURRENTUSER", "/VERYSILENT", "/SUPPRESSMSGBOXES",
                            "/NORESTART", "/TASKS=", f"/DIR={install_dir}",
                            f"/LOG={artifact / 'install.log'}"]
            subprocess.run(install_args, check=True, timeout=180)
            installed = True
            assert Path(registered()).resolve() == install_dir.resolve()
            assert shortcut.is_file()
            installed_exe = install_dir / "MediaDownloader.exe"
            assert digest(installed_exe) == digest(exe)
            run(installed_exe, "installed", "--smoke-url", base + "sample.mp4")
            run(installed_exe, "installed-restart", "--smoke-history")
            # Reinstall/upgrade the same version and check the persisted database.
            subprocess.run(install_args, check=True, timeout=180)
            run(installed_exe, "reinstalled-restart", "--smoke-history")
            preserved = [artifact / "user-data/history.sqlite3"]
            preserved += [Path(o["path"]) for r in result["runs"] for o in r["outputs"]]
            before = {str(path): digest(path) for path in preserved}
            subprocess.run([str(install_dir / "unins000.exe"), "/VERYSILENT",
                            "/SUPPRESSMSGBOXES", "/NORESTART",
                            f"/LOG={artifact / 'uninstall.log'}"], check=True, timeout=180)
            installed = False
            assert not installed_exe.exists()
            assert not registered()
            assert not shortcut.exists()
            assert before == {path: digest(path) for path in before}
            result["installer_lifecycle"] = "install, run, restart, reinstall, uninstall; data preserved"
        if args.public_url:
            run(exe, "public", "--smoke-url", args.public_url)
        result["success"] = True
    finally:
        TestRealMedia.tearDownClass()
        result["installation_left_for_inspection"] = installed
        (artifact / "validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(artifact / "validation.json")


if __name__ == "__main__":
    main()
