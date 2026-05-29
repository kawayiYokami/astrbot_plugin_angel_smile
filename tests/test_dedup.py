import json
import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from astrbot_plugin_angel_smile.tests._bootstrap import install_fake_astrbot

install_fake_astrbot()

from astrbot_plugin_angel_smile.models import PluginPaths  # noqa: E402
from astrbot_plugin_angel_smile.services.dedup import DHashDedupService  # noqa: E402
from astrbot_plugin_angel_smile.services.storage import MemeStorage  # noqa: E402


def _create_pattern_image(
    path: Path,
    variant: str = "base",
    size: tuple[int, int] = (128, 128),
    quality: int | None = None,
):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(image)
    if variant == "base":
        draw.rectangle((8, 8, 120, 32), fill="red")
        draw.ellipse((24, 40, 96, 112), fill="blue")
        draw.line((0, 127, 127, 0), fill="black", width=4)
    elif variant == "different":
        draw.rectangle((12, 48, 116, 120), fill="black")
        draw.polygon(((8, 8), (120, 8), (64, 60)), fill="green")
        draw.line((0, 0, 127, 127), fill="blue", width=8)
    else:
        raise ValueError(f"unknown variant: {variant}")

    if path.suffix.lower() in {".jpg", ".jpeg"}:
        image.save(path, quality=quality or 85)
    else:
        image.save(path)


class DedupTestCase(unittest.TestCase):
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

    def test_register_and_find_similar_duplicate(self):
        service = DHashDedupService(self.storage, threshold=8)
        service.initialize()

        original = self.paths.meme_dir / "original.png"
        candidate = Path(self.temp_dir.name) / "candidate.jpg"

        _create_pattern_image(original, variant="base")
        # Create a slightly different version (resized)
        with Image.open(original) as source_image:
            source_image = source_image.resize((96, 96))
            source_image.save(candidate, quality=70)

        service.register_file(original)
        match = service.find_similar_duplicate(candidate)

        self.assertIsNotNone(match)
        assert match is not None
        self.assertLessEqual(match.distance, 8)

    def test_different_images_do_not_match(self):
        service = DHashDedupService(self.storage, threshold=6)
        service.initialize()

        original = self.paths.meme_dir / "original.png"
        different = Path(self.temp_dir.name) / "different.png"

        _create_pattern_image(original, variant="base")
        _create_pattern_image(different, variant="different")

        service.register_file(original)
        match = service.find_similar_duplicate(different)

        self.assertIsNone(match)

    def test_initialize_rebuilds_index_from_existing_files(self):
        original = self.paths.meme_dir / "original.png"
        _create_pattern_image(original, variant="base")

        service = DHashDedupService(self.storage)
        service.initialize()

        rel_path = str(original.resolve().relative_to(self.paths.meme_dir.resolve()))
        self.assertIn(rel_path, service.index)

    def test_orphan_entries_preserved(self):
        """Orphan dhash entries are NOT removed during rebuild."""
        service = DHashDedupService(self.storage, threshold=8)

        # Pre-populate index with an orphan entry
        orphan_rel = "deleted_meme.webp"
        orphan_hash = "abcdef1234567890"
        service.index_path.parent.mkdir(parents=True, exist_ok=True)
        service.index_path.write_text(
            json.dumps({orphan_rel: orphan_hash}, ensure_ascii=False),
            encoding="utf-8",
        )

        service.initialize()

        # Orphan should still be in the index
        self.assertIn(orphan_rel, service.index)
        self.assertEqual(service.index[orphan_rel], orphan_hash)

    def test_orphan_blocks_reingest(self):
        """Orphan hash blocks re-ingestion of the same image."""
        service = DHashDedupService(self.storage, threshold=8)

        # Create an image and register it
        original = self.paths.meme_dir / "test.png"
        _create_pattern_image(original, variant="base")
        service.initialize()
        service.register_file(original)

        # Now "delete" the file but keep the hash
        original.unlink()

        # Try to ingest the same image again from a different path
        candidate = Path(self.temp_dir.name) / "same_image.png"
        _create_pattern_image(candidate, variant="base")

        match = service.find_similar_duplicate(candidate)
        self.assertIsNotNone(match)

    def test_update_path(self):
        """update_path correctly moves the index entry."""
        service = DHashDedupService(self.storage, threshold=8)
        service.initialize()

        original = self.paths.meme_dir / "坏笑.webp"
        _create_pattern_image(original, variant="base")
        service.register_file(original)

        old_rel = str(original.resolve().relative_to(self.paths.meme_dir.resolve()))
        self.assertIn(old_rel, service.index)

        new_path = self.paths.meme_dir / "坏笑" / "坏笑.webp"
        new_path.parent.mkdir(parents=True, exist_ok=True)
        original.rename(new_path)

        service.update_path(original, new_path)

        new_rel = str(new_path.resolve().relative_to(self.paths.meme_dir.resolve()))
        self.assertNotIn(old_rel, service.index)
        self.assertIn(new_rel, service.index)


if __name__ == "__main__":
    unittest.main()
