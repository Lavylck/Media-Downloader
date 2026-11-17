"""Legacy entry point; use the maintained worker regression suite."""
if __name__ == "__main__":
    import unittest
    unittest.main(module="media_downloader.tests.test_workers")
