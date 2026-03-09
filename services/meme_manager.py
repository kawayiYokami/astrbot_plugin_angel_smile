from asyncio import Lock
from pathlib import Path
from typing import Optional

from astrbot.api.event import AstrMessageEvent

from ..constants import SUPPORTED_IMAGE_SUFFIXES
from ..utils import normalize_category_name, resolve_user_path


class MemeManager:
    def __init__(self, storage):
        self.storage = storage
        self.write_lock = Lock()

    async def steal_meme(
        self,
        event: AstrMessageEvent,
        image_path: str,
        category: Optional[str] = None,
        description: Optional[str] = None,
        save_name: Optional[str] = None,
    ) -> str:
        raw_path = resolve_user_path(image_path)
        if not raw_path.exists() or not raw_path.is_file():
            return f"图片不存在或不是文件: {raw_path}"

        suffix = raw_path.suffix.lower()
        if suffix not in SUPPORTED_IMAGE_SUFFIXES:
            return f"暂不支持的图片格式: {suffix or '无扩展名'}"

        if not category or not str(category).strip():
            return "缺少 category。请先根据分类目录选择一个分类，再调用图片入库工具保存。"

        final_category = normalize_category_name(category)
        final_description = (description or self.storage.stickers_data.get(final_category) or "手动指定分类导入的表情包").strip()
        reason = "手动指定分类"
        overwrite_description = bool(description)

        async with self.write_lock:
            result = self.storage.save_meme(
                source_file=Path(raw_path),
                category=final_category,
                description=final_description,
                reason=reason,
                save_name=save_name,
                overwrite_description=overwrite_description,
            )

        return result.to_message()
