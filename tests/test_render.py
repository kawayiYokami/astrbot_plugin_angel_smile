import tempfile
import unittest
from pathlib import Path

from astrbot_plugin_angel_smile.tests._bootstrap import install_fake_astrbot

install_fake_astrbot()

from astrbot.core.message.components import Image, Plain  # noqa: E402
from astrbot_plugin_angel_smile.services.render import (  # noqa: E402
    StickerImage,
    StickerRenderer,
    register_sticker_component,
)


class _FakeStorage:
    def __init__(self):
        self._index = {
            "坏笑": [Path("/tmp/.meme/坏笑.webp")],
            "无语": [Path("/tmp/.meme/无语/无语.webp"), Path("/tmp/.meme/无语/无语(2).webp")],
        }

    def scan_meme_index(self):
        return self._index

    def get_available_meme_names(self):
        return sorted(self._index.keys())


class RenderTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_non_sticker_colon_text_keeps_single_plain_component(self):
        renderer = StickerRenderer(storage=_FakeStorage())
        text = "下次执行时间：2026-03-20 12:00:00"

        components = await renderer.render_text(text)

        self.assertEqual(len(components), 1)
        self.assertIsInstance(components[0], Plain)
        self.assertEqual(components[0].text, text)

    async def test_available_sticker_replaced_by_image(self):
        renderer = StickerRenderer(storage=_FakeStorage())
        text = "你好 :坏笑: 世界"

        components = await renderer.render_text(text)

        self.assertEqual(len(components), 3)
        self.assertIsInstance(components[0], Plain)
        self.assertEqual(components[0].text, "你好 ")
        self.assertIsInstance(components[1], Image)
        self.assertIsInstance(components[2], Plain)
        self.assertEqual(components[2].text, " 世界")

    async def test_multi_variant_sticker_picks_from_variants(self):
        """多变体贴纸随机取其中一张，多次渲染应覆盖到不同变体。"""
        renderer = StickerRenderer(storage=_FakeStorage())
        variants = {str(p) for p in _FakeStorage()._index["无语"]}

        picked = set()
        for _ in range(100):
            components = await renderer.render_text("看看 :无语:")
            self.assertEqual(len(components), 2)
            self.assertIn(components[1].path, variants)
            picked.add(components[1].path)

        self.assertEqual(picked, variants)

    async def test_sticker_style_emits_sub_type_one(self):
        """OneBot 平台下贴纸走 image 段 sub_type=1，原样透传给协议端。"""
        with tempfile.TemporaryDirectory() as tmp:
            img = Path(tmp) / "坏笑.webp"
            img.write_bytes(b"RIFF0000WEBPfake")

            class _Storage:
                def scan_meme_index(self):
                    return {"坏笑": [img]}

            renderer = StickerRenderer(storage=_Storage())
            components = await renderer.render_text(":坏笑:", sticker_style=True)

            self.assertEqual(len(components), 1)
            sticker = components[0]
            self.assertIsInstance(sticker, StickerImage)
            payload = sticker.toDict()
            self.assertEqual(payload["type"], "image")
            self.assertEqual(payload["data"]["sub_type"], 1)
            self.assertEqual(payload["data"]["summary"], "[动画表情]")
            self.assertTrue(payload["data"]["file"].startswith("base64://"))

    async def test_sticker_style_off_keeps_plain_image(self):
        """非 OneBot 平台维持普通图片组件。"""
        renderer = StickerRenderer(storage=_FakeStorage())

        components = await renderer.render_text(":坏笑:", sticker_style=False)

        self.assertIsInstance(components[0], Image)
        self.assertNotIsInstance(components[0], StickerImage)

    async def test_sticker_style_falls_back_when_file_missing(self):
        """贴纸文件读不到时退回普通图片，不抛异常。"""
        renderer = StickerRenderer(storage=_FakeStorage())

        components = await renderer.render_text(":坏笑:", sticker_style=True)

        self.assertIsInstance(components[0], Image)
        self.assertNotIsInstance(components[0], StickerImage)

    async def test_wrapped_sticker_symbols_are_stripped(self):
        """LLM 套在贴纸外的成对符号随贴纸一起剥掉，不留残骸。"""
        renderer = StickerRenderer(storage=_FakeStorage())

        for text in ("[:坏笑:]", "【:坏笑:】", "（:坏笑:）", "(:坏笑:)", "「:坏笑:」", "“:坏笑:”"):
            components = await renderer.render_text(text)
            self.assertEqual(len(components), 1, f"残留符号: {text} -> {components}")
            self.assertIsInstance(components[0], Image)

    async def test_wrapped_sticker_keeps_following_text(self):
        """剥掉外框后，正文原样保留。"""
        renderer = StickerRenderer(storage=_FakeStorage())

        components = await renderer.render_text("[:坏笑:] 一张图几百上千token")

        self.assertEqual(len(components), 2)
        self.assertIsInstance(components[0], Image)
        self.assertEqual(components[1].text, " 一张图几百上千token")

    async def test_unpaired_wrapper_is_kept(self):
        """只有一侧括号时不剥，避免吞掉正文符号。"""
        renderer = StickerRenderer(storage=_FakeStorage())

        components = await renderer.render_text("[:坏笑:")

        self.assertEqual(len(components), 2)
        self.assertEqual(components[0].text, "[")
        self.assertIsInstance(components[1], Image)

    async def test_prompt_injection_lists_names(self):
        renderer = StickerRenderer(storage=_FakeStorage())
        prompt = renderer.build_prompt_injection()

        self.assertIn("坏笑", prompt)
        self.assertIn("无语", prompt)
        self.assertNotIn("分类", prompt)

    async def test_prompt_injection_empty(self):
        class EmptyStorage:
            def get_available_meme_names(self):
                return []

        renderer = StickerRenderer(storage=EmptyStorage())
        prompt = renderer.build_prompt_injection()

        self.assertIn("没有可用 meme", prompt)


class StripStickerTokensTestCase(unittest.TestCase):
    """工具直发通道用的剥离：只删表情库里真实存在的标记。"""

    def test_removes_known_token(self):
        renderer = StickerRenderer(storage=_FakeStorage())

        self.assertEqual(renderer.strip_sticker_tokens("好耶 :坏笑: 走吧"), "好耶  走吧")

    def test_removes_token_with_paired_wrapper(self):
        renderer = StickerRenderer(storage=_FakeStorage())

        self.assertEqual(renderer.strip_sticker_tokens("好耶（:坏笑:）"), "好耶")

    def test_keeps_unknown_token(self):
        renderer = StickerRenderer(storage=_FakeStorage())
        text = "说明：:未知名字: 是普通文字"

        self.assertEqual(renderer.strip_sticker_tokens(text), text)

    def test_keeps_text_without_tokens(self):
        renderer = StickerRenderer(storage=_FakeStorage())
        text = "下次执行时间：2026-03-20 12:00:00"

        self.assertEqual(renderer.strip_sticker_tokens(text), text)

    def test_empty_index_keeps_text(self):
        class EmptyStorage:
            def scan_meme_index(self):
                return {}

        renderer = StickerRenderer(storage=EmptyStorage())

        self.assertEqual(renderer.strip_sticker_tokens(":坏笑:"), ":坏笑:")


if __name__ == "__main__":
    unittest.main()
