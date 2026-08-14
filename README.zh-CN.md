# Conversation-Improvement

**中文** | [English](README.md) | [日本語](README.ja.md)

面向对话式 AI 的视觉表达与持久图片记忆插件。

## 功能

- 用户可以明确要求生成新图，或找回已经归档的旧图。
- 按创建时间、语义标签、来源和 SHA-256 标识保存图片文件。
- 自动表情优先复用图库中匹配的图片，找不到才生成新图。
- 用户说“以前的图片”时只检索归档，不重新生成替代品。
- 自动视觉表达保持克制：严肃聊天、编程、学习、调试、隐私、健康和痛苦倾诉场景会被禁止。
- 支持永久角色参考图、预设图片/GIF 目录、或仅明确要求时生成。
- 自动表情图使用 Q 版、留白背景、单人、可见手部动作和自然表情的固定风格。

## 当前 Hermes Agent 集成

本仓库当前提供 Hermes Agent 原生插件，包含配置、生成、归档搜索和可选表情包预生成工具。

```bash
hermes plugins install FirmaSpring/Conversation-Improvement --enable
```

## 重要隐私行为

- 运行时数据保存在 `$HERMES_HOME/conversation-improvement/`。
- API Key 不写入插件配置。插件可使用 Hermes 凭据池引用或环境变量名。
- 默认不归档原始生图提示词。
- 生成和导入的媒体保存在本地图库，直到用户自行删除。

## 跨 Agent 路线

策略引擎和本地图库格式可以跨 Agent 共享，但完整接入需要宿主提供三类能力：

1. 图片生成 Provider 或工具；
2. 向用户发送图片/GIF 的能力；
3. 用于执行策略判断的每会话 Hook 或 Middleware。

| 接入方式 | 状态 | 说明 |
| --- | --- | --- |
| Hermes Agent 原生插件 | 已可用 | 本仓库已提供。 |
| 可共享策略/图库核心 | 计划中 | 将做成框架无关的 Python 包。 |
| MCP | 仍需研究 | MCP 可暴露归档、搜索、生成操作，但不能单独保证宿主的自动消息 Hook 或媒体发送。 |
| OpenClaw / Claude Code / Codex / OpenCode / Cursor / VS Code / Cline / Continue | 仍需适配研究 | 每个宿主实测前，不宣称已兼容。 |

## 开发

```bash
python -m pytest -q
```

## 许可证

MIT
