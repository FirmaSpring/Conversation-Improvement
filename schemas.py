CONFIGURE_SCHEMA = {
    "name": "conversation_image_configure",
    "description": "Configure ConversationImprovement after the user explicitly chooses a setup option.",
    "parameters": {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean"},
            "mode": {"type": "string", "enum": ["reference", "preset", "per_request"]},
            "reference_image": {"type": "string", "description": "Optional local path to the permanent character reference image."},
            "reference_description": {"type": "string", "description": "Optional reusable visual description for providers that cannot accept a reference image."},
            "preset_directory": {"type": "string", "description": "Optional local directory containing reusable images or GIFs."},
            "auto_expression": {"type": "boolean", "default": True},
            "image_provider": {"type": "string", "enum": ["hermes", "openai_compatible"]},
            "base_url": {"type": "string", "description": "OpenAI-compatible API base URL. Never include an API key."},
            "image_model": {"type": "string", "description": "Image-capable model name for the custom endpoint."},
            "api_protocol": {"type": "string", "enum": ["auto", "images", "chat_completions"], "description": "Image API protocol. Auto prefers the standard Images API."},
            "api_key_env": {"type": "string", "description": "Environment variable containing the API key. Never pass the key itself."},
            "credential_provider": {"type": "string", "description": "Optional Hermes credential pool provider id, for example custom:pokeapi."},
            "store_prompts": {"type": "boolean", "default": False},
        },
        "required": ["enabled"],
        "allOf": [{
            "if": {"properties": {"enabled": {"const": True}}},
            "then": {"required": ["base_url", "image_model", "api_key_env"]},
        }],
    },
}

GENERATE_SCHEMA = {
    "name": "conversation_image_generate",
    "description": (
        "Generate an image through the provider selected in ConversationImprovement. "
        "Use after an explicit request or when the restrained automatic-expression policy allows it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "aspect_ratio": {"type": "string", "default": "1:1"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "label": {"type": "string", "description": "Required concise human-readable label, for example 拥抱-开心. It becomes searchable metadata and part of the archived filename."},
            "purpose": {
                "type": "string",
                "enum": ["automatic_reaction", "explicit_new", "historical"],
                "description": "automatic_reaction reuses matching library media before generation; historical never generates; explicit_new creates a new image.",
            },
            "reuse_query": {"type": "string", "description": "Short space-separated emotion tags used to find reusable media."},
        },
        "required": ["prompt", "purpose", "label"],
    },
}

PREGENERATE_SCHEMA = {
    "name": "conversation_image_pregenerate",
    "description": "Generate an optional starter pack after setup. Every character image is restricted to exactly one person.",
    "parameters": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["none", "memes", "landscapes", "custom"]},
            "custom_prompt": {"type": "string"},
            "count": {"type": "integer", "minimum": 1, "maximum": 6, "default": 3},
        },
        "required": ["kind"],
    },
}

ARCHIVE_SCHEMA = {
    "name": "conversation_image_archive",
    "description": (
        "Permanently archive an image or GIF in the conversation library with date, prompt, and tags. "
        "Call after image_generate succeeds, or when the user asks to remember an existing image."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute local media path."},
            "prompt": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "label": {"type": "string", "description": "Human-readable expression or image name; stored in metadata and the filename."},
            "event_date": {"type": "string", "description": "Relevant image date in YYYY-MM-DD, used for historical retrieval."},
            "source": {"type": "string", "enum": ["generated", "preset", "reference", "imported"]},
        },
        "required": ["path"],
    },
}

SEARCH_SCHEMA = {
    "name": "conversation_image_search",
    "description": (
        "Search permanent conversation images by semantic tags, prompt text, and date. "
        "Use when the user asks to see an older, previous, or dated image. Returns local paths suitable for MEDIA delivery."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "date_from": {"type": "string", "description": "Inclusive YYYY-MM-DD."},
            "date_to": {"type": "string", "description": "Inclusive YYYY-MM-DD."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
        },
    },
}