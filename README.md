# ConversationImprovement for Hermes Agent

ConversationImprovement adds restrained visual expression and a permanent, searchable image memory to [Hermes Agent](https://github.com/NousResearch/hermes-agent). It reuses Hermes' configured `image_generate` tool instead of introducing another image provider.

## Behavior

- Explicit image requests are allowed immediately.
- Every request searches the permanent library before any provider call. A matching image is reused by default, including on a new chat; an explicit-new request may bypass reuse only with `force_new=true` after the user unmistakably asks for a newly created current image.
- Automatic image or GIF expressions are enabled by default, but only for playful contexts after a deterministic probability gate.
- Automatic media is blocked in serious, coding, study, health, privacy, and distress contexts.
- Existing library images may be reused at any time when contextually appropriate, including outside automatic-generation gates. Reuse has no cooldown, probability gate, session ceiling, or serious-topic block; it must still be relevant and non-repetitive.
- Automatic reactions search the permanent library first and generate only when no matching media exists.
- Historical image requests never generate replacements; they return only archived media.
- Newly generated automatic reactions use a chibi sticker style, a blank white or transparent-looking background, and lively natural expressions rather than stiff poses.
- Ordinary social chat has a 32% eligible-turn chance, playful chat 65%, and the fourth consecutive eligible casual turn is guaranteed. Defaults use a 5-turn cooldown and a 20-item session ceiling.
- Professional coding, study, debugging, long-task, privacy, health, and serious emotional contexts remain blocked from automatic *generation*, while fitting existing images may still be sent when useful.
- Every generated image requires a concise human-readable label such as `拥抱-开心`. The label is stored as metadata and embedded in its archived filename, alongside semantic tags.
- Generated media is copied to a profile-scoped permanent library with UTC creation time, relevant event date, prompt, source, SHA-256 identity, and semantic tags.
- Time-specific and historical images record an `event_date` in `YYYY-MM-DD`; requests for older images search the permanent library by tags, prompt text, and inclusive date range, and never generate replacements.

## Modes

| Mode | Behavior |
| --- | --- |
| `reference` | Keep one character reference image and pass it to Hermes image generation for visual consistency. |
| `preset` | Import PNG, JPEG, WebP, and GIF files from a directory. Folder names and filenames become searchable tags. |
| `per_request` | Generate only after an explicit user request. Automatic expressions are disabled. |

When enhancement is enabled, setup requires all three connection values: `base_url`, an API key source, and the image model name. The API key itself is stored only through Hermes' credential pool or an environment variable, never in plugin configuration.

After setup, the user may optionally pregenerate a starter pack: reaction memes, landscapes, or a free-form custom description. Character generations always append a hard single-subject guard requiring exactly one person and forbidding a second, duplicated, reflected, or background person. Landscape starter images forbid people entirely.

## Install

After publishing or forking this repository:

```bash
hermes plugins install OWNER/ConversationImprovement --enable
```

For local development, copy or link the repository into the active profile's plugin directory as `conversation-improvement`, then enable it:

```bash
hermes plugins enable conversation-improvement --no-allow-tool-override
```

Restart the Hermes gateway or desktop application after installation. On the first turn of the next new conversation, the assistant asks whether to enable enhancement and then asks for a mode. The portable fallback is:

```text
/conversation-improvement setup
```

Use `/conversation-improvement status`, `enable`, or `disable` at any time.

## Data and privacy

Runtime data stays under:

```text
$HERMES_HOME/conversation-improvement/
├── config.json
└── library/
    ├── index.json
    └── media/
```

The plugin does not store API keys. Image provider credentials remain managed by Hermes. Removing an original preset directory does not remove archived copies; delete the plugin data directory when permanent deletion is required.

For a custom endpoint, configuration stores only the base URL, model name, and a credential source reference. Existing Hermes credential pools such as `custom:pokeapi` can be reused without copying the key. When no pool exists, add the key through Hermes' masked prompt rather than chat:

```bash
hermes auth add <provider> --type api-key
```

## Development

```bash
python -m pytest -q
```

The plugin targets Hermes Agent 0.20 or newer and uses only Python's standard library at runtime.

## Current scope

Version 0.1 provides the native backend plugin and cross-platform chat setup. A richer desktop settings panel can be added without changing the archive format or policy engine. Direct GIF/video generation depends on the media providers enabled in Hermes; preset GIF reuse works now.

## License

MIT