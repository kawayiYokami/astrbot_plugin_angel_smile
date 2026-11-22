"""StickerRenderer: resolves :meme_name: tokens in LLM output to images."""

import asyncio
import base64
import random
import re
from pathlib import Path
from typing import List

from astrbot.api import logger
from astrbot.core.message.components import (
    BaseMessageComponent,
    ComponentType,
    Image,
    Plain,
)


class StickerImage(BaseMessageComponent):
    """以 OneBot 表情样式（image 段 sub_type=1）发送的图片段。

    刻意不继承 Image：aiocqhttp 发送侧的 _from_segment_to_dict 对 Image 走
    base64 硬编码分支，sub_type / summary 会被丢弃；非 Image 类型则落到
    segment.toDict() 兜底，原样透传给协议端。

    file 必须在构造前就备成 base64:// 或可访问 URL——兜底调用的是同步
    toDict()，里面不能 await。
    """

    type: ComponentType = ComponentType.Image
    file: str = ""
    sub_type: int = 1
    summary: str = "[动画表情]"

    def toDict(self) -> dict:
        return {
            "type": "image",
            "data": {
                "file": self.file,
                "sub_type": self.sub_type,
                "summary": self.summary,
            },
        }


def register_sticker_component() -> bool:
    """把 StickerImage 登记进框架的空消息校验表。

    RespondStage._is_empty_message_chain 用 type(comp) 精确匹配组件类来判断
    消息是否为空；StickerImage 不在表里会被整条丢弃（日志：
    "The message is empty; skipping the respond stage."）。

    Returns:
        True 表示注册成功，可以按表情样式发送。
    """
    try:
        from astrbot.core.pipeline.respond.stage import RespondStage

        RespondStage._component_validators[StickerImage] = lambda comp: bool(comp.file)
        return True
    except Exception as exc:  # pragma: no cover - 依赖框架内部结构
        logger.warning(f"AngelSmile: 注册表情组件校验器失败，退回普通图片: {exc}")
        return False


def unregister_sticker_component() -> None:
    """撤销 register_sticker_component 的注册。"""
    try:
        from astrbot.core.pipeline.respond.stage import RespondStage

        RespondStage._component_validators.pop(StickerImage, None)
    except Exception:  # pragma: no cover - 框架结构变化时静默
        pass


# 贴纸标记两侧可能被 LLM 套上的包裹符号。只有成对出现才剥，单侧一律不动，
# 避免误伤正文里本来就在用的括号。
_WRAPPER_PAIRS = {
    "[": "]",
    "【": "】",
    "（": "）",
    "(": ")",
    "「": "」",
    "『": "』",
    "“": "”",
}


def _expand_wrapper(text: str, start: int, end: int) -> tuple[int, int]:
    """把紧贴贴纸标记的成对包裹符号一并纳入替换范围。

    LLM 常写成 ``[:坏笑:]``、``【:坏笑:】`` 这类形式，只替换 ``:坏笑:``
    会在消息里留下孤零零的括号。这里只在两侧确实成对时向外扩一格。
    """
    if start > 0 and end < len(text):
        opener, closer = text[start - 1], text[end]
        if _WRAPPER_PAIRS.get(opener) == closer:
            return start - 1, end + 1
    return start, end


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

    async def _build_image(self, path: Path, sticker_style: bool):
        """构造贴纸组件。

        sticker_style 为 True 时走 OneBot 表情样式（image 段 sub_type=1），
        否则维持普通图片。读取失败时退回普通图片，不拖垮整条回复。
        """
        if not sticker_style:
            return Image.fromFileSystem(str(path))
        try:
            raw = await asyncio.to_thread(path.read_bytes)
        except OSError as exc:
            logger.warning(f"AngelSmile: 读取贴纸失败，退回普通图片 {path}: {exc}")
            return Image.fromFileSystem(str(path))
        return StickerImage(file=f"base64://{base64.b64encode(raw).decode()}")

    async def render_text(
        self, text: str, sticker_style: bool = False
    ) -> List:
        """Replace :meme_name: tokens with Image components.

        Args:
            sticker_style: True 时贴纸按 OneBot 表情样式发送（仅 aiocqhttp
                平台有意义），否则发送普通图片。
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

            for match in pattern.finditer(text):
                meme_name = match.group(1)
                variants = index.get(meme_name, [])
                start, end = match.start(), match.end()
                if variants:
                    start, end = _expand_wrapper(text, start, end)

                if start > last_end:
                    components.append(Plain(text[last_end:start]))

                if variants:
                    selected = random.choice(variants)
                    components.append(await self._build_image(selected, sticker_style))
                else:
                    components.append(Plain(match.group(0)))

                last_end = end

            if last_end < len(text):
                components.append(Plain(text[last_end:]))
        except Exception as exc:
            logger.error(f"AngelSmile: 处理表情标签时出错: {exc}", exc_info=True)
            components = [Plain(text)]
        return components
