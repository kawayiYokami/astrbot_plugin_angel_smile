import tempfile
import unittest
from pathlib import Path

from astrbot_plugin_angel_smile.tests._bootstrap import install_fake_astrbot


install_fake_astrbot()

from astrbot_plugin_angel_smile.utils import (  # noqa: E402
    is_path_within_roots,
    normalize_category_name,
    safe_filename,
)


class UtilsTestCase(unittest.TestCase):
    def test_normalize_category_name(self):
        self.assertEqual(normalize_category_name(" Happy Mood "), "happy_mood")
        self.assertEqual(normalize_category_name("???"), "unsorted")

    def test_safe_filename_strips_unsafe_chars(self):
        result = safe_filename('a<>:"/\\|?*.png', ".jpg")
        self.assertTrue(result.endswith(".png"))
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)

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
