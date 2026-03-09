import json
import os
import re
import time
from pathlib import Path
from typing import Optional

from .constants import DEFAULT_CATEGORY


def normalize_category_name(category: Optional[str]) -> str:
    text = (category or "").strip().lower()
    if not text:
        return DEFAULT_CATEGORY
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"[^a-z0-9_\u4e00-\u9fff]", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or DEFAULT_CATEGORY


def safe_filename(name: Optional[str], suffix: str) -> str:
    base = (name or "").strip()
    if base:
        base = Path(base).name
        base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", base)
        stem = Path(base).stem.strip() or f"meme_{int(time.time())}"
        ext = Path(base).suffix or suffix
        return f"{stem}{ext.lower()}"
    return f"meme_{int(time.time())}{suffix.lower()}"


def resolve_user_path(raw_path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(raw_path))).resolve()


def extract_json_object(text: str) -> Optional[dict]:
    if not text:
        return None
    stripped = text.strip()
    try:
        data = json.loads(stripped)
        return data if isinstance(data, dict) else None
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", stripped)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def remove_sticker_tags(text: str) -> str:
    return re.sub(r":([a-zA-Z0-9_\-\u4e00-\u9fff]+):", "", text).strip()
