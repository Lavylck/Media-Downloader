import unittest
from unittest.mock import patch, MagicMock
from media_downloader.downloader.yt_dlp_wrapper import YtDlpWrapper
from media_downloader.downloader.yt_dlp_wrapper import validate_url

class TestYtDlpWrapper(unittest.TestCase):
    @patch('media_downloader.downloader.yt_dlp_wrapper.yt_dlp.YoutubeDL')
    def test_extract_info(self, mock_ydl):
        mock_ydl.return_value.__enter__.return_value.extract_info.return_value = {
            'title': 'Test Video',
            'duration': 120,
            'formats': [],
        }
        wrapper = YtDlpWrapper()
        info = wrapper.extract_info('http://example.com')
        self.assertEqual(info['title'], 'Test Video')
        self.assertEqual(info['duration'], 120)

    def test_select_best_format_video(self):
        wrapper = YtDlpWrapper()
        info = {
            'formats': [
                {'format_id': '22', 'vcodec': 'h264', 'acodec': 'none', 'height': 720, 'filesize': 5000000},
                {'format_id': '18', 'vcodec': 'h264', 'acodec': 'none', 'height': 360, 'filesize': 2000000},
            ]
        }
        best = wrapper.select_best_format(info, 'video')
        self.assertEqual(best['format_id'], '22')

    def test_select_best_format_audio(self):
        wrapper = YtDlpWrapper()
        info = {
            'formats': [
                {'format_id': '140', 'acodec': 'aac', 'vcodec': 'none', 'abr': 128, 'filesize': 3000000},
                {'format_id': '139', 'acodec': 'aac', 'vcodec': 'none', 'abr': 64, 'filesize': 1000000},
            ]
        }
        best = wrapper.select_best_format(info, 'audio')
        self.assertEqual(best['format_id'], '140')

    def test_select_best_format_best(self):
        wrapper = YtDlpWrapper()
        info = {
            'formats': [
                {'format_id': '22', 'vcodec': 'h264', 'acodec': 'aac', 'height': 720, 'abr': 128, 'filesize': 5000000},
                {'format_id': '140', 'vcodec': 'none', 'acodec': 'aac', 'height': None, 'abr': 128, 'filesize': 3000000},
            ]
        }
        best = wrapper.select_best_format(info, 'best')
        self.assertEqual(best['format_id'], '22')

    def test_nullable_metadata_and_real_qualities(self):
        wrapper = YtDlpWrapper()
        info = {"formats": [
            {"format_id": "low", "height": 360, "fps": None, "tbr": None, "acodec": "aac"},
            {"format_id": "high", "height": 1080, "fps": 30, "tbr": None, "acodec": "none"},
            {"format_id": "storyboard", "vcodec": "none", "acodec": "none"},
            {"format_id": "drm", "height": 2160, "has_drm": True},
        ]}
        self.assertEqual(wrapper.select_best_format(info, "video")["format_id"], "high")
        self.assertEqual([v for _, v in wrapper.quality_choices(info, "MP4")], [None, 1080, 360])
        self.assertEqual(wrapper.download_selection(info, "MP4", 360)[0], "low")
        with self.assertRaises(ValueError):
            wrapper.download_selection(info, "MP4", 720)

    def test_reject_playlist_live_and_drm(self):
        for info in ({"_type": "playlist", "entries": []}, {"is_live": True}, {"has_drm": True}, None):
            with self.subTest(info=info), self.assertRaises(ValueError):
                YtDlpWrapper._single_media(info)

    def test_url_validation(self):
        for url in ("https://example.com/video", "http://127.0.0.1:8000/a.mp4"):
            self.assertEqual(validate_url(url), url)
        for url in ("file:///C:/foo", "test", "https://", "https://host:abc/x", "http://[invalid"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)

    @patch("media_downloader.downloader.yt_dlp_wrapper.yt_dlp.YoutubeDL")
    def test_extraction_error_propagates(self, mock_ydl):
        mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = RuntimeError("offline")
        with self.assertRaisesRegex(RuntimeError, "offline"):
            YtDlpWrapper().extract_info("https://example.com")

    @patch("media_downloader.downloader.yt_dlp_wrapper.shutil.which", return_value=None)
    def test_missing_ffmpeg_is_explicit(self, _):
        with self.assertRaisesRegex(RuntimeError, "FFmpeg"):
            YtDlpWrapper().download("https://example.com", "best", "test.%(ext)s")

    def test_audio_only_has_no_video_quality(self):
        info = {"formats": [{"format_id": "audio", "vcodec": "none", "acodec": "opus", "abr": None}]}
        wrapper = YtDlpWrapper()
        self.assertEqual(wrapper.quality_choices(info, "MP4"), [])
        self.assertEqual(wrapper.download_selection(info, "MP3")[0], "audio")

if __name__ == '__main__':
    unittest.main()
