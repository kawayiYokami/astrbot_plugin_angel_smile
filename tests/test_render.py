import unittest

from astrbot_plugin_angel_smile.tests._bootstrap import install_fake_astrbot


install_fake_astrbot()

from astrbot.core.message.components import Image, Plain  # noqa: E402
from astrbot_plugin_angel_smile.services.render import StickerRenderer  # noqa: E402


class _FakeStorage:
    def __init__(self):
        self.available = {"happy": "开心"}
        self.path = "/tmp/happy.png"

    def get_available_stickers_data(self):
        return self.available

    def get_random_sticker_path(self, name):
        if name == "happy":
            return self.path
        return None


class RenderTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_non_sticker_colon_text_keeps_single_plain_component(self):
        renderer = StickerRenderer(storage=_FakeStorage())
        text = "下次执行时间：2026-03-20 12 :00: 00"

        components = await renderer.render_text(text)

        self.assertEqual(len(components), 1)
        self.assertIsInstance(components[0], Plain)
        self.assertEqual(components[0].text, text)

    async def test_available_sticker_replaced_by_image(self):
        renderer = StickerRenderer(storage=_FakeStorage())
        text = "你好 :happy: 世界"

        components = await renderer.render_text(text)

        self.assertEqual(len(components), 3)
        self.assertIsInstance(components[0], Plain)
        self.assertEqual(components[0].text, "你好 ")
        self.assertIsInstance(components[1], Image)
        self.assertEqual(components[1].path, "/tmp/happy.png")
        self.assertIsInstance(components[2], Plain)
        self.assertEqual(components[2].text, " 世界")


if __name__ == "__main__":
    unittest.main()
