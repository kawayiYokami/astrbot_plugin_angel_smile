import tempfile
import unittest
from pathlib import Path

from astrbot_plugin_angel_smile.tests._bootstrap import install_fake_astrbot

install_fake_astrbot()

from astrbot_plugin_angel_smile.utils import (  # noqa: E402
    is_path_within_roots,
    is_valid_meme_name,
    stable_select,
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

    def test_stable_select_deterministic(self):
        variants = [Path("/a.webp"), Path("/b.webp"), Path("/c.webp")]
        result1 = stable_select(variants, "msg1", "坏笑", 0)
        result2 = stable_select(variants, "msg1", "坏笑", 0)
        self.assertEqual(result1, result2)

    def test_stable_select_single_variant(self):
        variants = [Path("/only.webp")]
        result = stable_select(variants, "msg1", "坏笑", 0)
        self.assertEqual(result, Path("/only.webp"))

    def test_stable_select_different_context_may_differ(self):
        variants = [Path("/a.webp"), Path("/b.webp"), Path("/c.webp")]
        results = set()
        for i in range(100):
            r = stable_select(variants, f"msg{i}", "坏笑", 0)
            results.add(r)
        # With 100 different message IDs and 3 variants, we should hit at least 2
        self.assertGreaterEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
