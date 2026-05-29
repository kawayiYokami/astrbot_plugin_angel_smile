"""MemeManager: orchestrates meme ingestion with dedup checking."""

from asyncio import Lock
from pathlib import Path
from typing import Optional

from astrbot.api import logger
from astrbot.core.utils.io import download_image_by_url

from ..constants import SUPPORTED_IMAGE_SUFFIXES
from ..models import MemeToolResult
from ..utils import (
    get_allowed_image_roots,
    is_path_within_roots,
    is_valid_meme_name,
    resolve_user_path,
)
from .dedup import DHashDedupService


class MemeManager:
    def __init__(self, storage):
        self.storage = storage
        self.write_lock = Lock()
        self.dedup = DHashDedupService(storage=self.storage)
        self.allowed_image_roots = get_allowed_image_roots(
            extra_roots=(self.storage.paths.plugin_dir, self.storage.paths.data_dir)
        )

    def initialize(self) -> None:
        self.dedup.initialize()

    async def _resolve_image_ref(self, image_ref: str) -> tuple[Optional[Path], bool]:
        """Resolve image reference into a local file path.

        Returns:
            (path, downloaded_from_url)
        """
        text = (image_ref or "").strip()
        if not text:
            return None, False

        if text.startswith("http://") or text.startswith("https://"):
            try:
                downloaded = await download_image_by_url(text)
                return resolve_user_path(downloaded), True
            except Exception as exc:  # noqa: BLE001
                logger.warning("AngelSmile: 下载图片失败 %s: %s", text, exc)
                return None, True

        if text.startswith("file:///"):
            local_path = text[8:]
            # Windows: file:///d:/path -> /d:/path -> d:/path
            if len(local_path) > 2 and local_path[0] == "/" and local_path[2] == ":":
                local_path = local_path[1:]
            return resolve_user_path(local_path), False

        return resolve_user_path(text), False

    async def ingest_meme(self, emotion: str, path: str) -> str:
        """Ingest a meme image into .meme/ directory.

        Args:
            emotion: The meme name (used as :emotion: token in chat).
            path: Image reference (local path, file:/// or http(s) URL).

        Returns:
            JSON string with operation result.
        """
        if not is_valid_meme_name(emotion):
            return MemeToolResult(
                ok=False, saved=False, emotion=emotion,
                message=f"无效的表情名: {emotion}",
            ).to_message()

        raw_path, from_url = await self._resolve_image_ref(path)
        if raw_path is None:
            return MemeToolResult(
                ok=False, saved=False, emotion=emotion,
                message=f"无法解析图片引用: {path}",
            ).to_message()

        if not raw_path.exists() or not raw_path.is_file():
            return MemeToolResult(
                ok=False, saved=False, emotion=emotion,
                message=f"图片不存在或不是文件: {raw_path}",
            ).to_message()

        if not is_path_within_roots(raw_path, self.allowed_image_roots):
            return MemeToolResult(
                ok=False, saved=False, emotion=emotion,
                message="图片路径不在允许的目录范围内。",
            ).to_message()

        suffix = raw_path.suffix.lower()
        if suffix not in SUPPORTED_IMAGE_SUFFIXES:
            return MemeToolResult(
                ok=False, saved=False, emotion=emotion,
                message=f"暂不支持的图片格式: {suffix or '无扩展名'}",
            ).to_message()

        async with self.write_lock:
            # Dedup check
            duplicate = self.dedup.find_similar_duplicate(raw_path)
            if duplicate is not None:
                return MemeToolResult(
                    ok=True, saved=False, emotion=emotion,
                    message="这个表情包已经收过了",
                    duplicate=True,
                    matched_file=str(duplicate.matched_file),
                    distance=duplicate.distance,
                ).to_message()

            # Ingest
            saved_file = self.storage.ingest_meme(emotion, raw_path)

            # Update dhash index for moved file (single->folder upgrade)
            move_info = self.storage.get_last_move_info()
            if move_info:
                old_path, new_path = move_info
                self.dedup.update_path(old_path, new_path)

            # Register new file
            self.dedup.register_file(saved_file)

        if from_url:
            logger.info("AngelSmile: 已从 URL 下载并保存表情: %s", path)

        return MemeToolResult(
            ok=True, saved=True, emotion=emotion,
            saved_file=saved_file,
            message="成功",
        ).to_message()
