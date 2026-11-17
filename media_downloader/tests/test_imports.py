import ast
import importlib
from pathlib import Path
import pkgutil
import unittest

import media_downloader


class TestImports(unittest.TestCase):
    def test_all_application_modules_import(self):
        for module in pkgutil.walk_packages(media_downloader.__path__, "media_downloader."):
            if ".tests" in module.name:
                continue
            with self.subTest(module=module.name):
                importlib.import_module(module.name)

    def test_python_sources_have_no_nulls_and_compile(self):
        root = Path(__file__).resolve().parents[2]
        sources = list((root / "media_downloader").rglob("*.py")) + list(root.glob("*.py"))
        for path in sources:
            with self.subTest(path=path):
                source = path.read_bytes()
                self.assertNotIn(b"\x00", source)
                ast.parse(source)
