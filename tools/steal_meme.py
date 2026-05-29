"""Meme tool: ingest images into .meme/ sticker library."""

from dataclasses import dataclass, field
from typing import Protocol

from astrbot.api import FunctionTool
from astrbot.api.event import AstrMessageEvent

from ..constants import MEME_TOOL_NAME


class MemeManagerProtocol(Protocol):
    async def ingest_meme(self, emotion: str, path: str) -> str: ...


@dataclass
class MemeIngestTool(FunctionTool):
    manager: MemeManagerProtocol | None = field(repr=False, default=None)
    name: str = MEME_TOOL_NAME
    description: str = "把图片收入贴纸库。参数：emotion 为贴纸名，path 为图片路径。"
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "emotion": {
                    "type": "string",
                    "description": "贴纸名，即聊天中使用的 :贴纸名: token。",
                },
                "path": {
                    "type": "string",
                    "description": "图片引用：本地绝对路径、file:/// 或 http(s) URL。",
                },
            },
            "required": ["emotion", "path"],
        }
    )

    async def run(
        self,
        event: AstrMessageEvent,
        emotion: str,
        path: str,
    ) -> str:
        _ = event
        if self.manager is None:
            raise RuntimeError("MemeIngestTool manager is not initialized")
        return await self.manager.ingest_meme(emotion=emotion, path=path)
