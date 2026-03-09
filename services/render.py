import re
from typing import List

from astrbot.api import logger
from astrbot.core.message.components import Image, Plain

from ..utils import remove_sticker_tags


class StickerRenderer:
    def __init__(self, storage):
        self.storage = storage

    def build_sticker_list(self) -> str:
        available_stickers = self.storage.get_available_stickers_data()
        return "\n".join(
            f"- :{name}: {description}" for name, description in available_stickers.items()
        )

    def build_prompt_catalog(self) -> str:
        available = self.storage.get_available_stickers_data()
        catalog = self.storage.get_catalog_stickers_data()
        unavailable = {
            name: description
            for name, description in catalog.items()
            if name not in available
        }

        sections = []
        if available:
            sections.append(
                "可用表情：\n" + "\n".join(
                    f"- :{name}: {description}" for name, description in available.items()
                )
            )
        if unavailable:
            sections.append(
                "暂不可用的表情（当前分类下暂无素材）：\n" + "\n".join(
                    f"- {name}: {description}" for name, description in unavailable.items()
                )
            )
        return "\n\n".join(sections)

    def clean_response_text(self, text: str) -> str:
        return remove_sticker_tags(text)

    async def render_text(self, text: str) -> List:
        components = []
        try:
            pattern = r"(:([a-zA-Z0-9_\-\u4e00-\u9fff]+):)"
            parts = re.split(pattern, text, flags=re.DOTALL)
            i = 0
            while i < len(parts):
                part = parts[i]
                if not part or not part.strip():
                    i += 1
                    continue

                if i + 1 < len(parts) and part.startswith(":") and part.endswith(":"):
                    sticker_name = parts[i + 1]
                    if sticker_name in self.storage.get_available_stickers_data():
                        image_path = self.storage.get_random_sticker_path(sticker_name)
                        if image_path:
                            components.append(Image.fromFileSystem(image_path))
                    i += 2
                    continue

                components.append(Plain(part))
                i += 1
        except Exception as exc:
            logger.error(f"AngelSmile: 处理表情标签时出错: {exc}", exc_info=True)
            if text.strip():
                components.append(Plain(text.strip()))
        return components
