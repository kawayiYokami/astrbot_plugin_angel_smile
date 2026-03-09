from asyncio import Lock
from pathlib import Path
from typing import Optional

from ..constants import SUPPORTED_IMAGE_SUFFIXES
from ..utils import (
    get_allowed_image_roots,
    is_path_within_roots,
    normalize_category_name,
    resolve_user_path,
)


class MemeManager:
    def __init__(self, storage):
        self.storage = storage
        self.write_lock = Lock()
        self.allowed_image_roots = get_allowed_image_roots(
            extra_roots=(self.storage.paths.plugin_dir, self.storage.paths.data_dir)
        )

    async def steal_meme(
        self,
        image_path: str,
        category: str,
        description: Optional[str] = None,
        save_name: Optional[str] = None,
    ) -> str:
        raw_path = resolve_user_path(image_path)
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
            result = self.storage.save_meme(
                source_file=Path(raw_path),
                category=final_category,
                description=final_description,
                reason=reason,
                save_name=save_name,
                overwrite_description=overwrite_description,
            )

        return result.to_message()
