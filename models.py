import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class PluginPaths:
    plugin_dir: Path
    data_dir: Path
    meme_dir: Path  # .meme/ directory


@dataclass(slots=True)
class MemeToolResult:
    ok: bool
    saved: bool
    emotion: str
    saved_file: Optional[Path] = None
    message: str = ""
    duplicate: bool = False
    matched_file: str = ""
    distance: Optional[int] = None

    def to_message(self) -> str:
        payload = {
            "ok": self.ok,
            "saved": self.saved,
            "emotion": self.emotion,
            "message": self.message,
            "duplicate": self.duplicate,
            "matched_file": self.matched_file,
            "distance": self.distance,
        }
        if self.saved_file is not None:
            payload["saved_file"] = str(self.saved_file)
        return json.dumps(payload, ensure_ascii=False)
