import re
from typing import List

from astrbot.api import logger
from astrbot.core.message.components import Image, Plain


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

    async def render_text(self, text: str) -> List:
        components = []
        try:
            available_stickers = self.storage.get_available_stickers_data()
            pattern = re.compile(r":([a-zA-Z0-9_\-\u4e00-\u9fff]+):")
            last_end = 0

            for match in pattern.finditer(text):
                if match.start() > last_end:
                    components.append(Plain(text[last_end:match.start()]))

                sticker_name = match.group(1)
                if sticker_name in available_stickers:
                    image_path = self.storage.get_random_sticker_path(sticker_name)
                    if image_path:
                        components.append(Image.fromFileSystem(image_path))
                    else:
                        components.append(Plain(match.group(0)))
                else:
                    components.append(Plain(match.group(0)))

                last_end = match.end()

            if last_end < len(text):
                components.append(Plain(text[last_end:]))
        except Exception as exc:
            logger.error(f"AngelSmile: 处理表情标签时出错: {exc}", exc_info=True)
            components.append(Plain(text))
        return components
