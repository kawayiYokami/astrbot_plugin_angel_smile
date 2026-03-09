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
