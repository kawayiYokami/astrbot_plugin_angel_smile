# Changelog

## 2.0.1 - 2026-06-20

### Fixed
- 修复 `on_llm_req` 抛 `NameError: name 'meme名' is not defined`：原指令提示词写在 f-string 里且包含 `:{meme名}:`，被 Python 当作表达式求值。
- 修复弱模型把示例占位符 `:meme名:` / `:贴纸名:` 直接照抄进回答的问题：移除抽象占位符，改用真实可用名字做示例，并显式列出常见错误写法作为反例。

### Changed
- `build_prompt_injection` 输出结构调整：从真实可用名字里挑前 3 个作为示例，附错误写法清单。
- `on_llm_req` 指令提示词文案重写为「使用方式 + 错误写法 + 其他规则」三段式；顺手修正原文错别字「再贴纸格式内部」→「在贴纸格式内部」、「任何发辅助文本」→「任何辅助文本」。

## 2.0.0 - 2026-05-29

### Breaking Changes
- 移除 `memes_data.json` 持久索引，可用 meme 列表改为扫描 `memes/` 目录动态生成。
- 工具名从 `steal_meme_to_smile` 改为 `meme`，参数简化为 `emotion` + `path`。
- 移除 `default/memes_data.json` 默认分类文件。
- 提示词不再使用"分类 + 描述"双层结构，直接列出可用 meme 名。

### New
- 入库统一转换为 WebP 格式。
- 同名 meme 多次入库自动升级为文件夹结构：首次单文件 → 第二次建文件夹 → 后续递增编号 `(2)`, `(3)`...
- 渲染选择改为稳定选择（基于 message_id + meme_name + token_index），同一消息重复渲染不会跳变。
- 内存索引缓存，5 分钟 TTL，入库后立即失效刷新。
- dHash 去重保留孤儿路径：用户手动删除的图片 hash 仍保留，防止同图被再次收入。
- dHash 索引路径在单文件升级为文件夹时自动同步更新。

### Removed
- 移除 `normalize_category_name()`、`safe_filename()` 等旧分类相关工具函数。
- 移除 `MemeSaveResult` 数据类，简化 `MemeToolResult`。
- 移除 `DEFAULT_CATEGORY`、`DEFAULT_CATEGORY_DESCRIPTION` 常量。

## 1.0.3 - 2026-03-19
- 修复表情渲染分词范围：仅匹配"可用表情"名称，不再把普通 `:xxx:` 文本（如时间里的 `:00:`）当作表情标签切分。
- 新增 `render` 回归测试，覆盖时间字符串场景，确保非表情文本保持原样。
- 补充测试桩中的 `astrbot.core.message.components` 假实现，保障渲染测试可稳定运行。

## 1.0.2 - 2026-03-19
- 修复 `utils` 模块接口兼容性问题，恢复 `get_allowed_image_roots` 等公共函数，避免导入报错。
- 入库流程改为按文件头检测图片真实格式，修复上游统一改成 `.jpg` 时导致的错误后缀保存问题。
- `safe_filename` 增加可选强制扩展名模式，在兼容旧行为的同时支持保存时使用真实后缀。

## 1.0.1 - 2026-03-13
- `steal_meme_to_smile` 现在支持图片引用统一输入：本地路径、`file:///` 与 `http(s)` URL。
- 当传入 `http(s)` URL 时，工具会先下载到本地再执行去重与入库流程。
- 更新工具参数描述，明确 `image_path` 可传路径与 URL，方便 LLM 在历史上下文中直接调用。

## 1.0.0 - 2026-03-10
- 初始化 `天使之笑` 插件，提供独立的表情目录与图片入库工具。
- 新增"可用表情 / 暂不可用表情"分类提示，供 LLM 在回复与整理素材时参考。
- 支持根据 `:tag:` 语法在回复中插入已存在的表情素材。
- 新增 `steal_meme_to_smile` 工具，用于按指定分类保存本地图片素材。
- 插件仅提供默认分类目录 `default/memes_data.json`，后续素材由模型自行补齐。
- 新增基于 dHash 的近似重复检测，命中重复图片时会直接跳过保存。
