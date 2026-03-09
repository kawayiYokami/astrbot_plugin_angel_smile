import json
import random
import shutil
import time
from pathlib import Path
from typing import Dict, Optional

from astrbot.api import logger

from ..constants import SUPPORTED_IMAGE_SUFFIXES
from ..models import MemeSaveResult, PluginPaths
from ..utils import safe_filename


class MemeStorage:
    def __init__(self, paths: PluginPaths):
        self.paths = paths
        self.stickers_data: Dict[str, str] = {}

    def initialize(self) -> None:
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)

        if not self.paths.stickers_data_file.exists():
            source = self.paths.default_dir / "memes_data.json"
            if source.exists():
                shutil.copy2(source, self.paths.stickers_data_file)
            else:
                self.paths.stickers_data_file.write_text("{}\n", encoding="utf-8")

        if not self.paths.stickers_dir.exists():
            self.paths.stickers_dir.mkdir(parents=True, exist_ok=True)
            source_memes = self.paths.default_dir / "memes"
            if source_memes.exists():
                for child in source_memes.iterdir():
                    if child.is_dir():
                        shutil.copytree(child, self.paths.stickers_dir / child.name, dirs_exist_ok=True)

        self.load_stickers_data()

    def load_stickers_data(self) -> Dict[str, str]:
        try:
            if self.paths.stickers_data_file.exists():
                self.stickers_data = json.loads(self.paths.stickers_data_file.read_text(encoding="utf-8"))
            else:
                self.stickers_data = {}
            logger.info(f"AngelSmile: 已加载 {len(self.stickers_data)} 个表情分类")
        except json.JSONDecodeError as exc:
            logger.error(f"AngelSmile: 表情数据文件格式错误: {exc}")
            self.stickers_data = {}
        except Exception as exc:
            logger.error(f"AngelSmile: 加载表情数据失败: {exc}", exc_info=True)
            self.stickers_data = {}
        return self.stickers_data

    def persist(self) -> None:
        self.paths.stickers_data_file.write_text(
            json.dumps(self.stickers_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def has_sticker_assets(self, category: str) -> bool:
        sticker_dir = self.paths.stickers_dir / category
        if not sticker_dir.exists() or not sticker_dir.is_dir():
            return False
        return any(
            path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
            for path in sticker_dir.iterdir()
        )

    def get_available_stickers_data(self) -> Dict[str, str]:
        return {
            category: description
            for category, description in self.stickers_data.items()
            if self.has_sticker_assets(category)
        }

    def get_catalog_stickers_data(self) -> Dict[str, str]:
        return dict(self.stickers_data)

    def get_random_sticker_path(self, category: str) -> Optional[str]:
        sticker_dir = self.paths.stickers_dir / category
        if not sticker_dir.exists() or not sticker_dir.is_dir():
            return None
        image_files = [
            path for path in sticker_dir.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        ]
        if not image_files:
            return None
        return str(random.choice(image_files))

    def save_meme(
        self,
        source_file: Path,
        category: str,
        description: str,
        reason: str,
        save_name: Optional[str] = None,
        overwrite_description: bool = False,
    ) -> MemeSaveResult:
        target_dir = self.paths.stickers_dir / category
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / safe_filename(save_name, source_file.suffix.lower())
        if target_file.exists():
            target_file = target_dir / f"{target_file.stem}_{int(time.time())}{target_file.suffix}"

        shutil.copy2(source_file, target_file)
        if category not in self.stickers_data:
            self.stickers_data[category] = description
        elif overwrite_description:
            self.stickers_data[category] = description
        self.persist()

        return MemeSaveResult(
            category=category,
            description=self.stickers_data.get(category, description),
            saved_file=target_file,
            reason=reason,
        )
