"""Legacy import smoke check; safe to import during test discovery."""

from media_downloader.downloader.yt_dlp_wrapper import YtDlpWrapper


if __name__ == "__main__":
    print(f"Import success: {YtDlpWrapper.__name__}")
