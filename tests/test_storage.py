import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from astrbot_plugin_angel_smile.tests._bootstrap import install_fake_astrbot

install_fake_astrbot()

from astrbot_plugin_angel_smile.models import PluginPaths  # noqa: E402
from astrbot_plugin_angel_smile.services.storage import MemeStorage  # noqa: E402


class StorageTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        os.environ["ASTRBOT_TEST_DATA_PATH"] = self.temp_dir.name

        root = Path(self.temp_dir.name)
        self.paths = PluginPaths(
            plugin_dir=root / "plugin",
            data_dir=root / "data",
            meme_dir=root / "data" / "memes",
        )
        self.paths.meme_dir.mkdir(parents=True, exist_ok=True)
        self.storage = MemeStorage(self.paths)

    def _create_image(self, path: Path, color: str = "red"):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (16, 16), color=color).save(path)

    def test_scan_root_single_file(self):
        """Root image file is listed as a meme."""
        self._create_image(self.paths.meme_dir / "坏笑.webp")
        index = self.storage.scan_meme_index()
        self.assertIn("坏笑", index)
        self.assertEqual(len(index["坏笑"]), 1)

    def test_scan_folder_variants(self):
        """Folder with images is listed as a meme with multiple variants."""
        folder = self.paths.meme_dir / "坏笑"
        self._create_image(folder / "坏笑.webp")
        self._create_image(folder / "坏笑(2).webp", color="blue")
        index = self.storage.scan_meme_index()
        self.assertIn("坏笑", index)
        self.assertEqual(len(index["坏笑"]), 2)

    def test_folder_priority_over_root_file(self):
        """Folder takes priority over same-name root file."""
        self._create_image(self.paths.meme_dir / "坏笑.webp")
        folder = self.paths.meme_dir / "坏笑"
        self._create_image(folder / "坏笑.webp", color="blue")
        self._create_image(folder / "坏笑(2).webp", color="green")

        index = self.storage.scan_meme_index()
        self.assertIn("坏笑", index)
        # Should use folder variants, not root file
        self.assertEqual(len(index["坏笑"]), 2)
        self.assertTrue(all("坏笑/" in str(p) or "坏笑\\" in str(p) for p in index["坏笑"]))

    def test_ignores_dhash_index_file(self):
        """image_dhash_index.json is not treated as a meme."""
        (self.paths.meme_dir / "image_dhash_index.json").write_text("{}", encoding="utf-8")
        self._create_image(self.paths.meme_dir / "无语.webp")
        index = self.storage.scan_meme_index()
        self.assertNotIn("image_dhash_index", index)
        self.assertIn("无语", index)

    def test_ignores_invalid_meme_names(self):
        """Files starting with dot are ignored."""
        self._create_image(self.paths.meme_dir / ".hidden.webp")
        index = self.storage.scan_meme_index()
        self.assertNotIn(".hidden", index)

    def test_ingest_first_time(self):
        """First ingest creates .meme/<emotion>.webp."""
        source = Path(self.temp_dir.name) / "source.png"
        self._create_image(source)

        result = self.storage.ingest_meme("坏笑", source)
        self.assertEqual(result, self.paths.meme_dir / "坏笑.webp")
        self.assertTrue(result.exists())

    def test_ingest_second_time_upgrades_to_folder(self):
        """Second ingest creates folder and moves original."""
        source1 = Path(self.temp_dir.name) / "s1.png"
        source2 = Path(self.temp_dir.name) / "s2.png"
        self._create_image(source1)
        self._create_image(source2, color="blue")

        self.storage.ingest_meme("坏笑", source1)
        result2 = self.storage.ingest_meme("坏笑", source2)

        folder = self.paths.meme_dir / "坏笑"
        self.assertTrue(folder.is_dir())
        self.assertTrue((folder / "坏笑.webp").exists())
        self.assertEqual(result2, folder / "坏笑(2).webp")
        self.assertTrue(result2.exists())
        # Original root file should be gone
        self.assertFalse((self.paths.meme_dir / "坏笑.webp").exists())

    def test_ingest_third_time_increments(self):
        """Third ingest adds (3) variant."""
        source1 = Path(self.temp_dir.name) / "s1.png"
        source2 = Path(self.temp_dir.name) / "s2.png"
        source3 = Path(self.temp_dir.name) / "s3.png"
        self._create_image(source1)
        self._create_image(source2, color="blue")
        self._create_image(source3, color="green")

        self.storage.ingest_meme("坏笑", source1)
        self.storage.ingest_meme("坏笑", source2)
        result3 = self.storage.ingest_meme("坏笑", source3)

        self.assertEqual(result3, self.paths.meme_dir / "坏笑" / "坏笑(3).webp")
        self.assertTrue(result3.exists())

    def test_get_last_move_info(self):
        """Move info is available after second ingest."""
        source1 = Path(self.temp_dir.name) / "s1.png"
        source2 = Path(self.temp_dir.name) / "s2.png"
        self._create_image(source1)
        self._create_image(source2, color="blue")

        self.storage.ingest_meme("坏笑", source1)
        self.storage.ingest_meme("坏笑", source2)

        move_info = self.storage.get_last_move_info()
        self.assertIsNotNone(move_info)
        old_path, new_path = move_info
        self.assertEqual(old_path, self.paths.meme_dir / "坏笑.webp")
        self.assertEqual(new_path, self.paths.meme_dir / "坏笑" / "坏笑.webp")


if __name__ == "__main__":
    unittest.main()
