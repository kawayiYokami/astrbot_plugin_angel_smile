import unittest
from pathlib import Path

from astrbot_plugin_angel_smile.tests._bootstrap import install_fake_astrbot

install_fake_astrbot()

from astrbot.core.message.components import Image, Plain  # noqa: E402
from astrbot_plugin_angel_smile.services.render import StickerRenderer  # noqa: E402


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

    async def test_stable_select_deterministic(self):
        """Same message_id + meme_name + token_index always picks same variant."""
        renderer = StickerRenderer(storage=_FakeStorage())
        text = "看看 :无语:"

        components1 = await renderer.render_text(text, message_id="msg123")
        components2 = await renderer.render_text(text, message_id="msg123")

        # Both should pick the same variant
        self.assertEqual(components1[1].path, components2[1].path)

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


if __name__ == "__main__":
    unittest.main()
