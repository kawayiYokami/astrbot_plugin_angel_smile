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
            stickers_dir=root / "data" / "memes",
            stickers_data_file=root / "data" / "memes_data.json",
            default_dir=root / "plugin" / "default",
        )
        self.paths.stickers_dir.mkdir(parents=True, exist_ok=True)
        self.storage = MemeStorage(self.paths)
        self.storage.stickers_data = {"happy": "开心"}

    def test_register_and_find_similar_duplicate(self):
        service = DHashDedupService(self.storage, threshold=8)
        service.initialize()

        base_dir = self.paths.stickers_dir / "happy"
        base_dir.mkdir(parents=True, exist_ok=True)
        original = base_dir / "original.png"
        candidate = self.paths.data_dir / "candidate.jpg"
        candidate.parent.mkdir(parents=True, exist_ok=True)

        _create_pattern_image(original, variant="base")
        with Image.open(original) as source_image:
            source_image = source_image.resize((96, 96))
            source_image.save(candidate, quality=70)

        service.register_file(original)
        match = service.find_similar_duplicate(candidate)

        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.matched_file.resolve(), original.resolve())
        self.assertLessEqual(match.distance, 8)

    def test_different_images_do_not_match(self):
        service = DHashDedupService(self.storage, threshold=6)
        service.initialize()

        base_dir = self.paths.stickers_dir / "happy"
        base_dir.mkdir(parents=True, exist_ok=True)
        original = base_dir / "original.png"
        different = self.paths.data_dir / "different.png"
        different.parent.mkdir(parents=True, exist_ok=True)

        _create_pattern_image(original, variant="base")
        _create_pattern_image(different, variant="different")

        service.register_file(original)
        match = service.find_similar_duplicate(different)

        self.assertIsNone(match)

    def test_initialize_rebuilds_index_from_existing_files(self):
        base_dir = self.paths.stickers_dir / "happy"
        base_dir.mkdir(parents=True, exist_ok=True)
        original = base_dir / "original.png"
        _create_pattern_image(original, variant="base")

        service = DHashDedupService(self.storage)
        service.initialize()

        self.assertIn(str(original.resolve()), service.index)


if __name__ == "__main__":
    unittest.main()
