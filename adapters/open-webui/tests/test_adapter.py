from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from open_webui_conversation_improvement import Filter, Tools, reset_state


def run(awaitable):
    return asyncio.run(awaitable)


def metadata(chat_id: str = "chat-1") -> dict:
    return {"chat_id": chat_id, "message_id": "message-1"}


def user(user_id: str = "user-1") -> dict:
    return {"id": user_id, "email": f"{user_id}@example.test"}


def setup_function() -> None:
    reset_state()


def test_filter_inlet_applies_policy_and_scopes_state() -> None:
    function = Filter()
    function.valves.probability = 0.0
    body = {"messages": [{"role": "user", "content": "Please debug this code"}]}

    result = run(function.inlet(body, __user__=user(), __metadata__=metadata()))

    assert result is body
    assert result["messages"][0]["role"] == "system"
    assert "blocked this turn (sensitive_context)" in result["messages"][0]["content"]
    assert function.state_for(user(), metadata()).turn == 1
    assert function.state_for(user("other"), metadata()).turn == 0


def test_filter_outlet_removes_private_policy_message() -> None:
    function = Filter()
    body = {"messages": [{"role": "user", "content": "hello"}]}
    run(function.inlet(body, __user__=user(), __metadata__=metadata()))

    result = run(function.outlet(body, __user__=user(), __metadata__=metadata()))

    assert all("Conversation-Improvement policy" not in str(message.get("content")) for message in result["messages"])


def test_archive_and_search_are_scoped_and_prompt_storage_is_opt_in(tmp_path: Path) -> None:
    media = tmp_path / "reaction.png"
    media.write_bytes(b"not-a-real-png-but-stable")
    tools = Tools()
    tools.valves.data_directory = str(tmp_path / "library")

    archived = run(tools.archive_media(
        path=str(media), prompt="private prompt", tags=["happy", "reaction"],
        __user__=user(), __metadata__=metadata(),
    ))
    found = run(tools.search_media(
        query="happy", __user__=user(), __metadata__=metadata(),
    ))
    other = run(tools.search_media(
        query="happy", __user__=user("other"), __metadata__=metadata(),
    ))

    assert archived["success"] is True
    assert found["images"][0]["prompt"] == ""
    assert other["images"] == []


def test_send_media_emits_official_image_and_file_events(tmp_path: Path) -> None:
    image = tmp_path / "reaction.png"
    image.write_bytes(b"png")
    document = tmp_path / "notes.txt"
    document.write_text("hello", encoding="utf-8")
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    tools = Tools()
    image_result = run(tools.send_media(
        location=str(image), title="Reaction", __event_emitter__=emit,
        __user__=user(), __metadata__=metadata(),
    ))
    file_result = run(tools.send_media(
        location=str(document), title="Notes", __event_emitter__=emit,
        __user__=user(), __metadata__=metadata(),
    ))

    assert image_result["success"] and file_result["success"]
    assert events[0]["type"] == "chat:message:files"
    assert events[0]["data"]["files"][0]["type"] == "image"
    assert events[0]["data"]["files"][0]["url"].startswith("data:image/png;base64,")
    assert base64.b64decode(events[0]["data"]["files"][0]["url"].split(",", 1)[1]) == b"png"
    assert events[1]["data"]["files"][0]["type"] == "file"


def test_tools_user_valves_disable_automatic_media(tmp_path: Path) -> None:
    image = tmp_path / "reaction.png"
    image.write_bytes(b"png")
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)

    tools = Tools()
    disabled_user = {**user(), "valves": {"allow_automatic_media": False}}
    result = run(tools.send_media(
        location=str(image), automatic=True, __event_emitter__=emit,
        __user__=disabled_user, __metadata__=metadata(),
    ))

    assert result["success"] is False
    assert result["error"] == "automatic_media_disabled_for_user"
    assert events == []
