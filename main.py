from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core.message.components import Plain
from astrbot.core.provider.entities import ProviderRequest

from .constants import MEME_TOOL_NAME
from .models import PluginPaths
from .services.meme_manager import MemeManager
from .services.render import (
    StickerRenderer,
    register_sticker_component,
    unregister_sticker_component,
)
from .services.storage import MemeStorage
from .tools.steal_meme import MemeIngestTool


@register(
    "astrbot_plugin_angel_smile",
    "OpenAI",
    "天使之笑：允许 LLM 在回答中插入表情包，并支持自动偷取表情包入库。",
    "2.4.2",
)
class AngelSmilePlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        # 插件自身配置（AstrBotConfig，dict 子类，带 schema）。
        # 由框架通过 config 参数注入；context.get_config() 返回的是全局
        # AstrBot 配置，不能用于插件配置。
        self.config = config if isinstance(config, dict) else {}

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

        # OneBot 表情样式发送（image 段 sub_type=1）需要把 StickerImage 登记进
        # 框架的空消息校验表；登记失败就退回普通图片，不影响发图。
        self._sticker_style_ready = register_sticker_component()

        self.context.provider_manager.llm_tools.remove_func(MEME_TOOL_NAME)
        self.meme_tool = MemeIngestTool(manager=self.manager)
        self.context.add_llm_tools(self.meme_tool)

        # -- 注册 WebUI API 路由（表情库管理页）--
        try:
            from .web_api import register_all_routes

            register_all_routes(self.context, self.storage, self.manager, plugin=self)
            logger.info("AngelSmile: 已注册表情管理 WebUI API 路由")
        except Exception as e:  # pragma: no cover - 兼容旧版 AstrBot
            logger.warning(f"AngelSmile: WebUI API 路由注册失败（不影响核心功能）: {e}")

    async def initialize(self):
        self.storage.initialize()
        self.manager.initialize()
        logger.info("AngelSmile: 插件已初始化")

    async def terminate(self):
        self.context.provider_manager.llm_tools.remove_func(self.meme_tool.name)
        unregister_sticker_component()
        logger.info("AngelSmile: 插件已停止")

    @filter.on_llm_request()
    async def on_llm_req(self, event: AstrMessageEvent, req: ProviderRequest):
        _ = event
        prompt_injection = self.renderer.build_prompt_injection()

        # Update tool description dynamically with current meme list
        self.meme_tool.description = self.renderer.build_tool_description()

        instruction_prompt = f"""
<表情贴纸>
使用方式：直接写贴纸格式，贴纸名必须来自下方"可用贴纸清单"。
错误写法：`:meme名:`、`:贴纸名:`、`:<名字>:`、`:{{名字}}:`（这些都是占位符，不要照抄字面）。

其他规则：
1. 每条消息最多使用 {self.config.get("max_stickers_per_message", 1)} 个表情包
2. 使用贴纸请克制，仅在闲聊，感情强烈时才使用
3. 执行任务、给出步骤、写代码、处理严肃问题时，不要使用表情包
4. 禁止贴纸格式前后加括号
5. 禁止在贴纸格式内部加贴纸名以外的任何辅助文本
6. 调用 `send_message_to_user` 工具发送消息时，不要在文本里写贴纸格式——该工具不解析贴纸，贴纸会原样显示成 `:名字:` 文本。贴纸只能写在正常回答正文里（也就是你不调用该工具、直接输出的那种回复）

可用贴纸清单：

{prompt_injection}
</表情贴纸>
"""
        req.system_prompt = f"{req.system_prompt or ''}\n\n{instruction_prompt}"

    @filter.on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent):
        result = event.get_result()
        # OneBot 平台按表情样式发送（image 段 sub_type=1），其它平台维持普通图片
        sticker_style = (
            self._sticker_style_ready and event.get_platform_name() == "aiocqhttp"
        )
        new_chain = []
        for item in result.chain:
            if isinstance(item, Plain):
                new_chain.extend(
                    await self.renderer.render_text(
                        item.text,
                        sticker_style=sticker_style,
                    )
                )
            else:
                new_chain.append(item)
        result.chain = new_chain

    @filter.after_message_sent()
    async def after_message_sent(self, event: AstrMessageEvent):
        _ = event
        return None
