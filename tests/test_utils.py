import tempfile
import unittest
from pathlib import Path

from astrbot_plugin_angel_smile.tests._bootstrap import install_fake_astrbot

install_fake_astrbot()

from astrbot_plugin_angel_smile.utils import (  # noqa: E402
    is_path_within_roots,
    is_valid_meme_name,
)


class UtilsTestCase(unittest.TestCase):
    def test_is_valid_meme_name(self):
        self.assertTrue(is_valid_meme_name("坏笑"))
        self.assertTrue(is_valid_meme_name("happy"))
        self.assertTrue(is_valid_meme_name("表情123"))
        self.assertFalse(is_valid_meme_name(""))
        self.assertFalse(is_valid_meme_name("   "))
        self.assertFalse(is_valid_meme_name(".hidden"))
        self.assertFalse(is_valid_meme_name("a/b"))
        self.assertFalse(is_valid_meme_name("a\\b"))
        self.assertFalse(is_valid_meme_name('a"b'))

    def test_path_within_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "sub" / "image.png"
            nested.parent.mkdir(parents=True, exist_ok=True)
            nested.write_bytes(b"ok")

            self.assertTrue(is_path_within_roots(nested, [root]))
            self.assertFalse(is_path_within_roots(Path(temp_dir).parent / "other.png", [root]))

if __name__ == "__main__":
    unittest.main()
