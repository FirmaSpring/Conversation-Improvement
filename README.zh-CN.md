# Conversation-Improvement

**中文** | [English](README.md) | [日本語](README.ja.md)

面向对话式 AI 的跨 Agent 视觉表达与持久图片记忆项目。它不再定位为 Hermes Agent 专属项目：策略与图库核心可以共享，每个受支持的 Agent 使用各自的原生插件适配器。

## 功能

- 明确生成新图，或找回已经归档的旧图。
- 按创建时间、语义标签、来源和 SHA-256 标识保存媒体。
- 自动表情优先复用匹配的图库媒体，找不到才生成新图。
- 用户要求“以前的图片”时只检索归档，不重新生成替代品。
- 严肃聊天、编程、学习、调试、隐私、健康和痛苦倾诉场景禁止自动媒体。
- 支持永久角色参考图、预设图片/GIF 目录、或仅在明确要求时生成。
- 自动反应图保持 Q 版、单人、手部动作清楚、表情自然、背景留白。
- API Key 不写入插件配置；默认不归档原始生图提示词。

## 架构

```text
Conversation-Improvement
├── 共享策略引擎
├── 持久图片图库
├── 与 Provider 无关的生成/归档操作
└── Agent 原生适配器
    ├── Hermes Agent
    ├── OpenClaw
    ├── ElizaOS
    ├── Open WebUI
    ├── Botpress
    └── 其他已验证的对话插件宿主
```

本项目有意**不把 MCP 作为主要分发层**。完整的对话视觉增强依赖宿主原生能力：逐轮 Hook、会话状态、图片生成和媒体发送。原生插件适配器才能正确集成这些行为。

## 适配器约定

完整原生适配器应尽量映射宿主提供的以下能力：

1. 插件生命周期与持久设置；
2. 逐轮 Hook、事件或 Middleware；
3. 工具注册；
4. 图片生成 Provider 调度；
5. 向当前对话发送图片/GIF；
6. 每会话冷却与使用次数状态；
7. 首次设置界面或命令。

如果某个宿主的插件 API 缺少其中一项，也可以提供受限适配器，但必须在文档中写明限制，不能宣称为完整兼容。

## Agent 兼容性

| Agent / 宿主 | 原生扩展机制 | 项目状态 |
| --- | --- | --- |
| Hermes Agent | 原生 Python 插件、工具、Hook、命令 | **已实现并通过测试** |
| OpenClaw | 原生 TypeScript 插件、类型化对话 Hook、工具、会话附件发送 | **适配器已实现；SDK 编译与 3 项行为测试通过；仍待真实 Gateway/频道验收** |
| ElizaOS | 原生插件、事件、Provider、Evaluator、Action、Memory 与媒体回调 | **适配器已实现；TypeScript 编译与 6 项行为测试通过；仍待真实运行时、数据库与连接器验收** |
| Open WebUI | 原生 Filter、Tool、Valve、消息与文件事件 | **适配器已实现；5 项测试、Python 编译与 wheel 构建通过；仍待真实 Open WebUI 验收** |
| Botpress | 原生 Hook、Integration、Action、分层状态与媒体卡片 | **受限原生模块已实现；官方 CLI 类型生成、TypeScript 编译与 6 项行为测试通过；媒体由宿主 Bot Integration 使用预备 payload 发送** |
| Dify / LibreChat / Rasa / Flowise | 存在原生扩展面，但通用逐轮 Hook、设置或可靠媒体能力至少有一项受限 | 只考虑受限集成，不作为完整自动表情目标 |
| 编程 Agent 与缺少合适原生插件 API 的宿主 | 不符合对话原生插件目标 | Conversation-Improvement 不支持 |

“计划中”不代表现在已经兼容。只有适配器完成并在对应宿主中真实运行后，才会标记为支持。

## 原生适配器

- `adapters/openclaw`：OpenClaw 原生 TypeScript 适配器
- `adapters/elizaos`：ElizaOS 原生 TypeScript 插件
- `adapters/open-webui`：Open WebUI Filter/Tools Python 适配器
- `adapters/botpress`：Botpress 原生模块，媒体交付由宿主 Integration 负责

## Hermes Agent 适配器

Hermes 是第一个完成的适配器，目前提供配置、图片生成、归档检索、自动表情策略注入、媒体归档和可选初始表情包生成。

```bash
hermes plugins install FirmaSpring/Conversation-Improvement --enable
```

Hermes 适配器运行时数据保存在：

```text
$HERMES_HOME/conversation-improvement/
```

API Key 不写入插件配置。Hermes 适配器可使用凭据池引用或环境变量名。生成与导入的媒体只保存在本地，直到用户主动删除。

## 开发

```bash
python -m pytest -q
```

新增适配器应复用策略与图库模块，不要复制业务逻辑。每个适配器必须说明宿主权限、媒体发送行为、存储位置和不支持的功能。

## 许可证

MIT
