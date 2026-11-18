import unittest

from media_downloader.downloader.yt_dlp_wrapper import YtDlpWrapper


class TestResolutionLabels(unittest.TestCase):
    def test_cinematic_labels_and_exact_selection(self):
        wrapper = YtDlpWrapper()
        for width, height, name in ((1920, 814, 1080), (1280, 542, 720), (854, 362, 480),
                                    (640, 272, 360), (426, 180, 240), (256, 108, 144)):
            with self.subTest(name=name):
                info = {"formats": [{"format_id": str(name), "width": width, "height": height,
                                      "format_note": f"{name}p", "vcodec": "h264", "acodec": "aac"}]}
                choices = wrapper.quality_choices(info, "MP4")
                self.assertEqual(choices[1], (f"{name}p — {width} × {height}", height))
                self.assertEqual(wrapper.download_selection(info, "MP4", choices[1][1])[0], str(name))
                self.assertEqual(info["formats"][0]["height"], height)

    def test_unknown_class_uses_dimensions_without_inventing_1080p(self):
        info = {"formats": [{"format_id": "x", "width": 1920, "height": 814}]}
        self.assertEqual(YtDlpWrapper().quality_choices(info, "MP4")[1], ("1920 × 814", 814))

    def test_variant_label_matches_the_format_actually_selected(self):
        info = {"formats": [
            {"format_id": "slow", "height": 814, "width": 1920, "fps": 24, "format_note": "1080p"},
            {"format_id": "fast", "height": 814, "width": 1920, "fps": 60, "format_note": "1080p60"},
        ]}
        wrapper = YtDlpWrapper()
        self.assertEqual(wrapper.quality_choices(info, "MP4")[1][0], "1080p — 1920 × 814")
        self.assertEqual(wrapper.download_selection(info, "MP4", 814)[0], "fast")
