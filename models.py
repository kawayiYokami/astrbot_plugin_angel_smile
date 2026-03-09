import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class PluginPaths:
    plugin_dir: Path
    data_dir: Path
    stickers_dir: Path
    stickers_data_file: Path
    default_dir: Path


@dataclass(slots=True)
class MemeToolResult:
    ok: bool
    saved: bool
    category: str
    saved_file: Optional[Path] = None
    description: str = ""
    message: str = ""
    reason: str = ""
    duplicate: bool = False
    duplicate_type: str = ""
    matched_file: str = ""
    distance: Optional[int] = None

    def to_message(self) -> str:
        payload = {
            "ok": self.ok,
            "saved": self.saved,
            "category": self.category,
            "description": self.description,
            "message": self.message,
            "reason": self.reason,
            "duplicate": self.duplicate,
            "duplicate_type": self.duplicate_type,
            "matched_file": self.matched_file,
            "distance": self.distance,
        }
        if self.saved_file is not None:
            payload["saved_file"] = str(self.saved_file)
        return json.dumps(payload, ensure_ascii=False)


@dataclass(slots=True)
class MemeSaveResult:
    category: str
    description: str
    saved_file: Path
    reason: str

    def to_tool_result(self) -> MemeToolResult:
        return MemeToolResult(
            ok=True,
            saved=True,
            category=self.category,
            saved_file=self.saved_file,
            description=self.description,
            message="成功",
            reason=self.reason or "成功",
        )
