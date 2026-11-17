"""Legacy entry point; imports no longer create a QApplication or exit."""
if __name__ == "__main__":
    import unittest
    unittest.main(module="media_downloader.tests.test_ui")
