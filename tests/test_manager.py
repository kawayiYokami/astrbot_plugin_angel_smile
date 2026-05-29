"""Integration tests for MemeManager ingest flow."""

import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from astrbot_plugin_angel_smile.tests._bootstrap import install_fake_astrbot

install_fake_astrbot()

from astrbot_plugin_angel_smile.models import PluginPaths  # noqa: E402
from astrbot_plugin_angel_smile.services.meme_manager import MemeManager  # noqa: E402
from astrbot_plugin_angel_smile.services.storage import MemeStorage  # noqa: E402


def _create_image(path: Path, color: str = "red", size=(64, 64)):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, color=color)
    draw = ImageDraw.Draw(img)
    # Add unique pattern based on color to ensure different dhashes
    if color == "red":
        draw.rectangle((4, 4, 60, 20), fill="blue")
    elif color == "blue":
        draw.ellipse((10, 10, 54, 54), fill="yellow")
    elif color == "green":
        draw.polygon(((4, 60), (32, 4), (60, 60)), fill="purple")
    img.save(path)


class MemeManagerTestCase(unittest.IsolatedAsyncioTestCase):
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
        self.paths.plugin_dir.mkdir(parents=True, exist_ok=True)
        self.paths.meme_dir.mkdir(parents=True, exist_ok=True)

        self.storage = MemeStorage(self.paths)
        self.storage.initialize()
        self.manager = MemeManager(self.storage)
        self.manager.initialize()

    async def test_first_ingest(self):
        """First ingest creates .meme/<emotion>.webp."""
        source = Path(self.temp_dir.name) / "img.png"
        _create_image(source)

        result = await self.manager.ingest_meme("坏笑", str(source))
        self.assertIn('"saved": true', result)
        self.assertTrue((self.paths.meme_dir / "坏笑.webp").exists())

    async def test_second_ingest_upgrades(self):
        """Second ingest upgrades to folder structure."""
        s1 = Path(self.temp_dir.name) / "s1.png"
        s2 = Path(self.temp_dir.name) / "s2.png"
        _create_image(s1, color="red")
        _create_image(s2, color="blue")

        await self.manager.ingest_meme("坏笑", str(s1))
        result = await self.manager.ingest_meme("坏笑", str(s2))

        self.assertIn('"saved": true', result)
        folder = self.paths.meme_dir / "坏笑"
        self.assertTrue(folder.is_dir())
        self.assertTrue((folder / "坏笑.webp").exists())
        self.assertTrue((folder / "坏笑(2).webp").exists())

    async def test_third_ingest_increments(self):
        """Third ingest adds (3) variant."""
        s1 = Path(self.temp_dir.name) / "s1.png"
        s2 = Path(self.temp_dir.name) / "s2.png"
        s3 = Path(self.temp_dir.name) / "s3.png"
        _create_image(s1, color="red")
        _create_image(s2, color="blue")
        _create_image(s3, color="green")

        await self.manager.ingest_meme("坏笑", str(s1))
        await self.manager.ingest_meme("坏笑", str(s2))
        result = await self.manager.ingest_meme("坏笑", str(s3))

        self.assertIn('"saved": true', result)
        self.assertTrue((self.paths.meme_dir / "坏笑" / "坏笑(3).webp").exists())

    async def test_duplicate_blocked(self):
        """Duplicate image is blocked by dhash."""
        source = Path(self.temp_dir.name) / "img.png"
        _create_image(source)

        await self.manager.ingest_meme("坏笑", str(source))

        # Try to ingest the same image again (even with different emotion name)
        result = await self.manager.ingest_meme("无语", str(source))
        self.assertIn('"duplicate": true', result)
        self.assertIn('"saved": false', result)

    async def test_dhash_path_updated_on_upgrade(self):
        """dHash index path is updated when single file moves to folder."""
        s1 = Path(self.temp_dir.name) / "s1.png"
        s2 = Path(self.temp_dir.name) / "s2.png"
        _create_image(s1, color="red")
        _create_image(s2, color="blue")

        await self.manager.ingest_meme("坏笑", str(s1))

        # Check that the original path is in the index
        old_rel = "坏笑.webp"
        self.assertIn(old_rel, self.manager.dedup.index)

        await self.manager.ingest_meme("坏笑", str(s2))

        # Old path should be gone, new path should exist
        new_rel = str(Path("坏笑") / "坏笑.webp")
        self.assertNotIn(old_rel, self.manager.dedup.index)
        self.assertIn(new_rel, self.manager.dedup.index)

    async def test_invalid_emotion_rejected(self):
        """Invalid emotion names are rejected."""
        source = Path(self.temp_dir.name) / "img.png"
        _create_image(source)

        result = await self.manager.ingest_meme(".hidden", str(source))
        self.assertIn('"ok": false', result)

        result = await self.manager.ingest_meme("", str(source))
        self.assertIn('"ok": false', result)

    async def test_tool_only_accepts_emotion_and_path(self):
        """Verify tool schema only has emotion and path."""
        from astrbot_plugin_angel_smile.tools.steal_meme import MemeIngestTool

        tool = MemeIngestTool()
        props = tool.parameters["properties"]
        self.assertEqual(set(props.keys()), {"emotion", "path"})
        self.assertEqual(tool.parameters["required"], ["emotion", "path"])

    async def test_orphan_hash_blocks_reingest(self):
        """After file deletion, orphan hash still blocks re-ingestion."""
        source = Path(self.temp_dir.name) / "img.png"
        _create_image(source)

        await self.manager.ingest_meme("坏笑", str(source))

        # "Delete" the meme file
        meme_file = self.paths.meme_dir / "坏笑.webp"
        self.assertTrue(meme_file.exists())
        meme_file.unlink()

        # Try to ingest the same image again
        result = await self.manager.ingest_meme("坏笑", str(source))
        self.assertIn('"duplicate": true', result)
        self.assertIn('"saved": false', result)


if __name__ == "__main__":
    unittest.main()
