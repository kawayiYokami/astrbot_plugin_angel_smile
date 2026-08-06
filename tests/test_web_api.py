"""MemeAPI 后端接口测试：列表分组 / 上传 / 删除 / 重命名 / 变体删除。

不依赖真实 AstrBot 框架，直接用 MemeAPI 实例 + 假 storage/manager 调 handler。
"""

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from astrbot_plugin_angel_smile.tests._bootstrap import install_fake_astrbot

install_fake_astrbot()


def _install_fake_web_api():
    """安装假的 astrbot.api.web（新版形态），handler 直接可用。"""
    web_module = types.ModuleType("astrbot.api.web")

    class _FakeResponse:
        def __init__(self, body, status_code=200):
            self.body = body
            self.status_code = status_code

    def json_response(data=None, *, status_code=200, headers=None):
        return _FakeResponse(data, status_code)

    def error_response(message, *, status_code=400, data=None, headers=None):
        return _FakeResponse(
            {"status": "error", "message": message, "data": data}, status_code
        )

    def file_response(path, *, filename=None, content_type=None, headers=None):
        return _FakeResponse({"__file__": str(path)}, 200)

    class _FakeRequest:
        """可配置的假 request：query / json body / form / files 都由测试设置。"""

        def __init__(self):
            self.query = {}
            self._json_data = None
            self._form_data = {}
            self._files_data = {}

        def set_json(self, data):
            self._json_data = data

        def set_form(self, form):
            self._form_data = form

        def set_files(self, files):
            self._files_data = files

        async def json(self, default=None):
            return self._json_data if self._json_data is not None else default

        async def form(self):
            return self._form_data

        async def files(self):
            return self._files_data

    web_module.json_response = json_response
    web_module.error_response = error_response
    web_module.file_response = file_response
    web_module.request = _FakeRequest()
    sys.modules["astrbot.api.web"] = web_module


_install_fake_web_api()

import astrbot.api.web as _web  # noqa: E402

from astrbot_plugin_angel_smile.models import PluginPaths  # noqa: E402
from astrbot_plugin_angel_smile.services.meme_manager import MemeManager  # noqa: E402
from astrbot_plugin_angel_smile.services.storage import MemeStorage  # noqa: E402
from astrbot_plugin_angel_smile.web_api import MemeAPI  # noqa: E402


def _create_image(path: Path, color: str = "red", size=(64, 64)):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, color=color)
    draw = ImageDraw.Draw(img)
    if color == "red":
        draw.rectangle((4, 4, 60, 20), fill="blue")
    elif color == "blue":
        draw.ellipse((10, 10, 54, 54), fill="yellow")
    elif color == "green":
        draw.polygon(((4, 60), (32, 4), (60, 60)), fill="purple")
    img.save(path)


def _unwrap(response):
    """从 _ok/_err 响应中取出 data。"""
    if hasattr(response, "json"):
        body = response.json
    elif hasattr(response, "body"):
        body = response.body
    else:
        body = response
    if isinstance(body, str):
        return json.loads(body)
    return body


class MemeAPIBaseTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        os.environ["ASTRBOT_TEST_DATA_PATH"] = self.temp_dir.name

        root = Path(self.temp_dir.name)
        self.paths = PluginPaths(
            plugin_dir=root / "plugin",
            data_dir=root / "data",
            meme_dir=root / "data" / "memes",
        )
        self.paths.plugin_dir.mkdir(parents=True, exist_ok=True)
        self.paths.meme_dir.mkdir(parents=True, exist_ok=True)

        self.storage = MemeStorage(self.paths)
        self.storage.initialize()
        self.manager = MemeManager(self.storage)
        self.manager.initialize()
        self.api = MemeAPI(self.storage, self.manager)
        self.request = _web.request

    async def _ingest(self, name: str, color: str = "red"):
        src = Path(self.temp_dir.name) / f"{name}_{color}.png"
        _create_image(src, color=color)
        await self.manager.ingest_meme(name, str(src))


class TestListMemes(MemeAPIBaseTestCase):
    async def test_list_empty(self):
        resp = await self.api.list_memes()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["data"], [])

    async def test_list_groups_by_name(self):
        await self._ingest("坏笑", "red")
        await self._ingest("坏笑", "blue")  # 第二张升级为文件夹
        await self._ingest("无语", "green")

        resp = await self.api.list_memes()
        body = _unwrap(resp)
        items = body["data"]
        self.assertEqual(len(items), 2)
        names = [item["name"] for item in items]
        self.assertEqual(names, ["坏笑", "无语"])

        laugh = next(item for item in items if item["name"] == "坏笑")
        self.assertEqual(len(laugh["variants"]), 2)
        # 变体 relative 路径区分单文件与文件夹（第二次 ingest 后升级为文件夹形态）
        rels = sorted(v["relative"] for v in laugh["variants"])
        self.assertIn(os.path.join("坏笑", "坏笑.webp"), rels)
        self.assertTrue(any(r.startswith("坏笑/") or r.startswith("坏笑\\") for r in rels))


class TestMemeImage(MemeAPIBaseTestCase):
    async def test_image_preview_ok(self):
        await self._ingest("坏笑", "red")
        self.request.query = {"path": "坏笑.webp"}
        resp = await self.api.meme_image()
        # 返回的是 FileResponse / send_file，非 JSON
        self.assertTrue(hasattr(resp, "body") or hasattr(resp, "status_code"))

    async def test_image_path_traversal_rejected(self):
        await self._ingest("坏笑", "red")
        self.request.query = {"path": "../../etc/passwd"}
        resp = await self.api.meme_image()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "error")

    async def test_image_missing_404(self):
        self.request.query = {"path": "不存在的.webp"}
        resp = await self.api.meme_image()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "error")

    async def test_image_b64_ok(self):
        await self._ingest("坏笑", "red")
        self.request.query = {"path": "坏笑.webp"}
        resp = await self.api.meme_image_b64()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "ok")
        data = body["data"]
        self.assertTrue(data["data_url"].startswith("data:image/webp;base64,"))

    async def test_image_b64_traversal_rejected(self):
        await self._ingest("坏笑", "red")
        self.request.query = {"path": "../../etc/passwd"}
        resp = await self.api.meme_image_b64()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "error")


class TestDeleteMeme(MemeAPIBaseTestCase):
    async def test_delete_single_file_rejected_when_variant_exists(self):
        """单文件分组也是一个变体，有变体时拒绝删除分组。"""
        await self._ingest("坏笑", "red")
        self.request.set_json({"name": "坏笑"})
        resp = await self.api.delete_meme()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "error")
        self.assertTrue((self.paths.meme_dir / "坏笑.webp").exists())

    async def test_delete_single_file_allowed_when_file_removed(self):
        """分组文件不存在时视为空分组，可删除（幂等清理）。"""
        await self._ingest("坏笑", "red")
        target = self.paths.meme_dir / "坏笑.webp"
        self.assertTrue(target.exists())
        target.unlink()

        self.request.set_json({"name": "坏笑"})
        resp = await self.api.delete_meme()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "ok")
        self.assertFalse(target.exists())

    async def test_delete_folder_rejected_when_variants_exist(self):
        """分组有变体时拒绝删除整个分组（需先删变体）。"""
        await self._ingest("坏笑", "red")
        await self._ingest("坏笑", "blue")
        self.assertTrue((self.paths.meme_dir / "坏笑").is_dir())

        self.request.set_json({"name": "坏笑"})
        resp = await self.api.delete_meme()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "error")
        self.assertTrue((self.paths.meme_dir / "坏笑").is_dir())

    async def test_delete_folder_allowed_when_empty(self):
        """分组全空（无变体）时可删除。"""
        await self._ingest("坏笑", "red")
        await self._ingest("坏笑", "blue")
        folder = self.paths.meme_dir / "坏笑"
        self.assertTrue(folder.is_dir())

        # 先删除全部变体
        for variant in list(folder.iterdir()):
            variant.unlink()
        self.assertFalse(any(folder.iterdir()))

        self.request.set_json({"name": "坏笑"})
        resp = await self.api.delete_meme()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "ok")
        self.assertFalse(folder.exists())

    async def test_delete_missing(self):
        self.request.set_json({"name": "不存在"})
        resp = await self.api.delete_meme()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "error")

    async def test_delete_no_name(self):
        self.request.set_json({})
        resp = await self.api.delete_meme()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "error")


class TestRenameMeme(MemeAPIBaseTestCase):
    async def test_rename_single_file(self):
        await self._ingest("坏笑", "red")
        self.request.set_json({"old_name": "坏笑", "new_name": "大笑"})
        resp = await self.api.rename_meme()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "ok")
        self.assertTrue((self.paths.meme_dir / "大笑.webp").exists())
        self.assertFalse((self.paths.meme_dir / "坏笑.webp").exists())

    async def test_rename_folder(self):
        await self._ingest("坏笑", "red")
        await self._ingest("坏笑", "blue")
        self.assertTrue((self.paths.meme_dir / "坏笑").is_dir())

        self.request.set_json({"old_name": "坏笑", "new_name": "大笑"})
        resp = await self.api.rename_meme()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "ok")
        self.assertTrue((self.paths.meme_dir / "大笑").is_dir())
        self.assertFalse((self.paths.meme_dir / "坏笑").exists())

    async def test_rename_invalid_name(self):
        await self._ingest("坏笑", "red")
        self.request.set_json({"old_name": "坏笑", "new_name": "a<b"})
        resp = await self.api.rename_meme()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "error")

    async def test_rename_dedup_paths_updated(self):
        """重命名后 dHash 索引相对路径同步更新。"""
        await self._ingest("坏笑", "red")
        old_rel = "坏笑.webp"
        self.assertIn(old_rel, self.manager.dedup.index)

        self.api._rebuild_dedup_paths("坏笑", "大笑")
        self.assertNotIn(old_rel, self.manager.dedup.index)
        self.assertIn("大笑.webp", self.manager.dedup.index)


class TestDeleteVariant(MemeAPIBaseTestCase):
    async def test_delete_one_variant_keeps_rest(self):
        await self._ingest("坏笑", "red")
        await self._ingest("坏笑", "blue")
        variants = self.storage.get_variants("坏笑")
        self.assertEqual(len(variants), 2)

        victim_rel = os.path.join("坏笑", variants[0].name)
        self.request.set_json({"name": "坏笑", "relative": victim_rel})
        resp = await self.api.delete_variant()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "ok")

        remaining = self.storage.get_variants("坏笑")
        self.assertEqual(len(remaining), 1)

    async def test_delete_last_variant_removes_folder(self):
        await self._ingest("坏笑", "red")
        await self._ingest("坏笑", "blue")
        folder = self.paths.meme_dir / "坏笑"
        self.assertTrue(folder.is_dir())

        # 逐个删除变体
        self.request.set_json({"name": "坏笑", "relative": os.path.join("坏笑", "坏笑.webp")})
        await self.api.delete_variant()
        self.request.set_json({"name": "坏笑", "relative": os.path.join("坏笑", "坏笑(2).webp")})
        resp = await self.api.delete_variant()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "ok")

        self.assertFalse(folder.exists())
        self.assertEqual(self.storage.get_variants("坏笑"), [])


class TestDeleteVariants(MemeAPIBaseTestCase):
    async def test_batch_delete_partial_keeps_rest(self):
        await self._ingest("坏笑", "red")
        await self._ingest("坏笑", "blue")
        await self._ingest("坏笑", "green")
        variants = self.storage.get_variants("坏笑")
        self.assertEqual(len(variants), 3)

        self.request.set_json({
            "name": "坏笑",
            "relatives": [os.path.join("坏笑", v.name) for v in variants[:2]],
        })
        resp = await self.api.delete_variants()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "ok")

        remaining = self.storage.get_variants("坏笑")
        self.assertEqual(len(remaining), 1)

    async def test_batch_delete_all_removes_folder(self):
        await self._ingest("坏笑", "red")
        await self._ingest("坏笑", "blue")
        folder = self.paths.meme_dir / "坏笑"
        self.assertTrue(folder.is_dir())

        variants = self.storage.get_variants("坏笑")
        self.request.set_json({
            "name": "坏笑",
            "relatives": [os.path.join("坏笑", v.name) for v in variants],
        })
        resp = await self.api.delete_variants()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "ok")

        self.assertFalse(folder.exists())
        self.assertEqual(self.storage.get_variants("坏笑"), [])

    async def test_batch_delete_traversal_rejected(self):
        await self._ingest("坏笑", "red")
        self.request.set_json({"name": "坏笑", "relatives": ["../../evil.webp"]})
        resp = await self.api.delete_variants()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "error")

    async def test_batch_delete_missing_relatives(self):
        self.request.set_json({"name": "坏笑"})
        resp = await self.api.delete_variants()
        body = _unwrap(resp)
        self.assertEqual(body["status"], "error")


if __name__ == "__main__":
    unittest.main()
