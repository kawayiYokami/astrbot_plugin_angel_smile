from dataclasses import dataclass, field
from typing import Optional, Protocol

from astrbot.api import FunctionTool
from astrbot.api.event import AstrMessageEvent

from ..constants import STEAL_TOOL_NAME


class MemeManagerProtocol(Protocol):
    async def steal_meme(
        self,
        image_path: str,
        category: str,
        description: Optional[str] = None,
        save_name: Optional[str] = None,
    ) -> str: ...


@dataclass
class StealMemeTool(FunctionTool):
    manager: MemeManagerProtocol | None = field(repr=False, default=None)
    name: str = STEAL_TOOL_NAME
    description: str = (
        "接收本地图片路径，并按给定 category 保存到天使之笑插件目录。"
        "调用前应先根据分类目录自行判断分类。"
    )
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "本地图片绝对路径或相对路径。"},
                "category": {"type": "string", "description": "必填，要保存到的表情分类名。"},
                "description": {"type": "string", "description": "可选，该分类的中文用途描述；仅在新建分类时会写入。"},
                "save_name": {"type": "string", "description": "可选，保存后的文件名，不含路径。"},
            },
            "required": ["image_path", "category"],
        }
    )

    async def run(
        self,
        event: AstrMessageEvent,
        image_path: str,
        category: str,
        description: Optional[str] = None,
        save_name: Optional[str] = None,
    ) -> str:
        _ = event
        if self.manager is None:
            raise RuntimeError("StealMemeTool manager is not initialized")
        return await self.manager.steal_meme(
            image_path=image_path,
            category=category,
            description=description,
            save_name=save_name,
        )
