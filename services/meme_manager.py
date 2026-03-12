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
    normalize_category_name,
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
            # Windows 兼容: file:///d:/path -> /d:/path -> d:/path
            if len(local_path) > 2 and local_path[0] == "/" and local_path[2] == ":":
                local_path = local_path[1:]
            return resolve_user_path(local_path), False

        return resolve_user_path(text), False

    async def steal_meme(
        self,
        image_path: str,
        category: str,
        description: Optional[str] = None,
        save_name: Optional[str] = None,
    ) -> str:
        raw_path, from_url = await self._resolve_image_ref(image_path)
        if raw_path is None:
            return f"无法解析图片引用: {image_path}"

        if not raw_path.exists() or not raw_path.is_file():
            return f"图片不存在或不是文件: {raw_path}"

        if not is_path_within_roots(raw_path, self.allowed_image_roots):
            return "图片路径不在允许的目录范围内。"

        suffix = raw_path.suffix.lower()
        if suffix not in SUPPORTED_IMAGE_SUFFIXES:
            return f"暂不支持的图片格式: {suffix or '无扩展名'}"

        if not category.strip():
            return "缺少 category。请先根据分类目录选择一个分类，再调用图片入库工具保存。"

        final_category = normalize_category_name(category)
        final_description = str(
            description
            or self.storage.get_catalog_description(final_category)
            or "手动指定分类导入的表情包"
        ).strip()
        reason = "手动指定分类"
        overwrite_description = bool(description)

        async with self.write_lock:
            duplicate = self.dedup.find_similar_duplicate(raw_path)
            if duplicate is not None:
                return MemeToolResult(
                    ok=True,
                    saved=False,
                    category=final_category,
                    description=final_description,
                    message="这个表情包已经偷过了",
                    reason="这个表情包已经偷过了",
                    duplicate=True,
                    duplicate_type="similar",
                    matched_file=str(duplicate.matched_file),
                    distance=duplicate.distance,
                ).to_message()

            result = self.storage.save_meme(
                source_file=Path(raw_path),
                category=final_category,
                description=final_description,
                reason=reason,
                save_name=save_name,
                overwrite_description=overwrite_description,
            )
            self.dedup.register_file(result.saved_file)

        if from_url:
            logger.info("AngelSmile: 已从 URL 下载并保存表情: %s", image_path)

        return result.to_tool_result().to_message()
