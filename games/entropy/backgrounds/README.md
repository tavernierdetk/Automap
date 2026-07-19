# Game-owned backgrounds (entropy)

PNGs dropped here are published to `content/backgrounds/` by
`scripts/12_publish_game.py` (they add to / override the reference-pulled
set by filename). Battles reference them by name via a per-encounter
`backdrop` (see `engine/combat/battle_ui.gd`); the overworld can use them as
a `background`/`parallax` file too.

## Pending: `weirgate.png` — the incident's battle backdrop

The incident story-battle (Vec restrains Caden at the flood-lock) asks for
`backdrop: "weirgate"`; `battle_ui` falls back to the default until this
lands. Generating it hit the **image-API billing hard limit** — raise the
cap, then run the one-off:

```python
# .venv/bin/python - <<'PY'
import base64
from pathlib import Path
from automap import genlab
PROMPT = (
    "16-bit SNES JRPG battle backdrop, painterly pixel-art landscape, wide "
    "establishing shot. A massive ancient stone flood-lock gate — the "
    "Weirgate — with riveted timber-and-iron sluice doors, standing over a "
    "swollen river of dark churning water that spills over the lip in white "
    "spray. Distant lantern-lit rooftops of a market town at the water's "
    "edge under a low bruised storm sky. Cold blue-grey light with a sickly "
    "green cast on the water and torch-orange glints on the wet stone. "
    "Ominous, cinematic depth. No people, no text, no UI, no border — a "
    "clean scenic background painted for a turn-based battle."
)
cfg = genlab.imagegen_config()
out = genlab._post_json(
    "https://api.openai.com/v1/images/generations",
    {"model": cfg.get("model", "gpt-image-1"), "prompt": PROMPT,
     "n": 1, "size": "1536x1024", "quality": cfg.get("quality", "high")},
    {"Authorization": f"Bearer {cfg['api_key']}"})
Path("games/entropy/backgrounds/weirgate.png").write_bytes(
    base64.b64decode(out["data"][0]["b64_json"]))
PY
```

Then `scripts/12_publish_game.py --game entropy` — the battle upgrades
automatically, no code change.
