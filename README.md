# Conversation-Improvement

[中文](README.zh-CN.md) | **English** | [日本語](README.ja.md)

A visual-expression and persistent image-memory plugin for conversational AI.

## What it does

- Lets users explicitly request a new image or an older archived image.
- Stores image files with creation time, semantic tags, source, and SHA-256 identity.
- Reuses matching archive media before generating new automatic reaction media.
- Never regenerates an image when the user asks for an older image; it searches the archive instead.
- Keeps automatic visual reactions restrained: serious, coding, study, debugging, privacy, health, and distress contexts are blocked.
- Supports a permanent character reference image, a preset image/GIF directory, or explicit-request-only generation.
- Uses a chibi reaction style with a blank background, one subject, visible hand gestures, and natural expressions for automatic reactions.

## Current Hermes Agent integration

This repository currently ships a native Hermes Agent plugin with tools for configuration, generation, archive search, and optional starter-pack generation.

```bash
hermes plugins install FirmaSpring/Conversation-Improvement --enable
```

## Important privacy behavior

- Runtime data stays under `$HERMES_HOME/conversation-improvement/`.
- API keys are not stored in plugin configuration. The plugin can use a Hermes credential-pool reference or an environment-variable name.
- Raw generation prompts are not archived by default.
- Generated and imported media remain in the local library until the user deletes them.

## Cross-agent roadmap

The policy engine and local image-library format can be shared across agents, but a full integration needs three host-specific capabilities:

1. an image-generation provider or tool;
2. a way to deliver images/GIFs to the user;
3. per-conversation hooks or middleware for policy decisions.

| Integration | Status | Notes |
| --- | --- | --- |
| Hermes Agent native plugin | Available | This repository ships it. |
| Shared policy/library core | Planned | Framework-neutral Python package. |
| MCP | Research required | MCP can expose archive/search/generation operations, but cannot by itself guarantee host-side automatic-message hooks or media delivery. |
| OpenClaw / Claude Code / Codex / OpenCode / Cursor / VS Code / Cline / Continue | Adapter research required | Compatibility must be tested per host before it is claimed. |

## Development

```bash
python -m pytest -q
```

## License

MIT
