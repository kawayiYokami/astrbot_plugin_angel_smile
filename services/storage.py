"""Meme storage: scanning, indexing, and file operations for .meme/ directory."""

import re
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional

from astrbot.api import logger

from ..constants import DHASH_INDEX_FILENAME, SUPPORTED_IMAGE_SUFFIXES
from ..models import PluginPaths
from ..utils import is_valid_meme_name

# Cache TTL in seconds
_CACHE_TTL = 300  # 5 minutes


class MemeStorage:
    """Manages the .meme/ directory structure and provides in-memory index."""

    def __init__(self, paths: PluginPaths):
        self.paths = paths
        self._cached_index: Optional[Dict[str, List[Path]]] = None
        self._cache_time: float = 0.0

    def initialize(self) -> None:
        self.paths.meme_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # In-memory index: cached with 5-minute TTL
    # ------------------------------------------------------------------

    def invalidate_cache(self) -> None:
        """Force next access to re-scan the directory."""
        self._cached_index = None
        self._cache_time = 0.0

    def scan_meme_index(self) -> Dict[str, List[Path]]:
        """Return cached meme index, re-scanning if expired or invalidated.

        Cache TTL: 5 minutes. Also invalidated explicitly after ingest.
        """
        now = time.time()
        if self._cached_index is not None and (now - self._cache_time) < _CACHE_TTL:
            return self._cached_index

        index = self._do_scan()
        self._cached_index = index
        self._cache_time = now
        return index

    def _do_scan(self) -> Dict[str, List[Path]]:
        """Scan .meme/ and return {meme_name: [variant_paths...]}.

        Rules:
        - Root image files: stem is meme name, single variant.
        - First-level folders: folder name is meme name, images inside are variants.
        - Folder takes priority over same-name root file.
        - Ignores: dhash index file, non-image files, deeper directories, invalid names.
        - Meme names sorted lexicographically; variants sorted by filename.
        """
        index: Dict[str, List[Path]] = {}
        meme_dir = self.paths.meme_dir

        if not meme_dir.exists():
            return index

        folder_names: set[str] = set()

        # Pass 1: first-level folders
        for entry in sorted(meme_dir.iterdir()):
            if not entry.is_dir():
                continue
            name = entry.name
            if not is_valid_meme_name(name):
                continue
            folder_names.add(name)
            variants = sorted(
                p for p in entry.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
            )
            if variants:
                index[name] = variants

        # Pass 2: root image files (skip if folder with same stem exists)
        for entry in sorted(meme_dir.iterdir()):
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
                continue
            if entry.name == DHASH_INDEX_FILENAME:
                continue
            stem = entry.stem
            if not is_valid_meme_name(stem):
                continue
            if stem in folder_names:
                # Folder takes priority; root file is legacy
                continue
            index[stem] = [entry]

        return dict(sorted(index.items()))

    def get_available_meme_names(self) -> List[str]:
        """Return sorted list of available meme names."""
        return list(self.scan_meme_index().keys())

    def get_variants(self, meme_name: str) -> List[Path]:
        """Get variant paths for a specific meme name."""
        index = self.scan_meme_index()
        return index.get(meme_name, [])

    # ------------------------------------------------------------------
    # Ingest: add a new image to .meme/
    # ------------------------------------------------------------------

    def ingest_meme(self, emotion: str, source_file: Path) -> Path:
        """Ingest a source image into .meme/ as WebP.

        Handles the progression:
        1. First time: .meme/<emotion>.webp
        2. Second time: create folder, move old file, add new as (2)
        3. Subsequent: add next numbered variant

        Returns the path of the newly saved file.
        Invalidates the in-memory cache after write.
        """
        meme_dir = self.paths.meme_dir
        single_file = meme_dir / f"{emotion}.webp"
        folder = meme_dir / emotion

        if folder.exists() and folder.is_dir():
            # Folder already exists: add next variant
            target = self._next_variant_path(folder, emotion)
            self._convert_to_webp(source_file, target)
            self.invalidate_cache()
            return target

        if single_file.exists():
            # Single file exists: upgrade to folder structure
            folder.mkdir(parents=True, exist_ok=True)
            moved_path = folder / f"{emotion}.webp"
            shutil.move(str(single_file), str(moved_path))
            # Notify caller about the move for dhash path update
            self._last_moved_from = single_file
            self._last_moved_to = moved_path

            target = folder / f"{emotion}(2).webp"
            self._convert_to_webp(source_file, target)
            self.invalidate_cache()
            return target

        # First time: save as single root file
        self._last_moved_from = None
        self._last_moved_to = None
        self._convert_to_webp(source_file, single_file)
        self.invalidate_cache()
        return single_file

    def get_last_move_info(self) -> Optional[tuple[Path, Path]]:
        """Return (old_path, new_path) if the last ingest moved an existing file."""
        old = getattr(self, "_last_moved_from", None)
        new = getattr(self, "_last_moved_to", None)
        if old and new:
            return (old, new)
        return None

    def _next_variant_path(self, folder: Path, emotion: str) -> Path:
        """Find the next available variant filename in a folder.

        Naming: <emotion>.webp, <emotion>(2).webp, <emotion>(3).webp, ...
        """
        existing = {p.name for p in folder.iterdir() if p.is_file()}

        # Check if base name is available
        base_name = f"{emotion}.webp"
        if base_name not in existing:
            return folder / base_name

        # Find next available number starting from (2)
        n = 2
        while True:
            candidate = f"{emotion}({n}).webp"
            if candidate not in existing:
                return folder / candidate
            n += 1

    def _convert_to_webp(self, source: Path, target: Path) -> None:
        """Convert source image to WebP and save to target path."""
        from PIL import Image

        try:
            with Image.open(source) as img:
                # Convert to RGBA to handle transparency, then save as WebP
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")
                img.save(target, format="WEBP", quality=85)
        except Exception as exc:
            logger.error(f"AngelSmile: WebP 转换失败: {exc}")
            # Fallback: just copy the file
            shutil.copy2(source, target)

    # ------------------------------------------------------------------
    # Utility: iterate all sticker files (for dhash rebuild)
    # ------------------------------------------------------------------

    def iter_all_sticker_files(self) -> list[Path]:
        """Iterate all image files in .meme/ (root + first-level folders only)."""
        if not self.paths.meme_dir.exists():
            return []

        files: list[Path] = []
        meme_dir = self.paths.meme_dir

        for entry in meme_dir.iterdir():
            if entry.is_file() and entry.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
                if entry.name != DHASH_INDEX_FILENAME:
                    files.append(entry)
            elif entry.is_dir() and is_valid_meme_name(entry.name):
                for sub in entry.iterdir():
                    if sub.is_file() and sub.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
                        files.append(sub)

        return files
