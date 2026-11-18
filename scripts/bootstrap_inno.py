"""Download the official Inno compiler in portable, per-project mode."""
import hashlib
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/jrsoftware/issrc/releases/download/is-7_1_1/innosetup-7.1.1-x64.exe"
SHA256 = "8a5a6711c3766a6e5fb74f280ba0e3551e719ce94538d901fdbd1f8f9920b3f0"


def main():
    folder = ROOT / ".build-tools"
    folder.mkdir(exist_ok=True)
    installer = folder / "innosetup-7.1.1-x64.exe"
    compiler = folder / "InnoSetup" / "ISCC.exe"
    if compiler.is_file():
        print(compiler)
        return
    if not installer.is_file():
        with urllib.request.urlopen(URL, timeout=60) as response, installer.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
    if hashlib.sha256(installer.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError("Hash do instalador Inno não corresponde à release oficial.")
    subprocess.run([str(installer), "/PORTABLE=1", "/CURRENTUSER", "/VERYSILENT",
                    "/SUPPRESSMSGBOXES", "/NORESTART", "/NOICONS", "/TASKS=",
                    f"/DIR={compiler.parent}"], check=True, timeout=120)
    if not compiler.is_file():
        raise RuntimeError("Compilador Inno não foi extraído.")
    print(compiler)


if __name__ == "__main__":
    main()
