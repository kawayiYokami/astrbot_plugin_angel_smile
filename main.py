from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core.message.components import Plain
from astrbot.core.provider.entities import ProviderRequest

from .constants import STEAL_TOOL_NAME
from .models import PluginPaths
from .services.meme_manager import MemeManager
from .services.render import StickerRenderer
from .services.storage import MemeStorage
from .tools.steal_meme import StealMemeTool


@register(
    "astrbot_plugin_angel_smile",
    "OpenAI",
    "天使之笑：允许 LLM 在回答中插入表情包，并支持自动偷取表情包入库。",
    "1.0.0",
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
            stickers_dir=data_dir / "memes",
            stickers_data_file=data_dir / "memes_data.json",
            default_dir=plugin_dir / "default",
        )

        self.storage = MemeStorage(paths=paths)
        self.renderer = StickerRenderer(storage=self.storage)
        self.manager = MemeManager(storage=self.storage)

        self.context.provider_manager.llm_tools.remove_func(STEAL_TOOL_NAME)
        self.steal_meme_tool = StealMemeTool(manager=self.manager)
        self.context.add_llm_tools(self.steal_meme_tool)

    async def initialize(self):
        self.storage.initialize()
        self.manager.initialize()
        logger.info("AngelSmile: 插件已初始化")

    async def terminate(self):
        self.context.provider_manager.llm_tools.remove_func(self.steal_meme_tool.name)
        logger.info("AngelSmile: 插件已停止")

    @filter.on_llm_request()
    async def on_llm_req(self, event: AstrMessageEvent, req: ProviderRequest):
        _ = event
        prompt_catalog = self.renderer.build_prompt_catalog()
        if not prompt_catalog.strip():
            return

        instruction_prompt = f"""
<表情包目录>
你维护一套表情包分类目录，分为“可用表情”和“暂不可用的表情（当前分类下暂无素材）”。

使用规则：
1. 你只能在“可用表情”中使用 `:表情包名字:`。
2. 当你需要使用表情包时，请使用如下格式：:表情包名字:
3. 每条消息最多使用 {self.max_stickers_per_message} 个表情包。
4. 使用表情包后，不要再用 emoji、颜文字或重复的情绪描述词表达同一种情绪。
5. 只有在表达情绪、语气或态度时才使用表情包。
6. 执行任务、给出步骤、写代码、处理严肃问题时，尽量不要使用表情包。
7. 当你需要调用图片入库工具保存图片时，应优先从“暂不可用的表情”里选择最合适的 `category` 来补齐素材。
8. 只有在目录中确实没有合适类别时，才允许新建分类，并同时提供 description。

{prompt_catalog}
</表情包目录>
"""
        req.system_prompt = f"{req.system_prompt or ''}\n\n{instruction_prompt}"

    @filter.on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent):
        result = event.get_result()
        new_chain = []
        for item in result.chain:
            if isinstance(item, Plain):
                new_chain.extend(await self.renderer.render_text(item.text))
            else:
                new_chain.append(item)
        result.chain = new_chain

    @filter.after_message_sent()
    async def after_message_sent(self, event: AstrMessageEvent):
        _ = event
        return None
