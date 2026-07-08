"""Character pipeline, Stage C: photo -> CharacterProfile.

A local vision model (Ollama, e.g. qwen2.5vl) reads a portrait and returns the
high-level physical traits that define a recognizable character — hair colour and
style, build, glasses, skin tone. We write those as a Godot `CharacterProfile`
resource (`.tres`), the same text contract a hand-authored profile uses, so Stage A
(the parametric figure) renders it unchanged.

Faces never leave the machine: the model runs locally via Ollama's HTTP API.

The model is asked for CATEGORICAL traits (named colours, a build category) rather
than raw numbers — small vision models pick reliably from a list but are poor at
inventing precise RGB/floats. We map those names to Colors/floats here, so the Godot
contract stays numeric while the model does what it's good at.

The network call is isolated in `call_ollama`; everything else (schema, mapping,
.tres rendering) is pure and unit-testable without a running model.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

# Must match the enum in godot/scripts/character_profile.gd.
HAIRSTYLES = ("bald", "short", "medium", "long", "ponytail", "afro")

HEIGHT_RANGE = (1.4, 2.1)
STANDARD_HEIGHT_M = 1.75  # 5'9" — the default when no scale reference is given

DEFAULT_MODEL = "qwen2.5vl:3b"
DEFAULT_HOST = "http://localhost:11434"

# Where character reference photos are dropped (the character "drop zone").
REFERENCE_DIR = "input/CharacterReferences"
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")

# Where photo-generated profiles are written (kept apart from curated sample profiles).
PROFILE_OUT_DIR = "godot/profiles/generated"

Rgb = tuple[float, float, float]

# --- categorical -> concrete maps (the model picks a name; we choose the value) ---
BUILDS: dict[str, float] = {
    "slim": 0.85, "average": 1.0, "athletic": 1.05, "broad": 1.2, "heavy": 1.3,
}
HAIR_COLORS: dict[str, Rgb] = {
    "black": (0.05, 0.04, 0.04),
    "dark_brown": (0.18, 0.12, 0.08),
    "brown": (0.33, 0.22, 0.13),
    "light_brown": (0.50, 0.36, 0.22),
    "blonde": (0.83, 0.69, 0.42),
    "red": (0.60, 0.24, 0.12),
    "auburn": (0.42, 0.19, 0.12),
    "gray": (0.62, 0.62, 0.64),
    "white": (0.90, 0.90, 0.90),
}
SKIN_TONES: dict[str, Rgb] = {
    "pale": (0.95, 0.84, 0.79),
    "fair": (0.92, 0.78, 0.68),
    "light": (0.86, 0.68, 0.55),
    "medium": (0.76, 0.57, 0.43),
    "olive": (0.70, 0.56, 0.40),
    "tan": (0.66, 0.48, 0.34),
    "brown": (0.48, 0.33, 0.22),
    "dark": (0.33, 0.22, 0.15),
}
BASIC_COLORS: dict[str, Rgb] = {
    "black": (0.05, 0.05, 0.06),
    "white": (0.90, 0.90, 0.90),
    "gray": (0.50, 0.50, 0.52),
    "red": (0.60, 0.12, 0.12),
    "orange": (0.85, 0.45, 0.15),
    "yellow": (0.85, 0.75, 0.20),
    "green": (0.20, 0.50, 0.25),
    "blue": (0.20, 0.35, 0.70),
    "navy": (0.12, 0.16, 0.32),
    "purple": (0.40, 0.20, 0.55),
    "pink": (0.85, 0.50, 0.60),
    "brown": (0.35, 0.24, 0.15),
    "beige": (0.80, 0.72, 0.58),
}


@dataclass
class CharacterAttributes:
    """The high-level traits — mirrors CharacterProfile in Godot (numeric form)."""
    height_m: float = STANDARD_HEIGHT_M
    build: float = 1.0
    skin_color: Rgb = (0.92, 0.78, 0.68)
    hair_color: Rgb = (0.18, 0.12, 0.08)
    shirt_color: Rgb = (0.50, 0.50, 0.52)
    pants_color: Rgb = (0.20, 0.22, 0.28)
    hairstyle: str = "short"
    glasses: bool = False
    facial_hair: bool = False
    descriptors: dict = field(default_factory=dict)  # the categorical picks, for logging
    notes: list[str] = field(default_factory=list)


# JSON schema handed to Ollama's `format`: everything categorical except height.
# Height is deliberately NOT asked of the model — a single photo has no reliable scale
# reference, so we use a standard height (or a manual --height) instead.
PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "build": {"type": "string", "enum": list(BUILDS)},
        "skin_tone": {"type": "string", "enum": list(SKIN_TONES)},
        "hair_color": {"type": "string", "enum": list(HAIR_COLORS)},
        "shirt_color": {"type": "string", "enum": list(BASIC_COLORS)},
        "pants_color": {"type": "string", "enum": list(BASIC_COLORS)},
        "hairstyle": {"type": "string", "enum": list(HAIRSTYLES)},
        "glasses": {"type": "boolean"},
        "facial_hair": {"type": "boolean"},
    },
    "required": [
        "build", "skin_tone", "hair_color",
        "shirt_color", "pants_color", "hairstyle", "glasses", "facial_hair",
    ],
}

_PROMPT = (
    "You are a character-design assistant. Look at the person in the photo and pick the "
    "closest option from each list for a stylized 3D character (not a likeness): overall "
    "build, skin tone, the dominant hair colour (ignore highlights), hairstyle, and the "
    "main colour of their top and lower garments. Report whether they wear glasses or have "
    "facial hair. Respond only with the requested JSON."
)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _named_color(value, palette: dict[str, Rgb], fallback: Rgb) -> tuple[Rgb, str]:
    """Resolve a colour from a category name; defensively accept a 0-1 or 0-255 RGB too."""
    if isinstance(value, str):
        key = value.strip().lower().replace(" ", "_")
        if key in palette:
            return palette[key], key
        return fallback, "?"
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            ch = [float(value[0]), float(value[1]), float(value[2])]
        except (TypeError, ValueError):
            return fallback, "?"
        if any(c > 1.0 for c in ch):  # model gave 0-255
            ch = [c / 255.0 for c in ch]
        rgb = (_clamp(ch[0], 0, 1), _clamp(ch[1], 0, 1), _clamp(ch[2], 0, 1))
        return rgb, "rgb"
    return fallback, "?"


def parse_attributes(raw: dict) -> CharacterAttributes:
    """Map a raw model response into safe CharacterAttributes.

    Tolerant by design: unknown categories fall back to averages so a sloppy response
    can never produce a broken profile.
    """
    a = CharacterAttributes()  # height_m defaults to STANDARD_HEIGHT_M
    if not isinstance(raw, dict):
        return a

    build_name = str(raw.get("build", "")).strip().lower()
    a.build = BUILDS.get(build_name, 1.0)

    a.hair_color, hair_name = _named_color(raw.get("hair_color"), HAIR_COLORS, a.hair_color)
    a.skin_color, skin_name = _named_color(raw.get("skin_tone"), SKIN_TONES, a.skin_color)
    a.shirt_color, shirt_name = _named_color(raw.get("shirt_color"), BASIC_COLORS, a.shirt_color)
    a.pants_color, pants_name = _named_color(raw.get("pants_color"), BASIC_COLORS, a.pants_color)

    style = str(raw.get("hairstyle", "")).strip().lower()
    a.hairstyle = style if style in HAIRSTYLES else "short"

    a.glasses = bool(raw.get("glasses", False))
    a.facial_hair = bool(raw.get("facial_hair", False))

    a.descriptors = {
        "build": build_name if build_name in BUILDS else "average",
        "skin_tone": skin_name, "hair_color": hair_name,
        "shirt_color": shirt_name, "pants_color": pants_name,
        "hairstyle": a.hairstyle,
    }
    return a


def _color_literal(c: Rgb) -> str:
    return f"Color({c[0]:.4g}, {c[1]:.4g}, {c[2]:.4g}, 1)"


def attributes_to_tres(attrs: CharacterAttributes) -> str:
    """Render a Godot CharacterProfile .tres (text) from attributes."""
    lines = [
        '[gd_resource type="Resource" script_class="CharacterProfile" load_steps=2 format=3]',
        "",
        '[ext_resource type="Script" path="res://scripts/character_profile.gd" id="1"]',
        "",
        "[resource]",
        'script = ExtResource("1")',
        f"height_m = {attrs.height_m:.4g}",
        f"build = {attrs.build:.4g}",
        f"skin_color = {_color_literal(attrs.skin_color)}",
        f"hair_color = {_color_literal(attrs.hair_color)}",
        f"shirt_color = {_color_literal(attrs.shirt_color)}",
        f"pants_color = {_color_literal(attrs.pants_color)}",
        f'hairstyle = "{attrs.hairstyle}"',
        f"glasses = {str(attrs.glasses).lower()}",
        f"facial_hair = {str(attrs.facial_hair).lower()}",
    ]
    return "\n".join(lines) + "\n"


def call_ollama(
    image: str | Path,
    *,
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    timeout: float = 120.0,
) -> dict:
    """Send the photo to a local Ollama vision model; return the parsed JSON dict.

    Raises ConnectionError with an actionable message if the server is unreachable.
    """
    image = Path(image)
    if not image.exists():
        raise FileNotFoundError(f"photo not found: {image}")

    b64 = base64.b64encode(image.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _PROMPT, "images": [b64]}],
        "format": PROFILE_SCHEMA,
        "stream": False,
        "options": {"temperature": 0},
    }
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Could not reach Ollama at {host}. Is it running ('ollama serve') and is "
            f"the model pulled ('ollama pull {model}')? Underlying error: {e}"
        ) from e

    content = body.get("message", {}).get("content", "")
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model did not return JSON. Got: {content[:200]!r}") from e


def newest_reference(ref_dir: str | Path = REFERENCE_DIR) -> Path | None:
    """Most recently modified image in the character reference folder, or None."""
    ref = Path(ref_dir)
    imgs = [p for p in ref.glob("*") if p.suffix.lower() in IMAGE_EXTS]
    return max(imgs, key=lambda p: p.stat().st_mtime) if imgs else None


def photo_to_profile(
    image: str | Path,
    out: str | Path,
    *,
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    height_override: float | None = None,
    write: bool = True,
    on_log=lambda _msg: None,
    _caller=call_ollama,
) -> CharacterAttributes:
    """Photo -> attributes, then (unless write=False) save a CharacterProfile .tres.

    Returns the attributes either way. With write=False this is a dry run: the model
    still runs, but nothing is written. `_caller` is the network step, injectable so
    tests run without a model.
    """
    image = Path(image)
    out = Path(out)
    on_log(f"reading traits from {image.name} via {model}")
    raw = _caller(image, model=model, host=host)
    attrs = parse_attributes(raw)

    if height_override is not None:
        attrs.height_m = _clamp(float(height_override), *HEIGHT_RANGE)
        attrs.notes.append("height set manually")
    else:
        attrs.height_m = STANDARD_HEIGHT_M
        attrs.notes.append("standard height (5'9\") — no scale reference")

    d = attrs.descriptors
    summary = (
        f"{attrs.height_m:.2f}m, build={d.get('build')}, skin={d.get('skin_tone')}, "
        f"hair={d.get('hair_color')}/{attrs.hairstyle}, shirt={d.get('shirt_color')}, "
        f"glasses={attrs.glasses}, facial_hair={attrs.facial_hair}"
    )
    if write:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(attributes_to_tres(attrs))
        on_log(f"wrote {out} — {summary}")
    else:
        on_log(f"dry run (not writing) — {summary}")
    return attrs
