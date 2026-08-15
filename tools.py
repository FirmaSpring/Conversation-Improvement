from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path

from .conversation_improvement.library import ImageLibrary


MEDIA_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

REACTION_STYLE = (
    "cute chibi reaction sticker, expressive natural facial expression, lively eyes and pose, "
    "emotion clearly readable, not stiff, not expressionless, isolated character, "
    "plain white or transparent-looking blank background, no scenery, no detailed environment"
)
ACTION_TEMPLATES = (
    ("抱抱", "open arms wide for a warm hug, both cute hands fully visible, gentle welcoming smile"),
    ("拥抱", "open arms wide for a warm hug, both cute hands fully visible, gentle welcoming smile"),
    ("抱一下", "open arms wide for a warm hug, both cute hands fully visible, gentle welcoming smile"),
    ("亲亲", "sending a cute blown kiss with one hand near the lips, warm affectionate smile, no second person"),
    ("亲一口", "sending a cute blown kiss with one hand near the lips, warm affectionate smile, no second person"),
    ("飞吻", "sending a cute blown kiss with one hand near the lips, warm affectionate smile, no second person"),
    ("贴贴", "leaning forward slightly with both hands held near the heart, sweet friendly closeness, no second person"),
    ("蹭蹭", "tilting the head playfully with both hands held near the cheeks, sweet friendly closeness, no second person"),
    ("哈气", "cupped hands near the mouth, gently breathing warm air into them, visible soft breath, caring expression"),
    ("呵气", "cupped hands near the mouth, gently breathing warm air into them, visible soft breath, caring expression"),
    ("暖暖", "cupped hands near the mouth, gently breathing warm air into them, visible soft breath, caring expression"),
    ("摸摸头", "one cute hand raised in a gentle head-patting gesture, other hand clearly visible, warm reassuring smile"),
    ("摸头", "one cute hand raised in a gentle head-patting gesture, other hand clearly visible, warm reassuring smile"),
    ("牵手", "one cute hand reaching forward as an invitation to hold hands, other hand clearly visible, no second person"),
    ("拉手", "one cute hand reaching forward as an invitation to hold hands, other hand clearly visible, no second person"),
)


def data_root() -> Path:
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    root = home / "conversation-improvement"
    root.mkdir(parents=True, exist_ok=True)
    return root


def config_path() -> Path:
    return data_root() / "config.json"


def load_config() -> dict:
    defaults = {
        "policy_version": 2,
        "configured": False,
        "enabled": False,
        "mode": "reference",
        "reference_description": "",
        "auto_expression": True,
        "probability": 0.32,
        "playful_probability": 0.65,
        "force_after_casual_turns": 4,
        "cooldown_turns": 5,
        "max_per_session": 20,
        "image_provider": "hermes",
        "base_url": "",
        "image_model": "",
        "api_protocol": "auto",
        "api_key_env": "CONVERSATION_IMPROVEMENT_API_KEY",
        "credential_provider": "",
        "store_prompts": False,
    }
    try:
        loaded = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    if not isinstance(loaded, dict):
        return defaults
    if int(loaded.get("policy_version", 1)) < 2:
        loaded.update({
            "policy_version": 2,
            "probability": 0.32,
            "playful_probability": 0.65,
            "force_after_casual_turns": 4,
            "cooldown_turns": 5,
            "max_per_session": 20,
        })
        save_config({**defaults, **loaded})
    return {**defaults, **loaded}


def save_config(config: dict) -> None:
    path = config_path()
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def configure(args: dict, **_: object) -> str:
    previous = load_config()
    config = dict(previous)
    enabled = bool(args.get("enabled"))
    config["enabled"] = enabled
    if args.get("mode") in {"reference", "preset", "per_request"}:
        config["mode"] = args["mode"]
    if "auto_expression" in args:
        config["auto_expression"] = bool(args["auto_expression"])
    if "reference_description" in args:
        config["reference_description"] = str(args.get("reference_description", "")).strip()
    if "store_prompts" in args:
        config["store_prompts"] = bool(args["store_prompts"])
    if args.get("image_provider") in {"hermes", "openai_compatible"}:
        config["image_provider"] = args["image_provider"]
    if args.get("api_protocol") in {"auto", "images", "chat_completions"}:
        config["api_protocol"] = args["api_protocol"]
    for key in ("base_url", "image_model", "api_key_env"):
        value = str(args.get(key, "")).strip()
        if value:
            config[key] = value
    if "credential_provider" in args:
        config["credential_provider"] = str(args.get("credential_provider", "")).strip()
    if enabled:
        missing = [key for key in ("base_url", "image_model") if not config.get(key)]
        has_api_source = bool(str(args.get("api_key_env", "")).strip() or str(args.get("credential_provider", "")).strip())
        if previous.get("configured"):
            has_api_source = has_api_source or bool(config.get("api_key_env") or config.get("credential_provider"))
        if not has_api_source:
            missing.append("api_key_env")
        if missing:
            return json.dumps({
                "success": False,
                "error": "Enabled setup requires base_url, API key source, and image_model.",
                "missing": missing,
            })
    if config["image_provider"] == "openai_compatible":
        env_name = config.get("api_key_env", "CONVERSATION_IMPROVEMENT_API_KEY")
        if not env_name.replace("_", "").isalnum():
            return json.dumps({"success": False, "error": "api_key_env must be an environment variable name."})
    for key in ("reference_image", "preset_directory"):
        value = str(args.get(key, "")).strip()
        if value:
            candidate = Path(value).expanduser().resolve()
            if key == "reference_image" and not candidate.is_file():
                return json.dumps({"success": False, "error": f"Reference image not found: {candidate}"}, ensure_ascii=False)
            if key == "preset_directory" and not candidate.is_dir():
                return json.dumps({"success": False, "error": f"Preset directory not found: {candidate}"}, ensure_ascii=False)
            config[key] = str(candidate)
            if key == "reference_image":
                ImageLibrary(data_root() / "library").archive(
                    candidate, tags=["reference", "character"], label="角色参考图", source="reference"
                )
            elif key == "preset_directory":
                library = ImageLibrary(data_root() / "library")
                for media in sorted(candidate.rglob("*")):
                    if media.is_file() and media.suffix.casefold() in MEDIA_SUFFIXES:
                        relative_parts = media.relative_to(candidate).parts[:-1]
                        stem_tags = [part for part in media.stem.replace("_", " ").replace("-", " ").split() if part]
                        library.archive(
                            media,
                            tags=["preset", *relative_parts, *stem_tags],
                            label=media.stem,
                            source="preset",
                        )
    config["configured"] = True
    save_config(config)
    return json.dumps({"success": True, "config": config}, ensure_ascii=False)


def archive(args: dict, **_: object) -> str:
    try:
        item = ImageLibrary(data_root() / "library").archive(
            Path(str(args.get("path", ""))),
            prompt=str(args.get("prompt", "")) if load_config().get("store_prompts") else "",
            tags=args.get("tags") or [],
            label=str(args.get("label", "")),
            event_date=str(args.get("event_date", "")),
            source=str(args.get("source", "generated")),
        )
    except (OSError, ValueError) as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)
    return json.dumps({
        "success": True, "id": item.id, "path": str(item.path),
        "created_at": item.created_at, "event_date": item.event_date,
        "label": item.label, "tags": list(item.tags),
    }, ensure_ascii=False)


def search(args: dict, **_: object) -> str:
    items = ImageLibrary(data_root() / "library").search(
        query=str(args.get("query", "")),
        date_from=str(args.get("date_from", "")),
        date_to=str(args.get("date_to", "")),
        limit=int(args.get("limit", 5)),
    )
    return json.dumps({"success": True, "images": [
        {"id": item.id, "path": str(item.path), "created_at": item.created_at,
         "event_date": item.event_date, "label": item.label, "prompt": item.prompt,
         "tags": list(item.tags), "source": item.source}
        for item in items
    ]}, ensure_ascii=False)


def find_reusable(query: str) -> dict | None:
    items = ImageLibrary(data_root() / "library").search(query=query, limit=1)
    if not items:
        return None
    item = items[0]
    if not item.path.is_file():
        return None
    return {
        "success": True,
        "image": str(item.path),
        "created_at": item.created_at,
        "event_date": item.event_date,
        "label": item.label,
        "tags": list(item.tags),
        "reused": True,
    }


def prepare_generation_args(args: dict) -> dict:
    prepared = dict(args)
    purpose = str(prepared.get("purpose", "explicit_new"))
    tags = [str(tag).strip() for tag in prepared.get("tags") or [] if str(tag).strip()]
    if purpose == "automatic_reaction":
        action = next((template for term, template in ACTION_TEMPLATES if term in str(prepared.get("prompt", ""))), "")
        prepared["prompt"] = f"{REACTION_STYLE}. {action}. Emotion and situation: {prepared.get('prompt', '')}"
        prepared["category"] = "portrait"
        prepared["aspect_ratio"] = "1:1"
        prepared["tags"] = sorted(set(["reaction", "meme", "chibi", *tags]))
    return prepared


def _reference_part(path_value: str) -> dict | None:
    path = Path(path_value) if path_value else None
    if path is None or not path.is_file():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}


def _extract_image(payload: dict) -> str:
    choices = payload.get("choices") or []
    message = choices[0].get("message", {}) if choices else {}
    content = message.get("content", "")
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            image = part.get("image_url") or part.get("url")
            if isinstance(image, dict):
                image = image.get("url")
            if isinstance(image, str) and image:
                return image
    if isinstance(content, str) and content.strip().startswith(("http://", "https://", "data:image/")):
        return content.strip()
    images = message.get("images") or payload.get("images") or payload.get("data") or []
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return str(first.get("url") or first.get("b64_json") or "")
    return ""


def _save_returned_image(value: str) -> Path:
    media = data_root() / "generated"
    media.mkdir(parents=True, exist_ok=True)
    destination = media / f"response_{os.urandom(8).hex()}.png"
    if value.startswith("data:image/"):
        destination.write_bytes(base64.b64decode(value.split(",", 1)[1]))
    elif value.startswith(("http://", "https://")):
        with urllib.request.urlopen(value, timeout=60) as response:
            destination.write_bytes(response.read())
    else:
        destination.write_bytes(base64.b64decode(value))
    return destination


def _image_size(aspect_ratio: str) -> str:
    return {
        "1:1": "1024x1024",
        "16:9": "1536x864",
        "9:16": "864x1536",
        "4:3": "1024x768",
        "3:4": "768x1024",
    }.get(aspect_ratio, "1024x1024")


def _guard_prompt(prompt: str, category: str = "portrait") -> str:
    clean = str(prompt).strip()
    if "exactly one person" in clean.casefold() or "no people" in clean.casefold():
        return clean
    if category == "landscape":
        return f"{clean}. no people, no human figures, no characters, landscape only."
    return (
        f"{clean}. exactly one person in the entire image, a single character only, "
        "no second person, no crowd, no duplicate body, no reflected extra person."
    )


def build_pregeneration_requests(kind: str, custom_prompt: str = "", count: int = 3) -> list[dict]:
    amount = max(1, min(int(count), 6))
    if kind == "none":
        return []
    if kind == "memes":
        prompts = [
            "Cute chibi reaction sticker, surprised wide-eyed expression, optional short text: Eh?!",
            "Cute chibi reaction sticker, joyful bright smile, optional short text: Yay!",
            "Cute chibi reaction sticker, shy embarrassed expression, optional short text: Stop teasing me",
            "Cute chibi reaction sticker, thoughtful expression, optional short text: Let me think",
            "Cute chibi reaction sticker, proud celebratory expression, optional short text: I did it!",
            "Cute chibi reaction sticker, sleepy drowsy expression, optional short text: So sleepy",
        ]
        category = "portrait"
    elif kind == "landscapes":
        prompts = [
            "A peaceful spring landscape with cherry blossoms",
            "A moonlit lakeside landscape",
            "A quiet mountain sunrise landscape",
            "A rainy city window landscape",
            "A starry coastal landscape",
            "A soft snowy forest landscape",
        ]
        category = "landscape"
    elif kind == "custom" and custom_prompt.strip():
        prompts = [custom_prompt.strip()] * amount
        category = "portrait"
    else:
        raise ValueError("Custom pregeneration requires custom_prompt.")
    return [
        {"prompt": _guard_prompt(prompts[index], category), "category": category, "tags": ["starter", kind]}
        for index in range(amount)
    ]


def _post_json(endpoint: str, api_key: str, payload: dict, timeout: int = 180) -> dict:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def generate_custom(args: dict, **_: object) -> str:
    config = load_config()
    env_name = config.get("api_key_env", "CONVERSATION_IMPROVEMENT_API_KEY")
    api_key = os.environ.get(env_name, "")
    credential_provider = str(config.get("credential_provider", "")).strip()
    if not api_key and credential_provider:
        try:
            from agent.credential_pool import load_pool
            credential = load_pool(credential_provider).select()
            api_key = credential.runtime_api_key if credential else ""
        except (ImportError, AttributeError, OSError):
            api_key = ""
    if not api_key:
        source = f"Hermes credential provider {credential_provider}" if credential_provider else f"environment variable {env_name}"
        return json.dumps({"success": False, "error": f"Missing API key from {source}"})
    category = str(args.get("category", "portrait"))
    raw_prompt = str(args.get("prompt", ""))
    # The public conversation tool requires a label. Keep this lower-level helper
    # compatible with Hermes hooks and direct integrations that predate labels.
    label = str(args.get("label", "")).strip() or "自动生成"
    reference_description = str(config.get("reference_description", "")).strip()
    if category != "landscape" and reference_description:
        raw_prompt = f"{reference_description}. {raw_prompt}"
    guarded_prompt = _guard_prompt(raw_prompt, category)
    base = config["base_url"].rstrip("/")
    protocol = config.get("api_protocol", "auto")
    try:
        if protocol in {"auto", "images"}:
            endpoint = base if base.endswith("/images/generations") else base + "/images/generations"
            payload = _post_json(endpoint, api_key, {
                "model": config["image_model"],
                "prompt": guarded_prompt,
                "size": _image_size(str(args.get("aspect_ratio", "1:1"))),
                "response_format": "b64_json",
            })
        else:
            content: list[dict] = [{"type": "text", "text": guarded_prompt}]
            reference = _reference_part(config.get("reference_image", ""))
            if reference:
                content.append(reference)
            endpoint = base if base.endswith("/chat/completions") else base + "/chat/completions"
            payload = _post_json(endpoint, api_key, {
                "model": config["image_model"],
                "messages": [{"role": "user", "content": content}],
                "modalities": ["text", "image"],
            })
        image_value = _extract_image(payload)
        if not image_value:
            raise ValueError("The endpoint returned no recognizable image.")
        path = _save_returned_image(image_value)
        archived = json.loads(archive({
            "path": str(path), "prompt": guarded_prompt,
            "tags": args.get("tags") or [], "label": label,
            "event_date": str(args.get("event_date", "")), "source": "generated",
        }))
        return json.dumps({
            "success": True, "image": archived["path"],
            "created_at": archived["created_at"],
        }, ensure_ascii=False)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError) as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)