"""天使之笑 WebUI 后端 API：表情库管理（列表/上传/删除/重命名/变体）。

通过 AstrBot 的 register_web_api 机制注册（/api/plug/...）。
仅支持新版 astrbot.api.web（FastAPI 形态）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from astrbot.api.web import (
    error_response,
    file_response,
    json_response,
    request,
)

from astrbot.api import logger


def _ok(data: Any = None, message: str = "") -> Any:
    return json_response({"status": "ok", "message": message, "data": data})


def _err(message: str, status_code: int = 400) -> Any:
    return error_response(message, status_code=status_code)


_MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def _mime_for_suffix(suffix: str) -> str:
    return _MIME_BY_SUFFIX.get(suffix.lower(), "application/octet-stream")


def _decode_emotion_token(token: str) -> str:
    """base64url(UTF-8) → 表情名。"""
    import base64
    import binascii

    token = (token or "").strip()
    if not token:
        return ""
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (binascii.Error, ValueError):
        return ""
    try:
        return raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return ""


async def _get_json() -> Dict:
    """读取请求体 JSON；非 JSON 或缺失时返回空 dict。"""
    data = await request.json(default=None)
    return data if isinstance(data, dict) else {}


class MemeAPI:
    """表情库管理 API：列表 / 上传 / 删除 / 重命名 / 变体删除。"""

    def __init__(self, storage, manager):
        self.storage = storage
        self.manager = manager

    # ---------- 列表 ----------

    async def list_memes(self):
        """表情列表：按贴纸名分组，每个名字下列出全部变体。

        返回：
        [
            {
                "name": "坏笑",
                "variants": [
                    {"file": "坏笑.webp", "relative": "坏笑.webp"},
                    {"file": "坏笑(2).webp", "relative": "坏笑/坏笑(2).webp"},
                ],
            },
            ...
        ]
        """
        index = self.storage.scan_meme_index()
        items = []
        for name in sorted(index.keys()):
            variants = []
            for path in index[name]:
                try:
                    rel = str(path.relative_to(self.storage.paths.meme_dir))
                except ValueError:
                    rel = path.name
                variants.append({"file": path.name, "relative": rel})
            items.append({"name": name, "variants": variants})
        return _ok(items)

    async def meme_image(self):
        """返回单个表情图片文件（用于预览）。

        query 参数：path 为相对 memes 目录的路径（如 "坏笑.webp" 或 "坏笑/坏笑(2).webp"）。
        校验路径在 memes 目录内，防止目录穿越。
        """
        meme_dir = self.storage.paths.meme_dir.resolve()
        rel = (request.query.get("path") or "").strip()
        if not rel:
            return _err("缺少图片路径")
        candidate = (meme_dir / rel).resolve()
        try:
            candidate.relative_to(meme_dir)
        except ValueError:
            return _err("图片路径不合法", 403)
        if not candidate.is_file():
            return _err("图片不存在", 404)
        return file_response(str(candidate))

    async def meme_image_b64(self):
        """返回单个表情图片的 base64 data URL（用于 WebUI 内嵌预览）。

        与 meme_image 不同，本接口返回 JSON，可经由 bridge 的 apiGet
        （宿主 axios 带 Authorization header）调用，绕过 `<img>` 原生
        请求在 HTTP + Secure cookie 下无法携带认证的问题。

        query 参数：path 为相对 memes 目录的路径。
        """
        import base64 as _b64

        meme_dir = self.storage.paths.meme_dir.resolve()
        rel = (request.query.get("path") or "").strip()
        if not rel:
            return _err("缺少图片路径")
        candidate = (meme_dir / rel).resolve()
        try:
            candidate.relative_to(meme_dir)
        except ValueError:
            return _err("图片路径不合法", 403)
        if not candidate.is_file():
            return _err("图片不存在", 404)

        data = candidate.read_bytes()
        mime = _mime_for_suffix(candidate.suffix)
        data_url = f"data:{mime};base64,{_b64.b64encode(data).decode('ascii')}"
        return _ok({"path": rel, "mime": mime, "data_url": data_url})

    # ---------- 上传 ----------

    async def upload_meme(self, token: str = ""):
        """上传新表情。token 来自 memes/upload/<token> 路径段。"""
        emotion = ""
        tmp_path: Optional[Path] = None
        try:
            form = await request.form()
            files = await request.files()
            emotion = (form.get("emotion") or "").strip()
            upload = files.get("file")
            if upload is None:
                return _err("缺少上传文件")
            if not emotion:
                emotion = _decode_emotion_token(token)
            tmp_path = await self._save_upload(upload)

            result_text = await self.manager.ingest_meme(
                emotion=emotion, path=str(tmp_path)
            )
        except Exception as e:
            logger.warning("AngelSmile: 上传表情失败: %s", e)
            return _err(f"上传失败: {e}")
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass

        import json as _json

        try:
            result = _json.loads(result_text)
        except _json.JSONDecodeError:
            result = {"ok": False, "message": result_text}

        if not result.get("ok"):
            return _err(result.get("message") or "入库失败")
        return _ok(
            {
                "emotion": result.get("emotion"),
                "saved": result.get("saved"),
                "duplicate": result.get("duplicate", False),
                "saved_file": result.get("saved_file"),
            },
            result.get("message") or "成功",
        )

    async def _save_upload(self, upload) -> Path:
        """存到数据目录内的临时文件（/tmp 不在 ingest 白名单里）。"""
        import uuid

        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in _MIME_BY_SUFFIX:
            suffix = ""
        tmp_dir = self.storage.paths.data_dir / "upload_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp = tmp_dir / f"upload_{uuid.uuid4().hex}{suffix}"
        try:
            await upload.save(str(tmp))
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        return tmp

    # ---------- 删除 ----------

    async def delete_meme(self):
        """删除表情分组，连同组内全部变体一次性删除。"""
        payload = await _get_json()
        name = (payload.get("name") or "").strip()
        if not name:
            return _err("缺少表情名")
        removed = self._delete_meme_by_name(name)
        if not removed and not self._has_dedup_trace(name):
            return _err(f"表情不存在: {name}", 404)
        self.storage.invalidate_cache()
        return _ok(None, f"已删除 {name}")

    def _has_dedup_trace(self, name: str) -> bool:
        """判断 dedup 索引中是否留有该名称的 orphan 记录。

        文件被外部删除后磁盘无残留，但 dHash 索引故意保留 orphan 条目，
        此时视为「曾存在已删空」，删除操作幂等成功；从未入库的名称返回 False。
        """
        dedup = getattr(self.manager, "dedup", None)
        if dedup is None:
            return False
        prefix = f"{name}/"
        for rel in dedup.index:
            if rel == name or rel.startswith(prefix) or Path(rel).stem == name:
                return True
        return False

    def _delete_meme_by_name(self, name: str) -> bool:
        """删除指定表情的所有文件（根文件或文件夹），返回是否删除了东西。"""
        import shutil

        meme_dir = self.storage.paths.meme_dir
        removed = False

        folder = meme_dir / name
        if folder.is_dir():
            shutil.rmtree(str(folder))
            removed = True

        for entry in meme_dir.iterdir():
            if (
                entry.is_file()
                and entry.stem == name
                and entry.suffix.lower() in self._supported_suffixes()
            ):
                entry.unlink(missing_ok=True)
                removed = True

        return removed

    def _supported_suffixes(self):
        from ..constants import SUPPORTED_IMAGE_SUFFIXES

        return SUPPORTED_IMAGE_SUFFIXES

    # ---------- 重命名 ----------

    async def rename_meme(self):
        """重命名表情（根文件或文件夹整体改名）。"""
        payload = await _get_json()
        old_name = (payload.get("old_name") or "").strip()
        new_name = (payload.get("new_name") or "").strip()
        if not old_name or not new_name:
            return _err("缺少旧名或新名")
        if old_name == new_name:
            return _ok(None, "名称未变化")
        from ..utils import is_valid_meme_name

        if not is_valid_meme_name(new_name):
            return _err(f"非法的表情名: {new_name}")

        meme_dir = self.storage.paths.meme_dir
        if (meme_dir / new_name).exists() or any(
            p.stem == new_name for p in meme_dir.iterdir() if p.is_file()
        ):
            return _err(f"表情名已存在: {new_name}")

        renamed = False
        folder = meme_dir / old_name
        if folder.is_dir():
            folder.rename(meme_dir / new_name)
            renamed = True
        else:
            for entry in meme_dir.iterdir():
                if (
                    entry.is_file()
                    and entry.stem == old_name
                    and entry.suffix.lower() in self._supported_suffixes()
                ):
                    entry.rename(meme_dir / f"{new_name}{entry.suffix}")
                    renamed = True

        if not renamed:
            return _err(f"表情不存在: {old_name}", 404)

        # 同步更新 dHash 索引中的相对路径
        self._rebuild_dedup_paths(old_name, new_name)
        self.storage.invalidate_cache()
        return _ok(None, f"已重命名 {old_name} -> {new_name}")

    def _rebuild_dedup_paths(self, old_name: str, new_name: str) -> None:
        """dHash 索引内把 old_name 开头的相对路径改为 new_name 开头。"""
        dedup = getattr(self.manager, "dedup", None)
        if dedup is None:
            return
        updates = {}
        for rel, value in list(dedup.index.items()):
            # 单文件形态：坏笑.webp；文件夹形态：坏笑/坏笑.webp
            if (
                rel == old_name
                or rel.startswith(old_name + "/")
                or rel.startswith(old_name + ".")
            ):
                new_rel = new_name + rel[len(old_name):]
                updates[rel] = new_rel
        if updates:
            for old_rel, new_rel in updates.items():
                dedup.index[new_rel] = dedup.index.pop(old_rel)
            try:
                dedup._persist_index()
            except Exception:  # noqa: BLE001
                logger.debug("AngelSmile: dHash 索引更新失败", exc_info=True)

    # ---------- 变体删除 ----------

    async def delete_variant(self):
        """删除单个变体；删完后该表情无变体则整体移除。"""
        payload = await _get_json()
        name = (payload.get("name") or "").strip()
        relative = (payload.get("relative") or "").strip()
        if not name or not relative:
            return _err("缺少表情名或变体路径")

        meme_dir = self.storage.paths.meme_dir.resolve()
        candidate = (meme_dir / relative).resolve()
        try:
            candidate.relative_to(meme_dir)
        except ValueError:
            return _err("变体路径不合法", 403)
        if not candidate.is_file():
            return _err("变体不存在", 404)

        candidate.unlink(missing_ok=True)

        # 若文件夹已空则移除文件夹；若整个表情只剩空壳则清掉
        folder = meme_dir / name
        if folder.is_dir() and not any(folder.iterdir()):
            import shutil

            shutil.rmtree(str(folder))

        self.storage.invalidate_cache()
        remaining = self.storage.get_variants(name)
        if not remaining:
            return _ok(None, f"已删除变体，表情 {name} 已移除")
        return _ok(None, f"已删除变体，剩余 {len(remaining)} 个")

    async def delete_variants(self):
        """批量删除变体；删完后该表情无变体则整体移除。"""
        payload = await _get_json()
        name = (payload.get("name") or "").strip()
        relatives = payload.get("relatives") or []
        if not name or not isinstance(relatives, list) or not relatives:
            return _err("缺少表情名或变体列表")

        meme_dir = self.storage.paths.meme_dir.resolve()
        removed = 0
        for raw in relatives:
            rel = str(raw or "").strip()
            if not rel:
                continue
            candidate = (meme_dir / rel).resolve()
            try:
                candidate.relative_to(meme_dir)
            except ValueError:
                return _err(f"变体路径不合法: {rel}", 403)
            if candidate.is_file():
                candidate.unlink(missing_ok=True)
                removed += 1

        # 若文件夹已空则移除文件夹；若整个表情只剩空壳则清掉
        folder = meme_dir / name
        if folder.is_dir() and not any(folder.iterdir()):
            import shutil

            shutil.rmtree(str(folder))

        self.storage.invalidate_cache()
        remaining = self.storage.get_variants(name)
        if not remaining:
            return _ok(None, f"已删除 {removed} 个变体，表情 {name} 已移除")
        return _ok(None, f"已删除 {removed} 个变体，剩余 {len(remaining)} 个")


def register_all_routes(context, storage, manager, plugin=None) -> None:
    """注册全部 WebUI API 路由。"""
    api = MemeAPI(storage, manager)

    routes = [
        ("/astrbot_plugin_angel_smile/memes", api.list_memes, ["GET"], "表情列表（按名字分组含变体）"),
        ("/astrbot_plugin_angel_smile/memes/image", api.meme_image, ["GET"], "表情图片预览"),
        ("/astrbot_plugin_angel_smile/memes/image/b64", api.meme_image_b64, ["GET"], "表情图片 base64 data URL"),
        ("/astrbot_plugin_angel_smile/memes/upload", api.upload_meme, ["POST"], "上传新表情"),
        (
            "/astrbot_plugin_angel_smile/memes/upload/<token>",
            api.upload_meme,
            ["POST"],
            "上传表情（bridge，表情名走路径段）",
        ),
        ("/astrbot_plugin_angel_smile/memes/delete", api.delete_meme, ["POST"], "删除表情"),
        ("/astrbot_plugin_angel_smile/memes/rename", api.rename_meme, ["POST"], "重命名表情"),
        ("/astrbot_plugin_angel_smile/memes/variant/delete", api.delete_variant, ["POST"], "删除单个变体"),
        ("/astrbot_plugin_angel_smile/memes/variant/batch_delete", api.delete_variants, ["POST"], "批量删除变体"),
    ]

    if plugin is not None:
        plugin_config_api = PluginConfigAPI(plugin)
        routes.append(
            (
                "/astrbot_plugin_angel_smile/plugin_config",
                plugin_config_api.get_config,
                ["GET"],
                "插件全局配置（schema + 当前值）",
            )
        )
        routes.append(
            (
                "/astrbot_plugin_angel_smile/plugin_config/save",
                plugin_config_api.save_config,
                ["POST"],
                "保存插件全局配置并即时生效",
            )
        )

    for path, handler, methods, description in routes:
        context.register_web_api(path, handler, methods, description)


# ========== 插件全局配置（_conf_schema.json）==========

# schema type -> 校验/转换规则；bool 必须先于 int 判断（bool 是 int 子类）
_SCHEMA_TYPES = {"string", "text", "int", "float", "bool", "list", "object"}


def _convert_value(value, meta, path: str) -> tuple[list[str], Any]:
    """按 schema 元数据校验并转换单个值，返回 (errors, converted)。"""
    t = meta.get("type")
    if t not in _SCHEMA_TYPES:
        return [], value
    if t == "object":
        items = meta.get("items", {})
        if not isinstance(value, dict):
            return [f"{path} 应为对象"], value
        errors: list[str] = []
        converted: dict = {}
        for key, sub_meta in items.items():
            if key not in value:
                continue
            sub_errors, sub_value = _convert_value(value[key], sub_meta, f"{path}.{key}")
            errors.extend(sub_errors)
            converted[key] = sub_value
        return errors, converted
    if t == "bool":
        if not isinstance(value, bool):
            return [f"{path} 应为布尔值"], value
        return [], value
    if t == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            if isinstance(value, float) and value.is_integer():
                return [], int(value)
            return [f"{path} 应为整数"], value
        return [], value
    if t == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return [f"{path} 应为数字"], value
        return [], float(value)
    if t == "list":
        if not isinstance(value, list):
            return [f"{path} 应为列表"], value
        return [], value
    # string / text
    if not isinstance(value, str):
        return [f"{path} 应为字符串"], value
    return [], value


class PluginConfigAPI:
    """插件全局配置（_conf_schema.json）读取与保存。

    数据源是宿主的 AstrBotConfig 对象（dict 子类）。保存时原地更新键值，
    运行时路径动态读取即时生效，无需重载插件；与原生 dashboard 配置页共存，
    互为同一份数据的两个编辑入口。
    """

    def __init__(self, plugin):
        self._plugin = plugin
        self._config = plugin.config
        self._schema = getattr(plugin.config, "schema", None) or {}

    def get_config(self):
        return _ok({"schema": self._schema, "values": dict(self._config)})

    async def save_config(self):
        payload = await _get_json()
        values = payload.get("values")
        if not isinstance(values, dict):
            return _err("values 必须是 JSON 对象")

        errors: list[str] = []
        converted: Dict[str, Any] = {}
        for key, value in values.items():
            meta = self._schema.get(key)
            if not isinstance(meta, dict):
                errors.append(f"未知配置项: {key}")
                continue
            key_errors, key_value = _convert_value(value, meta, key)
            errors.extend(key_errors)
            converted[key] = key_value
        if errors:
            return _err("；".join(errors))

        # 原地更新顶层键：保持 dict 引用，运行时动态读取即时生效
        for key, value in converted.items():
            self._config[key] = value
        try:
            self._config.save_config()
        except Exception as e:
            logger.error(f"AngelSmile: 配置落盘失败: {e}", exc_info=True)
            return _err(f"配置落盘失败: {e}")

        hook = getattr(self._plugin, "on_config_saved", None)
        if callable(hook):
            try:
                hook()
            except Exception as e:
                logger.error(f"AngelSmile: 配置热生效钩子失败: {e}", exc_info=True)
                return _err(f"配置已保存，但热生效刷新失败: {e}")

        return _ok(message="已保存并即时生效")
