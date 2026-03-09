# AstrBot 天使之笑

一个独立的新插件，感谢 `astrbot_plugin_meme_manager_lite` 提供的设计思路：

- 允许 LLM 在回复里插入表情包
- 额外提供 `steal_meme_to_smile` 工具
- 工具接受一个本地图片路径和一个明确分类，并保存到插件自己的表情包目录

说明：插件不会清洗 `:tag:` 标签配置项，标签解析由发送阶段直接处理。

## 数据目录

插件运行后会在以下目录维护数据：

`data/plugin_data/astrbot_plugin_angel_smile`

其中：

- `memes_data.json`：分类到描述的映射
- `memes/<category>/`：分类图片目录

## LLM 工具

工具名：`steal_meme_to_smile`

参数：

- `image_path`：本地图片路径，必填
- `category`：必填，明确指定分类
- `description`：可选，分类描述
- `save_name`：可选，保存后的文件名

## 说明

- 工具本身不会自动分类；应由 LLM 先根据分类目录判断后再传入 `category`。
- 插件只提供 `astrbot_plugin_angel_smile/default/memes_data.json` 作为默认分类目录，表情素材由 LLM 后续自行偷取补齐。
- 工具只返回给 LLM 调用结果，不会主动向用户发送任何提示消息。
