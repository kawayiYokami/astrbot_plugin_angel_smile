import os
import re
import time
from pathlib import Path
from typing import Iterable, Optional

from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .constants import DEFAULT_CATEGORY


def normalize_category_name(category: Optional[str]) -> str:
    text = (category or "").strip().lower()
    if not text:
        return DEFAULT_CATEGORY
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"[^a-z0-9_\u4e00-\u9fff]", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or DEFAULT_CATEGORY


def resolve_user_path(raw_path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(raw_path))).resolve()


def get_allowed_image_roots(extra_roots: Optional[Iterable[Path]] = None) -> tuple[Path, ...]:
    roots = {
        Path(get_astrbot_data_path()).resolve(),
        Path.cwd().resolve(),
    }
    if extra_roots:
        roots.update(path.resolve() for path in extra_roots)
    return tuple(sorted(roots))


def is_path_within_roots(target_path: Path, roots: Iterable[Path]) -> bool:
    resolved_target = target_path.resolve()
    for root in roots:
        resolved_root = root.resolve()
        if resolved_target == resolved_root or resolved_root in resolved_target.parents:
            return True
    return False


def _is_png(buf: bytes) -> bool:
    return len(buf) > 3 and buf[:4] == b"\x89PNG"


def _is_jpg(buf: bytes) -> bool:
    return len(buf) > 2 and buf[0] == 0xFF and buf[1] == 0xD8 and buf[2] == 0xFF


def _is_gif(buf: bytes) -> bool:
    return len(buf) > 2 and buf[:3] == b"GIF"


def _is_webp(buf: bytes) -> bool:
    return len(buf) > 13 and buf[:4] == b"RIFF" and buf[8:12] == b"WEBP"


def _is_bmp(buf: bytes) -> bool:
    return len(buf) > 1 and buf[:2] == b"BM"


def _is_tiff(buf: bytes) -> bool:
    return len(buf) > 3 and (buf[:2] == b"II" or buf[:2] == b"MM")


def _is_ico(buf: bytes) -> bool:
    return len(buf) > 3 and buf[:4] == b"\x00\x00\x01\x00"


def _is_heic(buf: bytes) -> bool:
    if len(buf) < 16 or buf[4:8] != b"ftyp":
        return False
    major_brand = buf[8:12].decode(errors="ignore")
    return major_brand == "heic" or major_brand in ("mif1", "msf1")


def _is_avif(buf: bytes) -> bool:
    if len(buf) < 16 or buf[4:8] != b"ftyp":
        return False
    major_brand = buf[8:12].decode(errors="ignore")
    return major_brand == "avif"


_IMAGE_CHECKERS = [
    (_is_png, "png"),
    (_is_jpg, "jpg"),
    (_is_gif, "gif"),
    (_is_webp, "webp"),
    (_is_bmp, "bmp"),
    (_is_tiff, "tiff"),
    (_is_ico, "ico"),
    (_is_heic, "heic"),
    (_is_avif, "avif"),
]


def detect_image_format(data: bytes) -> str | None:
    if not data:
        return None
    for checker, ext in _IMAGE_CHECKERS:
        if checker(data):
            return ext
    return None


def get_image_extension(data: bytes, default: str = "jpg") -> str:
    ext = detect_image_format(data)
    return ext if ext else default


def safe_filename(save_name: Optional[str], suffix: str, force_extension: bool = False) -> str:
    base = (save_name or "").strip()
    cleaned_suffix = suffix.lower().strip()
    if cleaned_suffix and not cleaned_suffix.startswith("."):
        cleaned_suffix = f".{cleaned_suffix}"
    if not cleaned_suffix:
        cleaned_suffix = ".jpg"

    if base:
        base = Path(base).name
        base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", base)
        stem = Path(base).stem.strip() or f"meme_{int(time.time())}"
        existing_ext = Path(base).suffix.lower()
        ext = cleaned_suffix if force_extension or not existing_ext else existing_ext
        return f"{stem}{ext}"
    return f"meme_{int(time.time())}{cleaned_suffix}"
