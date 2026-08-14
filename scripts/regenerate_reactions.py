from __future__ import annotations

import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).parents[1]
AGENT_ROOT = Path(r"C:\Users\ChainBox\AppData\Local\hermes\hermes-agent")
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

spec = importlib.util.spec_from_file_location(
    "conversation_improvement_regenerator",
    ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)

BASE = (
    "A single cute chibi silver-haired cat-eared girl with teal and lavender heterochromia, "
    "pink cherry blossom hairpin, gray-purple hoodie with teal accents. Exactly one character, "
    "both cute small hands clearly visible and anatomically coherent, expressive hand gesture and body action, "
    "lively natural eyes and mouth, emotion unmistakable, not stiff, not expressionless. "
    "Sticker illustration, isolated character, plain white or transparent-looking blank background, "
    "no scenery, no room, no furniture, no detailed environment, no extra person, no text, no speech bubble. "
)

ITEMS = [
    ("morning_wave", "早安", "morning", "brightly waving one hand high while the other hand holds a tiny steaming mug, energetic fresh smile"),
    ("morning_stretch", "早安", "morning", "stretching both cute hands above her head, sleepy-to-cheerful face, ears perked up"),
    ("goodnight_blanket", "晚安", "goodnight", "holding a soft blanket to her cheek with both hands, gentle sleepy smile, half-closed eyes"),
    ("goodnight_wave", "晚安", "goodnight", "small goodnight wave with one hand while the other hugs a moon-shaped pillow, tender drowsy expression"),
    ("sleep_droop", "睡觉", "sleepy", "nodding off while seated, hands loosely hugging a pillow, eyes closed, tiny relaxed sleepy mouth"),
    ("sleep_rubeyes", "睡觉", "sleepy", "rubbing one eye with a tiny fist while the other hand reaches for a blanket, adorably exhausted face"),
    ("lazy_sprawl", "犯懒", "lazy", "flopped forward lazily with both hands stretched toward the viewer, pouty unwilling-to-move expression"),
    ("lazy_nope", "犯懒", "lazy", "crossing both small arms in a soft refusal, puffed cheeks, droopy ears, comically lazy face"),
    ("happy_cheer", "开心", "happy", "raising both fists in a cheerful celebration, sparkling crescent eyes, open joyful smile"),
    ("shy_fingers", "害羞", "shy", "touching the tips of both index fingers together near her chest, blushing cheeks, bashful side glance"),
    ("surprised_hands", "惊喜", "surprised", "both hands lifted beside her cheeks, wide sparkling eyes, delighted open-mouth surprise"),
    ("mischievous_peek", "调皮", "mischievous", "making a playful V sign beside one eye with one hand and hiding a giggle with the other, cheeky wink"),
]


def generate(item: tuple[str, str, str, str]) -> dict:
    slug, zh, emotion, action = item
    prompt = BASE + action
    result = json.loads(plugin.generate_custom({
        "prompt": prompt,
        "aspect_ratio": "1:1",
        "category": "portrait",
        "tags": ["reaction", "meme", "chibi", emotion, zh, slug],
    }))
    return {"slug": slug, "emotion": emotion, "zh": zh, **result}


def main() -> int:
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(generate, item): item[0] for item in ITEMS}
        for future in as_completed(futures):
            slug = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"slug": slug, "success": False, "error": f"{type(exc).__name__}: {exc}"}
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    failed = [row for row in results if not row.get("success")]
    summary = {"requested": len(ITEMS), "succeeded": len(results) - len(failed), "failed": len(failed)}
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
