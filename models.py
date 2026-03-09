import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PluginPaths:
    plugin_dir: Path
    data_dir: Path
    stickers_dir: Path
    stickers_data_file: Path
    default_dir: Path


@dataclass(slots=True)
class MemeSaveResult:
    category: str
    description: str
    saved_file: Path
    reason: str

    def to_message(self) -> str:
        return json.dumps(
            {
                "ok": True,
                "category": self.category,
                "saved_file": str(self.saved_file),
                "description": self.description,
                "reason": self.reason,
            },
            ensure_ascii=False,
        )
