"""PyInstaller entry point; keep package imports absolute."""
from media_downloader.main import main

if __name__ == "__main__":
    raise SystemExit(main())
