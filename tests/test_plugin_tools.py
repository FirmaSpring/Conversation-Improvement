import importlib.util
import json
import sys
from pathlib import Path


def load_plugin_package():
    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location(
        "conversation_improvement_plugin",
        root / "__init__.py",
        submodule_search_locations=[str(root)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_configure_preset_indexes_media(monkeypatch, tmp_path: Path):
    plugin = load_plugin_package()
    configure = plugin.configure
    load_config = plugin.load_config
    search = plugin.search
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    presets = tmp_path / "presets" / "happy"
    presets.mkdir(parents=True)
    (presets / "wave_hello.gif").write_bytes(b"gif")

    result = json.loads(configure({
        "enabled": True,
        "mode": "preset",
        "preset_directory": str(presets.parent),
        "auto_expression": True,
        "image_provider": "openai_compatible",
        "base_url": "https://images.example/v1",
        "image_model": "image-model",
        "api_key_env": "TEST_IMAGE_KEY",
    }))

    assert result["success"] is True
    assert load_config()["mode"] == "preset"
    images = json.loads(search({"query": "happy wave"}))["images"]
    assert len(images) == 1
    assert images[0]["source"] == "preset"


def test_first_setup_context_requests_native_choice_ui(monkeypatch, tmp_path: Path):
    plugin = load_plugin_package()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    context = plugin._pre_llm_call(
        session_id="fresh", user_message="hello", is_first_turn=True
    )["context"]
    assert "clarify tool" in context
    assert "exactly two choices" in context


def test_explicit_generation_does_not_consume_automatic_quota(monkeypatch, tmp_path: Path):
    plugin = load_plugin_package()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    plugin.configure({
        "enabled": True, "mode": "per_request", "image_provider": "openai_compatible",
        "base_url": "https://images.example/v1", "image_model": "image-model",
        "api_key_env": "TEST_IMAGE_KEY",
    })
    plugin._pre_llm_call(
        session_id="explicit", user_message="show me a selfie", is_first_turn=False
    )
    image = tmp_path / "selfie.png"
    image.write_bytes(b"image")
    plugin._post_tool_call(
        tool_name="image_generate",
        args={"prompt": "selfie"},
        result=json.dumps({"success": True, "image": str(image)}),
        session_id="explicit",
    )
    assert plugin._session_state["explicit"].automatic_count == 0


def test_config_stores_only_api_key_environment_name(monkeypatch, tmp_path: Path):
    plugin = load_plugin_package()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    result = json.loads(plugin.configure({
        "enabled": True,
        "mode": "reference",
        "image_provider": "openai_compatible",
        "base_url": "https://images.example/v1",
        "image_model": "image-model",
        "api_key_env": "MY_IMAGE_API_KEY",
    }))
    assert result["success"] is True
    saved = plugin.load_config()
    assert saved["api_key_env"] == "MY_IMAGE_API_KEY"
    assert "api_key" not in saved


def test_config_can_reference_hermes_credential_pool(monkeypatch, tmp_path: Path):
    plugin = load_plugin_package()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    result = json.loads(plugin.configure({
        "enabled": True,
        "image_provider": "openai_compatible",
        "base_url": "https://images.example/v1",
        "image_model": "image-model",
        "credential_provider": "custom:pokeapi",
    }))
    assert result["success"] is True
    assert plugin.load_config()["credential_provider"] == "custom:pokeapi"


def test_config_can_clear_credential_pool_reference(monkeypatch, tmp_path: Path):
    plugin = load_plugin_package()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    common = {
        "enabled": True,
        "image_provider": "openai_compatible",
        "base_url": "https://images.example/v1",
        "image_model": "image-model",
    }
    plugin.configure({**common, "credential_provider": "custom:pokeapi"})
    plugin.configure({**common, "credential_provider": ""})
    assert plugin.load_config()["credential_provider"] == ""


def test_archive_does_not_store_prompt_by_default(monkeypatch, tmp_path: Path):
    plugin = load_plugin_package()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    image = tmp_path / "private.png"
    image.write_bytes(b"image")
    plugin.configure({
        "enabled": True, "mode": "per_request", "image_provider": "openai_compatible",
        "base_url": "https://images.example/v1", "image_model": "image-model",
        "api_key_env": "TEST_IMAGE_KEY",
    })
    plugin.archive({"path": str(image), "prompt": "private conversation text", "tags": ["selfie"]})
    found = json.loads(plugin.search({"query": "selfie"}))["images"][0]
    assert found["prompt"] == ""


def test_extracts_openai_compatible_image_response():
    plugin = load_plugin_package()
    payload = {"choices": [{"message": {"content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,aW1hZ2U="}}
    ]}}]}
    assert plugin.generate_custom.__globals__["_extract_image"](payload).startswith("data:image/png")


def test_images_protocol_uses_standard_generation_endpoint(monkeypatch, tmp_path: Path):
    plugin = load_plugin_package()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    monkeypatch.setenv("TEST_IMAGE_KEY", "secret")
    plugin.configure({
        "enabled": True,
        "image_provider": "openai_compatible",
        "base_url": "https://images.example/v1",
        "image_model": "image-model",
        "api_protocol": "images",
        "api_key_env": "TEST_IMAGE_KEY",
        "credential_provider": "",
    })
    seen = {}
    def fake_post(endpoint, api_key, payload, timeout=180):
        seen.update(endpoint=endpoint, api_key=api_key, payload=payload)
        return {"data": [{"b64_json": "aW1hZ2U="}]}
    monkeypatch.setitem(plugin.generate_custom.__globals__, "_post_json", fake_post)
    result = json.loads(plugin.generate_custom({"prompt": "flower", "aspect_ratio": "1:1"}))
    assert result["success"] is True
    assert seen["endpoint"] == "https://images.example/v1/images/generations"
    assert seen["payload"]["size"] == "1024x1024"


def test_enabled_setup_requires_base_url_model_and_api_source(monkeypatch, tmp_path: Path):
    plugin = load_plugin_package()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    result = json.loads(plugin.configure({"enabled": True, "mode": "reference"}))
    assert result["success"] is False
    assert {"base_url", "image_model", "api_key_env"}.issubset(result["missing"])
    assert plugin.load_config()["configured"] is False


def test_single_subject_guard_is_added_to_every_prompt():
    plugin = load_plugin_package()
    guard = plugin.generate_custom.__globals__["_guard_prompt"]
    portrait = guard("a cheerful selfie", "portrait")
    landscape = guard("spring mountains", "landscape")
    assert "exactly one person" in portrait
    assert "no second person" in portrait
    assert "no people" in landscape


def test_pregeneration_choices_build_guarded_requests():
    plugin = load_plugin_package()
    build = plugin.generate_custom.__globals__["build_pregeneration_requests"]
    memes = build("memes", "", 2)
    custom = build("custom", "wearing a raincoat", 1)
    assert len(memes) == 2
    assert memes[0]["category"] == "portrait"
    assert "chibi" in memes[0]["prompt"].lower()
    assert "exactly one person" in memes[0]["prompt"]
    assert "wearing a raincoat" in custom[0]["prompt"]


def test_reference_description_is_injected_for_people_only(monkeypatch, tmp_path: Path):
    plugin = load_plugin_package()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    monkeypatch.setenv("TEST_IMAGE_KEY", "secret")
    plugin.configure({
        "enabled": True, "mode": "reference", "image_provider": "openai_compatible",
        "base_url": "https://images.example/v1", "image_model": "image-model",
        "api_key_env": "TEST_IMAGE_KEY", "reference_description": "silver-haired character",
    })
    seen = []
    def fake_post(endpoint, api_key, payload, timeout=180):
        seen.append(payload["prompt"])
        return {"data": [{"b64_json": "aW1hZ2U="}]}
    monkeypatch.setitem(plugin.generate_custom.__globals__, "_post_json", fake_post)
    plugin.generate_custom({"prompt": "happy sticker", "category": "portrait"})
    plugin.generate_custom({"prompt": "spring hills", "category": "landscape"})
    assert "silver-haired character" in seen[0]
    assert "silver-haired character" not in seen[1]


def test_automatic_reaction_prompt_has_restrained_sticker_style():
    plugin = load_plugin_package()
    prepare = plugin.prepare_generation_args
    result = prepare({
        "purpose": "automatic_reaction",
        "prompt": "happy surprise",
        "aspect_ratio": "16:9",
        "tags": ["happy"],
    })
    prompt = result["prompt"].casefold()
    assert "chibi" in prompt
    assert "blank background" in prompt
    assert "not stiff" in prompt
    assert "no scenery" in prompt
    assert result["aspect_ratio"] == "1:1"
    assert {"reaction", "meme", "chibi", "happy"}.issubset(result["tags"])


def test_affectionate_action_templates_add_safe_single_person_pose():
    plugin = load_plugin_package()
    prepare = plugin.prepare_generation_args
    hug = prepare({"purpose": "automatic_reaction", "prompt": "给姐姐抱抱", "tags": ["抱抱"]})
    kiss = prepare({"purpose": "automatic_reaction", "prompt": "亲亲姐姐", "tags": ["亲亲"]})
    warm = prepare({"purpose": "automatic_reaction", "prompt": "姐姐哈气", "tags": ["哈气"]})
    assert "open arms" in hug["prompt"]
    assert "blown kiss" in kiss["prompt"]
    assert "no second person" in kiss["prompt"]
    assert "cupped hands" in warm["prompt"]


def test_find_reusable_returns_existing_tagged_reaction(monkeypatch, tmp_path: Path):
    plugin = load_plugin_package()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    image = tmp_path / "happy.png"
    image.write_bytes(b"image")
    plugin.archive({"path": str(image), "tags": ["reaction", "happy"]})
    result = plugin.find_reusable("reaction happy")
    assert result["success"] is True
    assert result["reused"] is True
    assert Path(result["image"]).is_file()


def test_historical_request_never_generates(monkeypatch, tmp_path: Path):
    plugin = load_plugin_package()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))

    class Context:
        def __init__(self):
            self.tools = {}
        def register_tool(self, name, handler, **_):
            self.tools[name] = handler
        def register_hook(self, *_args, **_kwargs):
            pass
        def register_command(self, *_args, **_kwargs):
            pass
        def dispatch_tool(self, *_args, **_kwargs):
            raise AssertionError("historical request must not dispatch generation")

    ctx = Context()
    plugin.register(ctx)
    result = json.loads(ctx.tools["conversation_image_generate"]({
        "purpose": "historical",
        "prompt": "show an old selfie",
        "reuse_query": "selfie old",
    }))
    assert result["success"] is False
    assert result["not_found"] is True


def test_existing_images_are_allowed_when_new_automatic_generation_is_blocked(monkeypatch, tmp_path: Path):
    plugin = load_plugin_package()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    plugin.configure({
        "enabled": True, "mode": "reference", "image_provider": "openai_compatible",
        "base_url": "https://images.example/v1", "image_model": "image-model", "api_key_env": "TEST_IMAGE_KEY",
    })
    context = plugin._pre_llm_call(session_id="serious", user_message="我今天学习很难受", is_first_turn=False)["context"]
    assert "Existing library images may be sent at any time" in context
    assert "New automatic generation is not allowed" in context


def test_old_policy_config_is_migrated(monkeypatch, tmp_path: Path):
    plugin = load_plugin_package()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    path = tmp_path / "hermes" / "conversation-improvement" / "config.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "configured": True,
        "enabled": True,
        "probability": 0.08,
        "cooldown_turns": 8,
        "max_per_session": 2,
    }), encoding="utf-8")
    config = plugin.load_config()
    assert config["policy_version"] == 2
    assert config["probability"] == 0.32
    assert config["playful_probability"] == 0.65
    assert config["force_after_casual_turns"] == 4
    assert config["cooldown_turns"] == 5
    assert config["max_per_session"] == 20