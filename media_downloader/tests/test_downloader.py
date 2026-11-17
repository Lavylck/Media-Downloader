import unittest
from unittest.mock import patch, MagicMock
from media_downloader.downloader.yt_dlp_wrapper import YtDlpWrapper

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

if __name__ == '__main__':
    unittest.main()
