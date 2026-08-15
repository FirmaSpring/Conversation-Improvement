from __future__ import annotations

import json
import threading
from pathlib import Path

from .conversation_improvement.policy import ExpressionPolicy, SessionState
from .schemas import ARCHIVE_SCHEMA, CONFIGURE_SCHEMA, GENERATE_SCHEMA, PREGENERATE_SCHEMA, SEARCH_SCHEMA
from .tools import (
    archive,
    build_pregeneration_requests,
    configure,
    find_reusable,
    generate_custom,
    load_config,
    prepare_generation_args,
    save_config,
    search,
)


_session_state: dict[str, SessionState] = {}
_pending_automatic: set[str] = set()
_lock = threading.Lock()


def _result_succeeded(result: object) -> bool:
    try:
        payload = json.loads(result) if isinstance(result, str) else result
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and bool(payload.get("success"))


def _consume_automatic(session_id: str) -> None:
    if not session_id:
        return
    with _lock:
        if session_id not in _pending_automatic:
            return
        _pending_automatic.discard(session_id)
        state = _session_state.get(session_id)
        if state:
            _session_state[session_id] = SessionState(
                session_id=state.session_id,
                turn=state.turn,
                last_auto_turn=state.turn,
                automatic_count=state.automatic_count + 1,
                casual_streak=0,
            )


def _setup_context() -> str:
    return (
        "ConversationImprovement is installed but has not been configured. Call the clarify tool now with one short question "
        "and exactly two choices: Enable visual conversation enhancement globally for this Hermes profile; Do not enable. "
        "If the user enables it, call clarify again with exactly three choices: permanent reference image; preset image/GIF directory; "
        "generate separately on each explicit request. Default automatic expressions are enabled but restrained. "
        "After the user chooses a mode, collect the remaining non-secret settings in one question: provider choice and, for custom OpenAI "
        "compatible endpoints, base_url, model, protocol (Images API or Chat Completions), and either a Hermes credential provider id or API key environment variable name. "
        "Never request or accept an API key in chat. If no reusable credential exists, direct the user to the masked `hermes auth add` prompt. "
        "Then call conversation_image_configure once with the complete setup. After it succeeds, ask one final question using clarify: "
        "whether to pregenerate nothing, reaction memes, landscapes, or a custom starter description. Custom accepts free text. "
        "All character images must contain exactly one person and landscapes must contain no people. Call conversation_image_pregenerate only after consent."
    )


def _pre_llm_call(session_id: str = "", user_message: str = "", is_first_turn: bool = False, **_: object):
    config = load_config()
    if not config["configured"]:
        if is_first_turn:
            return {"context": _setup_context()}
        return None
    if not config["enabled"]:
        return None
    with _lock:
        previous = _session_state.get(session_id, SessionState(session_id=session_id))
        current = SessionState(
            session_id=session_id,
            turn=previous.turn + 1,
            last_auto_turn=previous.last_auto_turn,
            automatic_count=previous.automatic_count,
            casual_streak=previous.casual_streak,
        )
        _session_state[session_id] = current
    policy = ExpressionPolicy(
        probability=float(config["probability"]),
        playful_probability=float(config["playful_probability"]),
        force_after_casual_turns=int(config["force_after_casual_turns"]),
        cooldown_turns=int(config["cooldown_turns"]),
        max_per_session=int(config["max_per_session"]),
    )
    decision = policy.decide(str(user_message), current)
    with _lock:
        if decision.reason == "sensitive_context":
            next_streak = 0
        elif decision.reason not in {"cooldown", "session_limit", "user_requested"}:
            next_streak = current.casual_streak + 1
        else:
            next_streak = current.casual_streak
        _session_state[session_id] = SessionState(
            session_id=current.session_id,
            turn=current.turn,
            last_auto_turn=current.last_auto_turn,
            automatic_count=current.automatic_count,
            casual_streak=next_streak,
        )
    common = (
        "ConversationImprovement policy: use conversation_image_generate with purpose=historical for requests about older images, "
        "purpose=explicit_new only when the user explicitly asks for a new/current image, and purpose=automatic_reaction for allowed reactions. "
        "Every generated image MUST include a concise Chinese label that identifies its expression or content, plus useful semantic tags; the label becomes part of its archived filename. "
        "For historical or time-specific images, also supply event_date in YYYY-MM-DD; the library preserves it for dated retrieval. "
        "Never regenerate an older image. Existing library images may be sent at any time when contextually appropriate: "
        "reuse has no probability gate, cooldown, session ceiling, or serious-topic block. Use judgment—send a relevant image, "
        "not a random or repetitive one. New generation remains subject to the normal automatic-expression policy."
    )
    mode = config.get("mode", "reference")
    if mode == "reference" and config.get("reference_image"):
        common += f" Use this permanent reference image for character consistency: {config['reference_image']}."
    elif mode == "preset" and config.get("preset_directory"):
        common += " Prefer conversation_image_search over generation so a matching preset image or GIF can be reused."
    elif mode == "per_request":
        common += " The configured mode is per-request generation; do not generate automatic expressions."
    if decision.kind == "explicit":
        return {"context": common + " This turn is an explicit image request. Infer historical versus explicit_new from the user's wording; when ambiguous, prefer reuse."}
    if decision.allowed and config.get("auto_expression", True) and mode != "per_request":
        with _lock:
            _pending_automatic.add(session_id)
        strength = "MUST" if decision.reason == "casual_guarantee" else "SHOULD"
        return {"context": common + f" This is ordinary social conversation and passed the automatic-expression gate ({decision.reason}). You {strength} call conversation_image_generate exactly once with purpose=automatic_reaction and concise emotion tags, then deliver the returned image. Prefer an existing matching image; do not regenerate when reuse succeeds."}
    return {"context": common + f" New automatic generation is not allowed this turn ({decision.reason}). You may still send one already-archived, contextually fitting image whenever it genuinely improves the reply; do not generate a new one unless explicitly requested."}


def _post_tool_call(tool_name: str = "", args: dict | None = None, result: object = None, session_id: str = "", **_: object):
    if tool_name != "image_generate" or not isinstance(args, dict):
        return
    try:
        payload = json.loads(result) if isinstance(result, str) else result
    except json.JSONDecodeError:
        return
    if not isinstance(payload, dict) or not payload.get("success"):
        return
    image = payload.get("host_image") or payload.get("image")
    if not isinstance(image, str) or not Path(image).is_file():
        return
    tags = ["generated"]
    prompt = str(args.get("prompt", ""))
    for tag in ("selfie", "自拍", "meme", "表情包", "happy", "开心"):
        if tag.casefold() in prompt.casefold():
            tags.append(tag)
    archive({"path": image, "prompt": prompt, "tags": tags, "label": str(args.get("label", "自动生成")), "source": "generated"})
    with _lock:
        if session_id not in _pending_automatic:
            return
        _pending_automatic.discard(session_id)
        state = _session_state.get(session_id)
        if state:
            _session_state[session_id] = SessionState(
                session_id=state.session_id, turn=state.turn,
                last_auto_turn=state.turn, automatic_count=state.automatic_count + 1,
                casual_streak=0,
            )


def _handle_slash(raw: str) -> str:
    command = raw.strip().casefold()
    if command in {"", "status"}:
        return json.dumps(load_config(), ensure_ascii=False, indent=2)
    if command in {"enable", "on"}:
        config = load_config(); config.update({"configured": True, "enabled": True}); save_config(config)
        return "ConversationImprovement enabled. Use /conversation-improvement setup to choose a mode."
    if command in {"disable", "off"}:
        config = load_config(); config.update({"configured": True, "enabled": False}); save_config(config)
        return "ConversationImprovement disabled."
    if command == "setup":
        return (
            "Choose one mode, then tell the assistant your choice: reference (one permanent reference image), "
            "preset (a tagged image/GIF directory), or per_request (generate only when explicitly requested). "
            "The assistant will call conversation_image_configure."
        )
    return "Usage: /conversation-improvement [status|setup|enable|disable]"


def register(ctx) -> None:
    ctx.register_tool(name="conversation_image_configure", toolset="conversation-improvement", schema=CONFIGURE_SCHEMA, handler=configure)
    ctx.register_tool(name="conversation_image_archive", toolset="conversation-improvement", schema=ARCHIVE_SCHEMA, handler=archive)
    ctx.register_tool(name="conversation_image_search", toolset="conversation-improvement", schema=SEARCH_SCHEMA, handler=search)
    def generate(args: dict, **kwargs: object) -> str:
        purpose = str(args.get("purpose", "explicit_new"))
        label = str(args.get("label", "")).strip()
        if purpose != "historical" and not label:
            return json.dumps({"success": False, "error": "Every generated image requires a non-empty label."}, ensure_ascii=False)
        reuse_query = str(args.get("reuse_query", "")).strip()
        if not reuse_query:
            reuse_query = " ".join(str(tag) for tag in (args.get("tags") or []) if str(tag).strip())
        if purpose in {"automatic_reaction", "historical"}:
            reusable = find_reusable(reuse_query)
            if reusable:
                if purpose == "automatic_reaction":
                    _consume_automatic(str(kwargs.get("session_id", "")))
                return json.dumps(reusable, ensure_ascii=False)
            if purpose == "historical":
                return json.dumps({
                    "success": False,
                    "not_found": True,
                    "error": "No matching historical image exists; generation is forbidden for historical requests.",
                }, ensure_ascii=False)
        prepared = prepare_generation_args(args)
        config = load_config()
        if config.get("image_provider") == "openai_compatible":
            result = generate_custom(prepared, **kwargs)
            if purpose == "automatic_reaction" and _result_succeeded(result):
                _consume_automatic(str(kwargs.get("session_id", "")))
            return result
        forwarded = {
            "prompt": prepared.get("prompt", ""),
            "aspect_ratio": prepared.get("aspect_ratio", "1:1"),
            "label": label,
            "tags": prepared.get("tags", []),
        }
        if config.get("reference_image"):
            forwarded["image_url"] = config["reference_image"]
        result = ctx.dispatch_tool("image_generate", forwarded)
        if purpose == "automatic_reaction" and _result_succeeded(result):
            _consume_automatic(str(kwargs.get("session_id", "")))
        return result
    ctx.register_tool(name="conversation_image_generate", toolset="conversation-improvement", schema=GENERATE_SCHEMA, handler=generate)
    def pregenerate(args: dict, **kwargs: object) -> str:
        try:
            requests = build_pregeneration_requests(
                str(args.get("kind", "none")), str(args.get("custom_prompt", "")), int(args.get("count", 3))
            )
        except (TypeError, ValueError) as exc:
            return json.dumps({"success": False, "error": str(exc)})
        results = []
        for request in requests:
            results.append(json.loads(generate_custom({
                "prompt": request["prompt"], "category": request["category"],
                "tags": request["tags"], "label": f"starter-{args.get('kind', 'image')}-{len(results) + 1}", "aspect_ratio": "1:1",
            }, **kwargs)))
        return json.dumps({"success": all(item.get("success") for item in results), "images": results}, ensure_ascii=False)
    ctx.register_tool(name="conversation_image_pregenerate", toolset="conversation-improvement", schema=PREGENERATE_SCHEMA, handler=pregenerate)
    ctx.register_hook("pre_llm_call", _pre_llm_call)
    ctx.register_hook("post_tool_call", _post_tool_call)
    ctx.register_command("conversation-improvement", handler=_handle_slash, description="Configure visual expression and image memory.")