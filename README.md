# Conversation-Improvement

[中文](README.zh-CN.md) | **English** | [日本語](README.ja.md)

A cross-agent visual-expression and persistent image-memory project for conversational AI. The project is not limited to Hermes Agent: its policy and image-library core are reusable, while each supported agent receives a native plugin adapter.

## Features

- Explicitly generate a new image or retrieve an archived image.
- Store media with creation time, semantic tags, source, and SHA-256 identity.
- Reuse matching reaction media before generating anything new.
- Never regenerate a replacement when the user asks for an older image.
- Block automatic media in serious, coding, study, debugging, privacy, health, and distress contexts.
- Support a permanent character reference, a preset image/GIF directory, or explicit-request-only generation.
- Generate restrained chibi reactions with one subject, visible hand gestures, natural expressions, and a blank background.
- Keep API keys out of plugin configuration and avoid archiving raw prompts by default.

## Architecture

```text
Conversation-Improvement
├── shared policy engine
├── persistent image library
├── provider-independent generation/archive operations
└── native agent adapters
    ├── Hermes Agent
    ├── OpenClaw
    ├── OpenCode
    ├── Gemini CLI
    └── other verified plugin hosts
```

This project intentionally does **not** use MCP as its primary distribution layer. Complete visual conversation enhancement depends on host-native behavior: per-turn hooks, session state, image generation, and media delivery. A native plugin adapter can integrate those capabilities correctly.

## Adapter contract

A full native adapter should map as many of these host capabilities as the host provides:

1. plugin lifecycle and persistent settings;
2. per-turn hook, event, or middleware;
3. tool registration;
4. image-generation provider dispatch;
5. image/GIF delivery to the active conversation;
6. per-conversation cooldown and usage state;
7. first-run setup UI or command.

A host can still receive a limited adapter when its plugin API lacks one capability, but the limitation must be documented instead of being presented as full compatibility.

## Agent compatibility

| Agent / host | Native extension mechanism | Project status |
| --- | --- | --- |
| Hermes Agent | Native Python plugins, tools, hooks, commands | **Implemented and tested** |
| OpenClaw | Official plugin system | Adapter planned; not yet verified |
| OpenCode | Official plugins and hooks | Adapter planned; not yet verified |
| Gemini CLI | Official extensions and hooks | Adapter planned; not yet verified |
| Claude Code | Official plugin mechanism | Adapter research planned; not yet verified |
| Other plugin-capable agents | Host-specific native adapter | Added only after implementation and testing |
| Hosts without a suitable native plugin system | None suitable | Not supported by this project |

“Planned” does not mean compatible today. An agent is marked supported only after its adapter is implemented and exercised against that host.

## Hermes Agent adapter

Hermes is the first completed adapter and currently provides configuration, generation, archive search, automatic-reaction policy injection, media archiving, and optional starter-pack generation.

```bash
hermes plugins install FirmaSpring/Conversation-Improvement --enable
```

Runtime data for the Hermes adapter is stored under:

```text
$HERMES_HOME/conversation-improvement/
```

API keys are not stored in plugin configuration. The Hermes adapter can use a credential-pool reference or an environment-variable name. Generated and imported media remains local until the user deletes it.

## Development

```bash
python -m pytest -q
```

New adapters should reuse the policy and library modules rather than duplicating behavior. Every adapter must document its host permissions, media-delivery behavior, storage location, and unsupported features.

## License

MIT
