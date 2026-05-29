import os
import re
from pathlib import Path
from typing import Iterable, Optional

from astrbot.core.utils.astrbot_path import get_astrbot_data_path


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


def is_valid_meme_name(name: str) -> bool:
    """Check if a meme name is valid.

    Valid meme names:
    - Non-empty after stripping
    - Do not contain path separators or special filesystem chars
    - Do not start with a dot
    """
    if not name or not name.strip():
        return False
    name = name.strip()
    if name.startswith("."):
        return False
    if re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
        return False
    return True


def stable_select(variants: list[Path], message_id: str, meme_name: str, token_index: int) -> Path:
    """Deterministically select a variant based on message context.

    Uses a simple hash of (message_id, meme_name, token_index) to pick
    a stable variant from the list, so the same message always renders
    the same image.
    """
    if len(variants) == 1:
        return variants[0]
    key = f"{message_id}:{meme_name}:{token_index}"
    idx = hash(key) % len(variants)
    return variants[idx]


# --- Image format detection ---

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


_IMAGE_CHECKERS = [
    (_is_png, "png"),
    (_is_jpg, "jpg"),
    (_is_gif, "gif"),
    (_is_webp, "webp"),
    (_is_bmp, "bmp"),
]


def detect_image_format(data: bytes) -> str | None:
    if not data:
        return None
    for checker, ext in _IMAGE_CHECKERS:
        if checker(data):
            return ext
    return None
