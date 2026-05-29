from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core.message.components import Plain
from astrbot.core.provider.entities import ProviderRequest

from .constants import MEME_TOOL_NAME
from .models import PluginPaths
from .services.meme_manager import MemeManager
from .services.render import StickerRenderer
from .services.storage import MemeStorage
from .tools.steal_meme import MemeIngestTool


@register(
    "astrbot_plugin_angel_smile",
    "OpenAI",
    "天使之笑：允许 LLM 在回答中插入表情包，并支持自动偷取表情包入库。",
    "2.0.0",
)
class AngelSmilePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = context.get_config()
        self.max_stickers_per_message = self.config.get("max_stickers_per_message", 1)

        plugin_dir = Path(__file__).resolve().parent
        data_dir = Path(StarTools.get_data_dir())
        paths = PluginPaths(
            plugin_dir=plugin_dir,
            data_dir=data_dir,
            meme_dir=data_dir / "memes",
        )

        self.storage = MemeStorage(paths=paths)
        self.renderer = StickerRenderer(storage=self.storage)
        self.manager = MemeManager(storage=self.storage)

        self.context.provider_manager.llm_tools.remove_func(MEME_TOOL_NAME)
        self.meme_tool = MemeIngestTool(manager=self.manager)
        self.context.add_llm_tools(self.meme_tool)

    async def initialize(self):
        self.storage.initialize()
        self.manager.initialize()
        logger.info("AngelSmile: 插件已初始化")

    async def terminate(self):
        self.context.provider_manager.llm_tools.remove_func(self.meme_tool.name)
        logger.info("AngelSmile: 插件已停止")

    @filter.on_llm_request()
    async def on_llm_req(self, event: AstrMessageEvent, req: ProviderRequest):
        _ = event
        prompt_injection = self.renderer.build_prompt_injection()

        # Update tool description dynamically with current meme list
        self.meme_tool.description = self.renderer.build_tool_description()

        instruction_prompt = f"""
<表情包>
使用规则：
1. 当你需要使用表情包时，请使用如下格式：:meme名:
2. 每条消息最多使用 {self.max_stickers_per_message} 个表情包。
3. 使用表情包后，不要再用 emoji、颜文字或重复的情绪描述词表达同一种情绪。
4. 只有在表达情绪、语气或态度时才使用表情包。
5. 执行任务、给出步骤、写代码、处理严肃问题时，尽量不要使用表情包。

{prompt_injection}
</表情包>
"""
        req.system_prompt = f"{req.system_prompt or ''}\n\n{instruction_prompt}"

    @filter.on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent):
        result = event.get_result()
        message_id = getattr(event, "message_id", "") or ""
        new_chain = []
        for item in result.chain:
            if isinstance(item, Plain):
                new_chain.extend(await self.renderer.render_text(item.text, message_id=message_id))
            else:
                new_chain.append(item)
        result.chain = new_chain

    @filter.after_message_sent()
    async def after_message_sent(self, event: AstrMessageEvent):
        _ = event
        return None
