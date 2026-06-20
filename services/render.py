"""StickerRenderer: resolves :meme_name: tokens in LLM output to images."""

import re
from typing import List

from astrbot.api import logger
from astrbot.core.message.components import Image, Plain

from ..utils import stable_select


class StickerRenderer:
    def __init__(self, storage):
        self.storage = storage

    def build_prompt_injection(self) -> str:
        """Build the prompt text to inject into system prompt.

        Lists available meme names directly. No category/description structure.
        """
        names = self.storage.get_available_meme_names()
        if not names:
            return (
                "当前没有可用 meme。\n"
                "如果上下文里有适合做贴纸的图片路径，可以调用 `meme` 工具收入库存。"
            )
        name_list = "、".join(names)
        # 从真实可用名字里挑前 3 个做示例，避免出现"meme名/贴纸名"等占位符让弱模型照抄
        examples = "  ".join(f":{n}:" for n in names[:3])
        return (
            f"当前可用 meme：{name_list}。\n"
            "如果你要发送贴纸，请直接在回答正文中写贴纸格式，名字必须从上面的清单里挑。\n"
            f"示例：{examples}\n"
            "错误写法：`:meme名:`、`:贴纸名:`、`:<名字>:`（这些都是占位符，不要照抄字面）。\n"
            "不要编造不存在的 meme 名，也不要调用工具查询列表。\n"
            "只有当你需要把当前看到的图片收进贴纸库时，才调用 `meme` 工具。"
        )

    def build_tool_description(self) -> str:
        """Build the meme tool description including available meme list."""
        names = self.storage.get_available_meme_names()
        if names:
            name_list = "、".join(names)
            return (
                f"把图片收入贴纸库。当前可用 meme：{name_list}。\n"
                "聊天时如需发送贴纸，直接输出 :meme名:，例如 :坏笑:。\n"
                "不要调用本工具查询列表；只有需要新增贴纸库存时才调用。\n"
                "参数：emotion 为贴纸名，path 为图片路径。"
            )
        return (
            "把图片收入贴纸库。当前没有可用 meme。\n"
            "参数：emotion 为贴纸名，path 为图片路径。"
        )

    async def render_text(self, text: str, message_id: str = "") -> List:
        """Replace :meme_name: tokens with Image components.

        Uses stable_select for deterministic variant choice.
        """
        components: List = []
        try:
            index = self.storage.scan_meme_index()
            if not index:
                return [Plain(text)]

            # Build regex matching only available meme names
            names = sorted((re.escape(name) for name in index), key=len, reverse=True)
            pattern = re.compile(r":(" + "|".join(names) + r"):")
            last_end = 0
            token_counter = 0

            for match in pattern.finditer(text):
                if match.start() > last_end:
                    components.append(Plain(text[last_end:match.start()]))

                meme_name = match.group(1)
                variants = index.get(meme_name, [])
                if variants:
                    selected = stable_select(variants, message_id, meme_name, token_counter)
                    components.append(Image.fromFileSystem(str(selected)))
                else:
                    components.append(Plain(match.group(0)))

                token_counter += 1
                last_end = match.end()

            if last_end < len(text):
                components.append(Plain(text[last_end:]))
        except Exception as exc:
            logger.error(f"AngelSmile: 处理表情标签时出错: {exc}", exc_info=True)
            components = [Plain(text)]
        return components
