import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from PIL import Image, UnidentifiedImageError

from astrbot.api import logger


@dataclass(slots=True)
class DuplicateMatch:
    matched_file: Path
    distance: int
    dhash: str


class DHashDedupService:
    def __init__(self, storage, threshold: int = 8):
        self.storage = storage
        self.threshold = threshold
        self.index_path = self.storage.paths.data_dir / "image_dhash_index.json"
        self.index: Dict[str, str] = {}

    def initialize(self) -> None:
        self.index = self._load_index()
        self._rebuild_missing_entries()

    def find_similar_duplicate(self, source_file: Path) -> Optional[DuplicateMatch]:
        candidate_hash = self.compute_dhash(source_file)
        if not candidate_hash:
            return None

        for file_path_str, existing_hash in self.index.items():
            file_path = Path(file_path_str)
            if not file_path.exists():
                continue
            distance = self.hamming_distance(candidate_hash, existing_hash)
            if distance <= self.threshold:
                return DuplicateMatch(
                    matched_file=file_path,
                    distance=distance,
                    dhash=existing_hash,
                )
        return None

    def register_file(self, file_path: Path) -> None:
        image_hash = self.compute_dhash(file_path)
        if not image_hash:
            return
        self.index[str(file_path.resolve())] = image_hash
        self._persist_index()

    def compute_dhash(self, image_path: Path) -> str:
        try:
            with Image.open(image_path) as image:
                image = image.convert("L")
                image = image.resize((9, 8), Image.Resampling.LANCZOS)
                pixels = list(image.getdata())

            diff = []
            width, height = 9, 8
            for row in range(height):
                for col in range(width - 1):
                    pixel_left_idx = row * width + col
                    pixel_right_idx = pixel_left_idx + 1
                    diff.append(pixels[pixel_left_idx] > pixels[pixel_right_idx])

            decimal_value = 0
            for index, value in enumerate(diff):
                if value:
                    decimal_value += 1 << index

            return hex(decimal_value)[2:]
        except (OSError, UnidentifiedImageError) as exc:
            logger.warning(f"AngelSmile: dHash 计算失败: {exc}")
            return ""

    def hamming_distance(self, left: str, right: str) -> int:
        max_len = max(len(left), len(right))
        left_bits = bin(int(left, 16))[2:].zfill(max_len * 4)
        right_bits = bin(int(right, 16))[2:].zfill(max_len * 4)
        return sum(bit_left != bit_right for bit_left, bit_right in zip(left_bits, right_bits))

    def _load_index(self) -> Dict[str, str]:
        if not self.index_path.exists():
            return {}
        try:
            raw_data = json.loads(self.index_path.read_text(encoding="utf-8"))
            if not isinstance(raw_data, dict):
                return {}
            normalized: Dict[str, str] = {}
            for raw_key, raw_value in raw_data.items():
                if isinstance(raw_key, str) and isinstance(raw_value, str):
                    normalized[str(Path(raw_key).resolve())] = raw_value
            return normalized
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning(f"AngelSmile: 读取 dHash 索引失败，已重建: {exc}")
            return {}

    def _rebuild_missing_entries(self) -> None:
        changed = False
        existing_files = {str(path.resolve()) for path in self.storage.iter_all_sticker_files()}

        for indexed_file in list(self.index):
            if indexed_file not in existing_files:
                self.index.pop(indexed_file, None)
                changed = True

        for file_path in self.storage.iter_all_sticker_files():
            resolved = str(file_path.resolve())
            if resolved not in self.index:
                image_hash = self.compute_dhash(file_path)
                if image_hash:
                    self.index[resolved] = image_hash
                    changed = True

        if changed:
            self._persist_index()

    def _persist_index(self) -> None:
        try:
            self.index_path.write_text(
                json.dumps(self.index, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning(f"AngelSmile: 持久化 dHash 索引失败: {exc}")
