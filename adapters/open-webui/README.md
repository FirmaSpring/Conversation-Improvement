# Open WebUI native adapter

A native Open WebUI **Filter Function** plus **Tools** for Conversation-Improvement. It uses Open WebUI's official `Filter`, `Tools`, `Valves`, `UserValves`, injected special arguments, and `__event_emitter__` interfaces. It does not require MCP.

## Capabilities

- `Filter.inlet` evaluates the latest user message on every turn and injects private policy guidance.
- `Filter.outlet` strips that guidance before the response body is displayed or persisted.
- Policy counters are isolated by Open WebUI user ID and chat ID, including cooldown, casual streak, and automatic-use limit.
- `archive_media` stores server-local images, GIFs, or files in a content-addressed archive.
- `search_media` searches the current user/chat archive by prompt, tags, and date.
- `send_media` emits Open WebUI's official `chat:message:files` event. Images/GIFs use file type `image`; other media uses `file`.
- Local media is emitted as a data URL. Remote media must use HTTPS and can be disabled with a Valve.

The adapter intentionally does not embed an image provider. For a new image, use an image-generation capability already configured in Open WebUI, then call `archive_media` and `send_media`.

## Install in Open WebUI

Open WebUI discovers metadata from the module-level docstring (`title`, `author`, `version`, `license`, `description`, and `requirements`). Install the same Python file twice because Open WebUI manages Filters and Tools as separate Function types:

1. Open **Workspace → Functions**.
2. Create a **Filter Function**, paste `open_webui_conversation_improvement.py`, save it, enable it, and attach it globally or to the desired models.
3. Create a **Tools Function**, paste the same file, save it, and enable it for the desired models.
4. In the Filter editor, configure the admin `Valves` if desired.
5. In the Tools editor, set `data_directory` to persistent server storage. In containers, mount that directory as a volume.
6. Users may disable unsolicited visuals with the per-user `allow_automatic_media` User Valve.

Open WebUI instantiates the class matching the selected Function type (`Filter` or `Tools`). The adapter does not require API keys and must not be configured with secrets.

## Native signatures

Open WebUI injects these official special arguments when declared:

- `__user__`: current user data and per-user valves
- `__metadata__`: chat/conversation metadata used for scoping
- `__event_emitter__`: asynchronous event emitter used by `send_media`

The emitted payload is:

```json
{
  "type": "chat:message:files",
  "data": {
    "files": [{"type": "image", "url": "data:image/png;base64,...", "name": "title"}]
  }
}
```

## Development

```bash
cd adapters/open-webui
python -m pip install -e ".[test]"
python -m pytest -q
python -m compileall -q open_webui_conversation_improvement.py tests
```

Tests cover per-turn inlet/outlet behavior, user/chat state isolation, user valves, archive/search scope isolation, image events, file events, and the automatic-policy gate.

## Operational notes

- State counters are process-local. They survive ordinary turns in one Open WebUI worker but reset on process restart; media archives are persistent.
- A multi-worker deployment maintains counters independently per worker. The durable archive remains scoped because its directory key is derived from user and chat IDs.
- Archive paths are server-local paths, not browser paths.
- Prompt persistence defaults off. Enable `store_prompts` only if local privacy policy permits it.
