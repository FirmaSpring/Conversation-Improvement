"""
title: Conversation Improvement
author: MoonsvnLyn
version: 0.1.0
license: MIT
description: Per-turn visual-expression policy and scoped media memory for Open WebUI.
requirements: pydantic>=2.0
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Awaitable, Callable, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field


POLICY_MARKER = "[conversation-improvement-policy]"
EXPLICIT_TERMS = (
    "发张图", "发图片", "生成图片", "生成一张", "画一张", "看看你", "看你",
    "自拍", "照片", "表情包", "gif", "image", "picture", "show me",
)
SENSITIVE_TERMS = (
    "报错", "错误", "调试", "代码", "考试", "作业", "学习", "难受", "痛苦",
    "生病", "隐私", "密码", "事故", "去世", "分手", "严肃", "debug", "error",
    "项目", "重构", "部署", "测试", "终端", "命令", "算法", "论文", "报告", "分析", "任务",
    "project", "refactor", "deploy", "terminal", "command", "algorithm", "report", "analysis", "task",
)
PLAYFUL_TERMS = (
    "哈哈", "开心", "好耶", "可爱", "调皮", "惊喜", "逗", "笑死", "庆祝",
    "嘿嘿", "有意思", "funny", "cute", "yay", "lol",
)
AFFECTIONATE_TERMS = (
    "抱抱", "拥抱", "抱一下", "亲亲", "亲一口", "飞吻", "贴贴", "蹭蹭",
    "哈气", "呵气", "暖暖", "摸摸头", "摸头", "牵手", "拉手",
)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
EventEmitter = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class SessionState:
    """Policy counters isolated to one Open WebUI user and chat."""

    turn: int = 0
    last_auto_turn: int | None = None
    automatic_count: int = 0
    casual_streak: int = 0
    pending_automatic: bool = False


@dataclass(frozen=True)
class Decision:
    allowed: bool
    kind: str
    reason: str


_STATE: dict[tuple[str, str], SessionState] = {}
_STATE_LOCK = RLock()


def reset_state() -> None:
    """Clear process-local state; primarily useful for tests and hot reloads."""
    with _STATE_LOCK:
        _STATE.clear()


def _identity(__user__: dict[str, Any] | None, __metadata__: dict[str, Any] | None) -> tuple[str, str]:
    user = __user__ or {}
    metadata = __metadata__ or {}
    user_id = str(user.get("id") or user.get("email") or "anonymous")
    chat_id = str(metadata.get("chat_id") or metadata.get("conversation_id") or "default")
    return user_id, chat_id


def _state_for(__user__: dict[str, Any] | None, __metadata__: dict[str, Any] | None) -> SessionState:
    key = _identity(__user__, __metadata__)
    with _STATE_LOCK:
        return _STATE.setdefault(key, SessionState())


def _latest_user_text(body: dict[str, Any]) -> str:
    for message in reversed(body.get("messages") or []):
        if message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    return ""


def _decide(message: str, state: SessionState, valves: Any) -> Decision:
    text = message.casefold()
    if any(term in text for term in EXPLICIT_TERMS):
        return Decision(True, "explicit", "user_requested")
    if any(term in text for term in SENSITIVE_TERMS):
        return Decision(False, "none", "sensitive_context")
    if not valves.enabled or not valves.automatic_media:
        return Decision(False, "none", "automatic_media_disabled")
    if state.automatic_count >= valves.max_per_chat:
        return Decision(False, "none", "chat_limit")
    if state.last_auto_turn is not None and state.turn - state.last_auto_turn < valves.cooldown_turns:
        return Decision(False, "none", "cooldown")
    if any(term in text for term in AFFECTIONATE_TERMS):
        return Decision(True, "automatic", "affectionate_action")
    if state.casual_streak + 1 >= valves.force_after_casual_turns:
        return Decision(True, "automatic", "casual_guarantee")
    seed = f"{state.turn}:{text}".encode()
    sample = int.from_bytes(hashlib.sha256(seed).digest()[:8], "big") / 2**64
    threshold = valves.playful_probability if any(term in text for term in PLAYFUL_TERMS) else valves.probability
    return Decision(sample < threshold, "automatic" if sample < threshold else "none", "probability_gate")


def _scope_root(base: str, __user__: dict[str, Any] | None, __metadata__: dict[str, Any] | None) -> Path:
    user_id, chat_id = _identity(__user__, __metadata__)
    digest = hashlib.sha256(f"{user_id}\0{chat_id}".encode()).hexdigest()[:24]
    root = Path(base).expanduser() / digest
    root.mkdir(parents=True, exist_ok=True)
    return root


class MediaLibrary:
    """Small JSON index and content-addressed media store for one scope."""

    def __init__(self, root: Path):
        self.root = root
        self.media = root / "media"
        self.index = root / "index.json"
        self.media.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict[str, Any]]:
        try:
            value = json.loads(self.index.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, rows: list[dict[str, Any]]) -> None:
        temporary = self.index.with_suffix(".tmp")
        temporary.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.index)

    def archive(self, source: Path, prompt: str, tags: list[str], source_kind: str) -> dict[str, Any]:
        source = source.expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        clean_tags = sorted({tag.strip() for tag in tags if tag.strip()})
        rows = self._load()
        for row in rows:
            if row.get("id") == digest:
                row["tags"] = sorted(set(row.get("tags", [])) | set(clean_tags))
                self._save(rows)
                return row
        now = datetime.now(timezone.utc)
        destination = self.media / f"{now:%Y-%m-%d}_{digest[:12]}{source.suffix.lower() or '.bin'}"
        shutil.copy2(source, destination)
        row = {
            "id": digest, "path": str(destination), "created_at": now.isoformat(),
            "prompt": prompt, "tags": clean_tags, "source": source_kind,
        }
        rows.append(row)
        self._save(rows)
        return row

    def search(self, query: str, date_from: str, date_to: str, limit: int) -> list[dict[str, Any]]:
        terms = query.casefold().split()
        results = []
        for row in reversed(self._load()):
            created = str(row.get("created_at", ""))[:10]
            haystack = " ".join([str(row.get("prompt", "")), *row.get("tags", [])]).casefold()
            if date_from and created < date_from or date_to and created > date_to:
                continue
            if terms and not all(term in haystack for term in terms):
                continue
            results.append(row)
            if len(results) >= max(1, min(limit, 20)):
                break
        return results


class Filter:
    """Open WebUI Filter Function applying visual-media policy to every chat turn."""

    class Valves(BaseModel):
        enabled: bool = Field(True, description="Enable per-turn policy injection.")
        automatic_media: bool = Field(True, description="Allow restrained automatic visual reactions.")
        probability: float = Field(0.32, ge=0.0, le=1.0)
        playful_probability: float = Field(0.65, ge=0.0, le=1.0)
        force_after_casual_turns: int = Field(4, ge=1)
        cooldown_turns: int = Field(5, ge=0)
        max_per_chat: int = Field(20, ge=0)
        priority: int = Field(0, description="Open WebUI filter ordering priority.")

    class UserValves(BaseModel):
        allow_automatic_media: bool = Field(True, description="Allow automatic visual reactions for this user.")

    def __init__(self) -> None:
        self.valves = self.Valves()

    def state_for(self, __user__: dict[str, Any], __metadata__: dict[str, Any]) -> SessionState:
        return _state_for(__user__, __metadata__)

    async def inlet(
        self, body: dict[str, Any], __user__: dict[str, Any] | None = None,
        __metadata__: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate the current user turn and inject private model guidance."""
        state = _state_for(__user__, __metadata__)
        state.turn += 1
        decision = _decide(_latest_user_text(body), state, self.valves)
        user_valves = (__user__ or {}).get("valves") or {}
        if decision.kind == "automatic" and not user_valves.get("allow_automatic_media", True):
            decision = Decision(False, "none", "automatic_media_disabled_for_user")
        state.pending_automatic = decision.allowed and decision.kind == "automatic"
        state.casual_streak = 0 if state.pending_automatic else state.casual_streak + 1
        if decision.kind == "explicit":
            guidance = "Explicit media is allowed. Search archived media for historical wording; create new media only when requested."
        elif decision.allowed:
            guidance = "One restrained visual reaction is allowed. Search media first, then send a match or use the host's configured image generator."
        else:
            guidance = f"Automatic media is blocked this turn ({decision.reason}); answer with text unless media was explicitly requested."
        body.setdefault("messages", []).insert(0, {
            "role": "system", "content": f"{POLICY_MARKER} Conversation-Improvement policy: {guidance}",
        })
        return body

    async def outlet(
        self, body: dict[str, Any], __user__: dict[str, Any] | None = None,
        __metadata__: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Remove private guidance so it is not persisted or displayed."""
        body["messages"] = [
            message for message in body.get("messages", [])
            if POLICY_MARKER not in str(message.get("content", ""))
        ]
        return body


class Tools:
    """Open WebUI native tools for scoped media archive, search, and delivery."""

    class Valves(BaseModel):
        data_directory: str = Field(
            str(Path.home() / ".open-webui" / "conversation-improvement"),
            description="Server-local root for scoped media archives.",
        )
        store_prompts: bool = Field(False, description="Persist generation prompts in the archive index.")
        allow_remote_media: bool = Field(True, description="Allow HTTPS media URLs to be emitted without downloading.")

    class UserValves(BaseModel):
        allow_automatic_media: bool = Field(True, description="Allow automatic visual reactions for this user.")

    def __init__(self) -> None:
        self.valves = self.Valves()

    def _library(self, user: dict[str, Any] | None, metadata: dict[str, Any] | None) -> MediaLibrary:
        return MediaLibrary(_scope_root(self.valves.data_directory, user, metadata))

    async def archive_media(
        self,
        path: str,
        prompt: str = "",
        tags: list[str] | None = None,
        source: Literal["generated", "preset", "reference", "imported"] = "imported",
        __user__: dict[str, Any] | None = None,
        __metadata__: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Archive one server-local image/GIF/file in the current user+chat scope.

        :param path: Absolute or home-relative server-local media path.
        :param prompt: Optional source/generation prompt; stored only when the admin valve permits it.
        :param tags: Searchable semantic tags.
        :param source: Media provenance category.
        """
        try:
            row = self._library(__user__, __metadata__).archive(
                Path(path), prompt if self.valves.store_prompts else "", list(tags or []), source,
            )
            return {"success": True, "image": row}
        except (OSError, ValueError) as exc:
            return {"success": False, "error": str(exc)}

    async def search_media(
        self,
        query: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int = 5,
        __user__: dict[str, Any] | None = None,
        __metadata__: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search media in the current user+chat scope by tags, prompt text, and date.

        :param query: Space-separated terms; every term must match.
        :param date_from: Optional inclusive YYYY-MM-DD lower bound.
        :param date_to: Optional inclusive YYYY-MM-DD upper bound.
        :param limit: Maximum number of newest matches, from 1 through 20.
        """
        rows = self._library(__user__, __metadata__).search(query, date_from, date_to, limit)
        return {"success": True, "images": rows}

    async def send_media(
        self,
        location: str,
        title: str = "Conversation media",
        automatic: bool = False,
        __event_emitter__: EventEmitter | None = None,
        __user__: dict[str, Any] | None = None,
        __metadata__: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Display an image/GIF or attach a file using Open WebUI's official event emitter.

        :param location: HTTPS URL or server-local path returned by search_media/archive_media.
        :param title: Visible attachment name.
        :param automatic: True only for policy-approved unsolicited reactions.
        """
        if automatic and not ((__user__ or {}).get("valves") or {}).get("allow_automatic_media", True):
            return {"success": False, "error": "automatic_media_disabled_for_user"}
        if __event_emitter__ is None:
            return {"success": False, "error": "event_emitter_unavailable"}
        state = _state_for(__user__, __metadata__)
        if automatic and not state.pending_automatic:
            return {"success": False, "error": "automatic_media_not_approved_this_turn"}
        parsed = urlparse(location)
        is_remote = parsed.scheme in {"http", "https"}
        if is_remote:
            if parsed.scheme != "https" or not self.valves.allow_remote_media:
                return {"success": False, "error": "remote_media_not_allowed"}
            url = location
            suffix = Path(parsed.path).suffix.casefold()
        else:
            path = Path(location).expanduser().resolve()
            if not path.is_file():
                return {"success": False, "error": f"media_not_found: {path}"}
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            url = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
            suffix = path.suffix.casefold()
        file_type = "image" if suffix in IMAGE_SUFFIXES else "file"
        await __event_emitter__({
            "type": "chat:message:files",
            "data": {"files": [{"type": file_type, "url": url, "name": title}]},
        })
        if automatic:
            state.pending_automatic = False
            state.last_auto_turn = state.turn
            state.automatic_count += 1
        return {"success": True, "type": file_type, "title": title}
