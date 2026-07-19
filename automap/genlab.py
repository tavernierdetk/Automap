"""GenLab: the image-model top of the Asset Creator.

An alternative generation backend: instead of painting procedurally
(trees_px), we ask an image-generation model for a rich reference close to
the end result, then RePixel recreates it as proper pixel art. Components:

- **PromptComposer** (`compose_prompt`) — mandate: ONE very descriptive
  prompt. It encodes the identity's master palette (explicit hex ramps),
  the family descriptor's perspective (three-quarter etc.), the target
  canvas proportions, the fixed key light, and hard don'ts (no scene, no
  ground shadow — the pipeline adds its own dithered ellipse).
- **ImageGen adapter** — the swappable box (same philosophy as ODM):
  mode "drop" writes `prompt.md` + an `incoming/` folder and any cloud
  image tool fills it; mode "api" is a provider-pluggable stub that
  activates when a key is hooked up. The contract either way: PNGs land in
  `incoming/`, with provenance recorded.
- **IntentQC** (`intent_qc`) — OPTIONAL gate, interface only for now:
  records "skipped"; a VLM scorer against the request intent is a named
  later feature.
- **ingest** — reference -> repixel -> measured meta -> the SAME asset_qc
  gate and catalog contract as the procedural backend. Genlab assets carry
  style token "gen1" and are ordinary hash-guarded PNGs afterwards
  (hand touch-ups survive, provenance flips to "manual").

Requests live under work/game/<game>/genlab/<req_id>/ (gitignored — the
published sprite is the durable artifact; replay skips a genlab recipe
whose reference images are gone).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from automap import pixelart, repixel

STYLE_TOKEN = "gen1"
GENERATOR = "genlab/1"
REQUEST_SCHEMA = "genlab-request/1.0"

# family -> the reference-subject wording per substyle
SUBJECTS = {
    "tree": {
        "deciduous": "a single deciduous tree with a full leafy canopy made of "
                     "many small rounded leaf tufts, and a short sturdy visible "
                     "trunk with a slight root flare",
        "pine": "a single conifer (pine/fir) tree with stacked tiers of dark "
                "needled branches forming a jagged near-round mass, and a short "
                "sturdy visible trunk",
        "dead": "a single dead leafless tree: a gnarled weathered trunk with "
                "bare twisting branches reaching upward, no foliage",
    },
    "rock": {
        "boulder": "a single large weathered boulder: a massive rounded "
                   "granite mass with a few flat facets, cracks and small "
                   "chips at the base, sitting heavily on the ground",
        "rock": "a single medium field rock: an angular chunk of stone with "
                "clear flat facets and a chipped edge, sitting on the ground",
        "ore": "a single low heaped pile of mined ore: rough grey stone "
               "chunks loosely stacked in a mound, shot through with bright "
               "bronze metallic veins and a few glinting nuggets on top",
    },
    "stump": {
        "stump": "a single tree stump: a short sawn-off trunk cylinder with "
                 "a lighter elliptical cut top face showing growth rings, "
                 "rough dark bark on the sides, and a small root flare where "
                 "it meets the ground",
        "log": "a single fallen log lying on the ground: a horizontal trunk "
               "cylinder with rough bark, one sawn end face showing growth "
               "rings, and a couple of broken branch nubs",
    },
    "column": {
        "intact": "a single Roman marble column: round fluted shaft on a "
                  "square plinth, simple capital on top, pale stone with "
                  "subtle vertical flute shadows",
        "broken": "a single ruined Roman marble column: fluted shaft snapped "
                  "at two-thirds height with a jagged broken top, chipped "
                  "plinth, pale weathered stone",
        "piped": "a single Roman marble column retrofitted with steampunk "
                 "plumbing: a bronze pipe spiraling up the fluted shaft with "
                 "a small valve wheel, verdigris stains bleeding down the "
                 "stone from the fittings",
    },
    "statue": {
        "robed": "a single marble statue of a robed scholar on a low square "
                 "pedestal: toga folds, one arm raised holding a small "
                 "orrery, pale stone with soft shading",
        "founder": "a single bronze statue of a stern philosopher-engineer "
                   "on a marble pedestal: toga over a geared breastplate, "
                   "verdigris streaks on the shoulders and folds",
    },
    "brazier": {
        "standing": "a single standing bronze brazier: a wide fire bowl on "
                    "three legs with a small flame burning above it, warm "
                    "orange flame with a bright core, bronze bowl with rim "
                    "highlights",
        "lantern": "a single standing miner's lantern: a small bronze oil "
                   "lamp with a warm flame visible in its open cage, hung "
                   "from a shepherd's-hook bronze post rising from a small "
                   "weighted base",
    },
    "fountain": {
        "tiered": "a single round two-tiered Roman fountain: a wide marble "
                  "basin holding water, a smaller raised bowl on a center "
                  "pedestal, water spilling from the upper bowl into the "
                  "basin, a few verdigris bronze spouts",
    },
    "machine": {
        "gearstack": "a single steampunk gear machine: a bronze assembly of "
                     "meshed gears of different sizes mounted upright on a "
                     "stone base, a small chimney pipe, verdigris patina in "
                     "the recesses",
        "boiler": "a single steampunk boiler: an upright riveted bronze "
                  "tank on a stone footing with a pressure gauge, a valve "
                  "wheel and a short chimney, verdigris drips under the "
                  "fittings",
        # NO baked-in track: rails are a GROUND class (the atlas's rail_v/
        # rail_h rows) — a cart that carries its own track stub floats on
        # any floor that isn't that stub (mine_hall critique, plan S4)
        "cart": "a single abandoned steampunk mine cart: a riveted bronze "
                "ore tub on four small spoked wheels resting directly on "
                "the ground, verdigris streaks down the sides, a few stone "
                "chunks heaped above the rim",
        "winch": "a single steampunk mine winch: a wide bronze cable drum "
                 "mounted upright between two squat stone pylons, a crank "
                 "handle on one side and a taut cable dropping to a hook, "
                 "verdigris patina in the drum grooves",
    },
    "topiary": {
        "sphere": "a single topiary bush: a dense clipped sphere of foliage "
                  "on a short wooden stem in the ground, small leaf-cluster "
                  "texture",
        "spiral": "a single topiary bush clipped into a spiral cone of "
                  "foliage on a short wooden stem, small leaf-cluster "
                  "texture",
    },
    "bench": {
        "marble": "a single low Roman marble bench SEEN STRAIGHT FROM THE "
                  "FRONT: the thick stone slab seat is one wide horizontal "
                  "band resting on two carved supports, a flat frontal "
                  "composition, pale weathered stone",
        "picnic": "a single wooden picnic set SEEN STRAIGHT FROM THE "
                  "FRONT: the table top is one wide horizontal plank band, "
                  "a long bench fully visible in front of the table, the "
                  "far bench peeking above the top edge behind it, legs "
                  "straight down — a flat frontal composition, weathered "
                  "wood",
    },
    "support": {
        "timber": "a single wooden mine support frame: two thick rough-hewn "
                  "timber posts with a heavy lintel beam wedged across the "
                  "top, standing like an open doorway, visible axe-cut "
                  "facets and wood grain",
    },
    "ride": {
        "ferris": "a single steampunk ferris wheel: a great upright bronze "
                  "lattice wheel on two riveted A-frame support legs, eight "
                  "red-and-cream striped canvas gondola cabs hanging inside "
                  "the rim, a bronze hub with radial spokes, verdigris "
                  "streaks on the older struts, a small boarding platform "
                  "with a lever between the legs",
        "carousel": "a single steampunk carousel pavilion: a round platform "
                    "under a red-and-cream striped conical canvas canopy, "
                    "brass poles around the rim, a bronze center column "
                    "with gearwork at its base, verdigris on the crown",
    },
    "stall": {
        "tent": "a single fairground tent: a tall red-and-cream striped "
                "canvas marquee with a scalloped valance, a peaked roof on "
                "a timber frame, an open dark entrance flap, a small "
                "pennant on the peak",
        "booth": "a single fairground game booth: a timber counter stall "
                 "under a red-and-cream striped canvas awning, prize "
                 "shelves at the back wall, a hanging sign board",
        "highstriker": "a single carnival high-striker: a tall narrow "
                       "timber tower with a bronze bell at the top, a "
                       "red puck track up its face, a striking pad on a "
                       "small base at the bottom",
        "bunting": "a single line of triangular carnival pennant bunting "
                   "strung between two slim wooden poles: red and cream "
                   "flags on a gently sagging rope, each pole on a small "
                   "weighted base",
        "sign": "a single standing fairground sign board: a wooden A-frame "
                "sign with a painted red-and-cream striped border and a "
                "blank center panel, a tiny pennant on its top corner",
        "marquee": "a single grand festival marquee tent: a tall "
                   "red-and-cream striped big-top with a star-tipped "
                   "center peak, swooping scalloped canopy skirts, a dark "
                   "open entrance, guy ropes to small stakes",
        "flagpole": "a single tall slim festival flag pole: a dark wooden "
                    "pole on a small weighted base flying one large red "
                    "swallow-tail pennant near the top",
    },
    "shopsign": {
        "apothecary": "a single hanging shop sign for an apothecary: a "
                      "wooden sign board hung from a scrolled bronze "
                      "bracket on a dark post, the board carved with a "
                      "bold MORTAR AND PESTLE icon, a small verdigris "
                      "accent",
        "garments": "a single hanging shop sign for a tailor: a wooden "
                    "sign board hung from a scrolled bronze bracket on a "
                    "dark post, the board carved with a bold FOLDED "
                    "GARMENT icon with crossed shears",
        "smith": "a single hanging shop sign for a weaponsmith: a wooden "
                 "sign board hung from a scrolled bronze bracket on a "
                 "dark post, the board carved with a bold CROSSED SWORDS "
                 "icon over an anvil",
        "inn": "a single hanging shop sign for an inn: a wooden sign "
               "board hung from a scrolled bronze bracket on a dark "
               "post, the board carved with a bold FOAMING TANKARD icon",
        "general": "a single hanging shop sign for a general goods "
                   "store: a wooden sign board hung from a scrolled "
                   "bronze bracket on a dark post, the board carved with "
                   "a bold HANGING SCALES icon",
    },
    "clutter": {
        "crates": "a single stack of wooden crates: three rough plank "
                  "crates stacked slightly offset, rope loop handles, the "
                  "top lid ajar",
        "barrel": "a single upright wooden barrel with bronze hoops, a "
                  "verdigris stain bleeding under the top hoop",
    },
    "furniture": {
        "desk": "a single wooden school desk seen from a high three-quarter "
                "top-down angle: a sturdy oak writing table with a slightly "
                "sloped top facing the viewer, clear plank grain, four square "
                "legs, a small stack of parchment and a quill resting on top",
        "bookcase": "a single tall wooden bookcase seen from a high "
                    "three-quarter angle: an oak shelf unit of four shelves "
                    "packed with rows of worn leather-bound books and a few "
                    "glass potion bottles, a solid plank base, standing "
                    "upright against a wall",
        "lectern": "a single wooden lectern reading-stand seen from a high "
                   "three-quarter angle: a slanted oak book-rest on a turned "
                   "central post rising from a wide round base, an open tome "
                   "resting on the slope",
        "chalkboard": "a single large slate chalkboard on a wooden A-frame "
                      "stand seen from a high three-quarter angle: a dark "
                      "blue-grey slate writing surface framed in oak, faint "
                      "pale chalk diagrams on the slate, a narrow chalk tray "
                      "across the bottom",
    },
    "portal": {
        "arch": "a single carved stone arch gateway: a semicircular arch of "
                "wedge-shaped voussoir blocks with a protruding keystone, "
                "springing from two squat stone jamb pillars, weathered "
                "mortar joints, standing free like a monumental doorway",
        "bricked": "a single bricked-off gallery mouth: a stone arch opening "
                   "sealed flush with rough mortared brick infill, the brick "
                   "courses slightly uneven, mortar smears at the edges",
        "shaftmouth": "a single open mine shaft mouth in the ground: a low "
                      "ring of mortared stone blocks around a rectangular "
                      "pit opening whose inside falls to pure black, one "
                      "heavy wooden beam frame across the near edge",
    },
}

PERSPECTIVE_TEXT = {
    # THE DOCTRINE (2026-07-18): three-quarter top-down ONLY — the
    # isometric corner views the model drifts to are retired
    "three_quarter": (
        "classic SNES-RPG three-quarter top-down view: the subject is seen "
        "STRAIGHT FROM THE FRONT and slightly from above — its front face "
        "is flat and parallel to the picture frame, all vertical edges stay "
        "perfectly vertical, its ground contact forms ONE horizontal line, "
        "and top surfaces tilt gently toward the viewer. STRICTLY FORBIDDEN: "
        "isometric view, corner or 45-degree diagonal angles, showing a "
        "second side face, rotated bases, vanishing-point perspective"),
    "top_down": "pure top-down (bird's eye) view",
    "side": "straight side view",
}


def _hex_ramps(pal: dict, materials: tuple[str, ...]) -> list[str]:
    lines = []
    # same graceful intersection as repixel.palettize: optional family
    # materials the identity never defined stay out of the prompt
    for mat in (m for m in materials if m in pal["materials"]):
        m = pal["materials"][mat]
        ramp = " ".join("#%02x%02x%02x" % tuple(c) for c in m["ramp"])
        lines.append(f"- {mat}: {ramp} (outline #%02x%02x%02x)"
                     % tuple(m["outline"]))
    return lines


def _family_sizes(family: str) -> dict:
    from automap import asset_creator
    return asset_creator.FAMILIES[family].get("sizes", {"large": (64, 96)})


def compose_prompt(identity: dict, family: str, substyle: str,
                   size_class: str, pal: dict, descriptor: dict,
                   materials: tuple[str, ...]) -> str:
    """The ONE rich prompt. Deterministic — its sha rides in provenance.

    The shared scaffold (style, palette, light, canvas) is family-agnostic;
    everything that names the subject's anatomy comes from the family
    descriptor — `texture_motifs` (what the small repeated elements are),
    `anchor` (the load-bearing form that must survive downscale), and
    `prompt_notes` (extra composition constraints; a dict keys by substyle).
    Tree language leaking into a doorway prompt was the mine_hall arch
    failure (plan S4) — never hardcode a family's anatomy here.
    """
    subject = SUBJECTS.get(family, {}).get(
        substyle, f"a single {substyle} {family}")
    w, h = _family_sizes(family)[size_class]
    perspective = PERSPECTIVE_TEXT.get(descriptor.get("perspective", ""),
                                       descriptor.get("perspective", ""))
    palette_lines = "\n".join(_hex_ramps(pal, materials))
    motifs = descriptor.get("texture_motifs",
                            "small repeated shaded elements true to the material")
    anchor = descriptor.get("anchor", "base")
    notes = descriptor.get("prompt_notes", ())
    if isinstance(notes, dict):
        notes = notes.get(substyle, ())
    note_lines = "".join(f"\n- {n}" for n in notes)
    return f"""Traditional 16-bit pixel art sprite of {subject}.

STYLE — strict traditional pixel art craft:
- crisp, deliberate pixel clusters; no anti-aliasing, no gradients, no noise
- banded shading: exactly 5 flat tones per material, hard steps between bands
- a dark, hue-shifted outline hugging the silhouette (sel-out), softened on
  the light-facing side
- texture built from small repeated shaded elements ({motifs}), never airbrush

PERSPECTIVE: {perspective}.

PALETTE — use ONLY these exact colors (identity "{pal.get('identity', '')}"):
{palette_lines}

LIGHT: one fixed key light from the TOP-LEFT. Highlights face up-left,
shadow tones face down-right.

COMPOSITION:
- exactly ONE subject, centered, filling about 80% of the frame
- subject proportions close to {w}:{h} (it will be downscaled to a
  {w}x{h} px sprite on a 32 px tile grid — keep forms chunky enough to
  survive that: its {anchor} clearly wider than {max(3, w // 12)} px at
  final scale){note_lines}
- plain solid background in a single flat color far from the palette
  (pure magenta #ff00ff), nothing else in frame
- NO ground/cast shadow of any kind — the background stays pure, unshaded
  #ff00ff everywhere, including under the subject and through any opening
  (the game pipeline adds its own dithered shadow)
- no text, no watermark, no border, no photorealism, no 3D render look
"""


# --- request lifecycle (the swappable ImageGen box) -------------------------------

def create_request(genlab_dir: Path, identity: dict, identity_path: str,
                   family: str, substyle: str, size_class: str,
                   count: int, descriptor: dict,
                   materials: tuple[str, ...]) -> Path:
    """Write a drop-mode request: prompt.md + request.json + incoming/."""
    pal = pixelart.master_palette(identity)
    prompt = compose_prompt(identity, family, substyle, size_class, pal,
                            descriptor, materials)
    base = f"{family}_{substyle}_{size_class}"
    n = 1
    while (genlab_dir / f"{base}_r{n}").exists():
        n += 1
    req_dir = genlab_dir / f"{base}_r{n}"
    (req_dir / "incoming").mkdir(parents=True)
    (req_dir / "prompt.md").write_text(prompt)
    (req_dir / "request.json").write_text(json.dumps({
        "schema": REQUEST_SCHEMA,
        "family": family, "substyle": substyle, "size_class": size_class,
        "identity": identity_path, "count": count,
        "prompt_sha12": hashlib.sha256(prompt.encode()).hexdigest()[:12],
        "mode": "drop",
    }, indent=2) + "\n")
    return req_dir


# --- scene concepts: the director's visual sense ----------------------------------
# Before authoring a grid, the director may generate wide concept views of
# the WHOLE scene from its brief — reference only, never traced, never
# shipped (gitignored intermediates; the lessons land in the brief's
# "Composition notes"). Brief-downstream by construction: no brief, no
# concept.

def compose_scene_prompt(brief_md: str, pal: dict) -> str:
    """A wide-illustration prompt distilled from a scene brief."""
    import re as _re

    def section(pattern: str) -> str:
        m = _re.search(rf"^## {pattern}\n(.*?)(?=^## |\Z)", brief_md,
                       _re.M | _re.S)
        return m.group(1).strip() if m else ""

    place = section("The place")
    light = section("Light & air")
    zones = "\n".join(l for l in section(r"Zones[^\n]*").splitlines()
                      if l.startswith("- **"))[:1200]
    ramps = ", ".join(f"{m} #%02x%02x%02x" % tuple(s["ramp"][2])
                      for m, s in sorted(pal["materials"].items()))
    return f"""Wide establishing illustration of a 2D RPG game scene, seen
from a high three-quarter top-down angle (the camera of a 16-bit RPG),
painted as a cohesive game-art concept — NOT a tile map, NOT a diagram:
one readable picture of the whole place.

THE PLACE:
{place[:1500]}

LIGHT:
{light[:600]}

THE ZONES TO COMPOSE (all visible in one view, composed naturally):
{zones}

STYLE: painterly game concept art with crisp shapes; mid colors near this
palette: {ramps}. Dense, lived-in composition — clustered props, varied
spacing, paths that lead somewhere; no text, no UI, no grid lines, no
watermark."""


def generate_scene_concept(brief_path: Path, identity: dict, out_dir: Path,
                           count: int = 2, log=print) -> list[Path]:
    """Fill out_dir with wide concept renders of the scene brief."""
    import base64

    cfg = imagegen_config()
    pal = pixelart.master_palette(identity)
    prompt = compose_scene_prompt(brief_path.read_text(), pal)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "prompt.md").write_text(prompt)
    log(f"[genlab] concept: requesting {count} view(s) (1536x1024) …")
    out = _post_json(
        "https://api.openai.com/v1/images/generations",
        {"model": cfg.get("model", "gpt-image-1"), "prompt": prompt,
         "n": count, "size": "1536x1024",
         "quality": cfg.get("quality", "high")},
        {"Authorization": f"Bearer {cfg['api_key']}"})
    start = len(list(out_dir.glob("concept_*.png")))
    saved = []
    for i, item in enumerate(out.get("data", [])):
        p = out_dir / f"concept_{start + i}.png"
        p.write_bytes(base64.b64decode(item["b64_json"]))
        saved.append(p)
    (out_dir / "generation.json").write_text(json.dumps({
        "model": cfg.get("model", "gpt-image-1"), "n": count,
        "prompt_sha12": hashlib.sha256(prompt.encode()).hexdigest()[:12],
        "saved": [p.name for p in saved]}, indent=2) + "\n")
    log(f"[genlab] concept: {len(saved)} view(s) -> {out_dir} "
        "(reference only — write Composition notes into the brief)")
    return saved


# --- API mode of the ImageGen box --------------------------------------------------
# Provider-pluggable (same philosophy as ODM): the config names the provider,
# the request supplies the prompt, PNGs land in incoming/ exactly as if a
# human had dropped them — everything downstream (preview/ingest) is
# identical. Key resolution: IMAGEGEN_API_KEY / OPENAI_API_KEY env vars,
# else the keyfile (chmod 600, never in the repo):
#   ~/.automap/imagegen.json
#   {"provider": "openai", "api_key": "sk-...", "quality": "high"}

KEYFILE = Path.home() / ".automap" / "imagegen.json"


def imagegen_config() -> dict:
    import os
    key = os.environ.get("IMAGEGEN_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if key:
        return {"provider": "openai", "api_key": key}
    if KEYFILE.exists():
        cfg = json.loads(KEYFILE.read_text())
        # any non-openai provider is self-hosted on the private LAN and needs
        # no key — the genserver transport (docker node) or a1111 (a local
        # Stable-Diffusion-WebUI HTTP server) reaches it directly
        if cfg.get("provider", "openai") != "openai":
            return dict(cfg)
        if cfg.get("api_key"):
            return {"provider": "openai", **cfg}
    raise RuntimeError(
        "no image-generation provider: set IMAGEGEN_API_KEY (OpenAI), or write "
        f"{KEYFILE} as {{\"provider\": \"openai\", \"api_key\": \"...\"}}, "
        "{\"provider\": \"genserver\", \"target\": \"gpu1\"}, or "
        "{\"provider\": \"a1111\", \"endpoint\": \"http://<box-ip>:7860\"}")


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 300) -> dict:
    """One JSON POST (stdlib only; seam for tests to mock)."""
    import urllib.request
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _gen_size(target: tuple[int, int]) -> str:
    """Provider canvas from the sprite's aspect (detail budget, right shape)."""
    w, h = target
    if h >= w * 1.2:
        return "1024x1536"
    if w >= h * 1.2:
        return "1536x1024"
    return "1024x1024"


def generate_via_api(req_dir: Path, provider: str | None = None,
                     count: int | None = None, log=print) -> list[Path]:
    """Fill a request's incoming/ from the configured image provider.

    Returns the saved reference paths; generation metadata is archived at
    <req_dir>/generation.json. Drop mode keeps working unchanged — this
    just automates the human's stage-2 step, one API call per request.
    """
    import base64

    cfg = imagegen_config()
    provider = provider or cfg.get("provider", "openai")
    if provider == "genserver":
        return _generate_via_genserver(req_dir, cfg, count, log)
    if provider == "a1111":
        return _generate_via_a1111(req_dir, cfg, count, log)
    if provider != "openai":
        raise NotImplementedError(f"unknown image provider '{provider}' "
                                  "(supported: openai, genserver, a1111)")
    req = json.loads((req_dir / "request.json").read_text())
    prompt = (req_dir / "prompt.md").read_text()
    target = _family_sizes(req["family"])[req["size_class"]]
    n = count or max(2, int(req.get("count", 2)))
    size = _gen_size(target)
    quality = cfg.get("quality", "high")
    log(f"[genlab] {req_dir.name}: requesting {n} reference(s) "
        f"({size}, quality {quality}) from {provider}…")
    out = _post_json(
        "https://api.openai.com/v1/images/generations",
        {"model": cfg.get("model", "gpt-image-1"), "prompt": prompt,
         "n": n, "size": size, "quality": quality},
        {"Authorization": f"Bearer {cfg['api_key']}"})
    incoming = req_dir / "incoming"
    incoming.mkdir(exist_ok=True)
    start = len(list(incoming.glob("*.png")))
    saved = []
    for i, item in enumerate(out.get("data", [])):
        p = incoming / f"gen_{start + i}.png"
        p.write_bytes(base64.b64decode(item["b64_json"]))
        saved.append(p)
    (req_dir / "generation.json").write_text(json.dumps({
        "provider": provider, "model": cfg.get("model", "gpt-image-1"),
        "size": size, "quality": quality, "n": n,
        "prompt_sha12": req["prompt_sha12"],
        "saved": [p.name for p in saved],
    }, indent=2) + "\n")
    log(f"[genlab] {req_dir.name}: {len(saved)} reference(s) -> incoming/ "
        "(next: assets preview)")
    return saved


def _generate_via_genserver(req_dir: Path, cfg: dict, count: int | None = None,
                            log=print) -> list[Path]:
    """Fill incoming/ from the self-hosted SDXL node via genserver — the
    money-saving swap for the OpenAI box. Downstream (preview/ingest) is
    identical; the only difference is where the pixels came from. genserver
    content-keys the job on prompt+params, so a re-run is a free cache hit.

    Config (~/.automap/imagegen.json): {"provider": "genserver",
    "target": "gpu1", "genserver_root": "~/Cowork/genserver", "steps": 30,
    "model": "…", "seed": 0}.
    """
    import re
    import shutil
    import subprocess
    import tempfile

    req = json.loads((req_dir / "request.json").read_text())
    prompt = (req_dir / "prompt.md").read_text()
    target = str(cfg.get("target", "gpu1"))
    root = Path(str(cfg.get("genserver_root", "~/Cowork/genserver"))).expanduser()
    gs = str(cfg.get("bin") or (root / ".venv" / "bin" / "genserver"))
    w, h = (int(x) for x in _gen_size(_family_sizes(req["family"])[req["size_class"]]).split("x"))
    n = count or max(2, int(req.get("count", 2)))

    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "prompt.txt").write_text(prompt)
        cmd = [gs, "run", "imagegen", "--input", f"prompt={td}",
               "--param", f"n={n}", "--param", f"width={w}", "--param", f"height={h}",
               "--param", f"steps={cfg.get('steps', 30)}",
               "--param", f"guidance={cfg.get('guidance', 6.5)}",
               "--param", f"seed={cfg.get('seed', 0)}",
               "--param", f"model={cfg.get('model', 'stabilityai/stable-diffusion-xl-base-1.0')}",
               "--target", target]
        log(f"[genlab] {req_dir.name}: requesting {n} reference(s) ({w}x{h}) "
            f"from genserver:{target}…")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"genserver imagegen failed: {proc.stderr or proc.stdout}")
        m = re.search(r"outputs:\s*(\S+)", proc.stdout)
        if not m:
            raise RuntimeError(f"genserver: no outputs path in:\n{proc.stdout}")
        out_dir = Path(m.group(1))

    incoming = req_dir / "incoming"
    incoming.mkdir(exist_ok=True)
    start = len(list(incoming.glob("*.png")))
    saved = []
    for i, src in enumerate(sorted(out_dir.glob("gen_*.png"))):
        dst = incoming / f"gen_{start + i}.png"
        shutil.copy2(src, dst)
        saved.append(dst)
    if not saved:
        raise RuntimeError(f"genserver: no PNGs produced in {out_dir}")
    (req_dir / "generation.json").write_text(json.dumps({
        "provider": "genserver", "target": target,
        "model": cfg.get("model", "stabilityai/stable-diffusion-xl-base-1.0"),
        "size": f"{w}x{h}", "n": n, "prompt_sha12": req["prompt_sha12"],
        "saved": [p.name for p in saved],
    }, indent=2) + "\n")
    log(f"[genlab] {req_dir.name}: {len(saved)} reference(s) -> incoming/ "
        "(next: assets preview)")
    return saved


def _generate_via_a1111(req_dir: Path, cfg: dict, count: int | None = None,
                        log=print) -> list[Path]:
    """Fill incoming/ from a local Stable-Diffusion-WebUI (Automatic1111 /
    Forge / reForge) over the LAN — the Windows-native, no-Docker, no-Linux
    swap for the OpenAI box. Reuses _post_json (the same POST seam), so
    downstream (preview/ingest) is byte-for-byte identical.

    Config (~/.automap/imagegen.json): {"provider": "a1111",
    "endpoint": "http://<box-ip>:7860", "steps": 30, "sampler": "DPM++ 2M"}.
    """
    import base64

    req = json.loads((req_dir / "request.json").read_text())
    prompt = (req_dir / "prompt.md").read_text()
    endpoint = str(cfg["endpoint"]).rstrip("/")
    # scale the SDXL-tuned canvas to the model's native size via `base` (the
    # target SHORT side): SD 1.5 wants ~512-640, not 1024, or it duplicates
    # and warps. Default 1024 = unchanged (SDXL). Snap to /64 (SD requirement).
    bw, bh = (int(x) for x in _gen_size(_family_sizes(req["family"])[req["size_class"]]).split("x"))
    scale = int(cfg.get("base", 1024)) / min(bw, bh)
    w = max(64, round(bw * scale / 64) * 64)
    h = max(64, round(bh * scale / 64) * 64)
    n = count or max(2, int(req.get("count", 2)))
    payload = {
        "prompt": prompt,
        "negative_prompt": cfg.get("negative_prompt", ""),
        "steps": int(cfg.get("steps", 30)),
        "width": w, "height": h,
        "cfg_scale": float(cfg.get("guidance", 6.5)),
        "sampler_name": cfg.get("sampler", "DPM++ 2M"),
        "batch_size": n,
        "seed": int(cfg.get("seed", -1)),
    }
    headers = {}
    if cfg.get("api_user"):   # optional --api-auth on the WebUI (LAN hardening)
        tok = base64.b64encode(
            f"{cfg['api_user']}:{cfg.get('api_pass', '')}".encode()).decode()
        headers["Authorization"] = "Basic " + tok
    log(f"[genlab] {req_dir.name}: requesting {n} reference(s) ({w}x{h}) "
        f"from a1111 {endpoint}…")
    out = _post_json(endpoint + "/sdapi/v1/txt2img", payload, headers,
                     timeout=int(cfg.get("timeout", 600)))
    images = out.get("images", [])
    if not images:
        raise RuntimeError(f"a1111: no images returned from {endpoint}")

    incoming = req_dir / "incoming"
    incoming.mkdir(exist_ok=True)
    start = len(list(incoming.glob("*.png")))
    saved = []
    for i, b64 in enumerate(images):
        if "," in b64[:32]:            # strip a data: URI prefix if present
            b64 = b64.split(",", 1)[1]
        p = incoming / f"gen_{start + i}.png"
        p.write_bytes(base64.b64decode(b64))
        saved.append(p)
    (req_dir / "generation.json").write_text(json.dumps({
        "provider": "a1111", "endpoint": endpoint,
        "model": cfg.get("model", "webui-default"),
        "size": f"{w}x{h}", "n": n, "prompt_sha12": req["prompt_sha12"],
        "saved": [p.name for p in saved],
    }, indent=2) + "\n")
    log(f"[genlab] {req_dir.name}: {len(saved)} reference(s) -> incoming/ "
        "(next: assets preview)")
    return saved


def intent_qc(image: Image.Image, request: dict) -> dict:
    """OPTIONAL gate: does the reference match the request intent?

    Interface only — a VLM scorer is a later feature. Recorded in
    provenance so a future pass can re-judge archived references."""
    return {"status": "skipped", "reason": "intent QC not implemented"}


def _subject_meta(material: np.ndarray, names: dict, descriptor: dict,
                  target: tuple[int, int]) -> dict:
    """Measure a repixeled sprite's placement meta (anchor, blocking)."""
    subject = (material > 0) & (material < min(
        i for i, m in names.items() if m.startswith("outline:")))
    if descriptor.get("blocking") == "trunk_base":
        wood_idx = next((i for i, m in names.items() if m == "wood"), None)
        blocking = (material == wood_idx) if wood_idx is not None \
            else np.zeros_like(subject)
        meta = pixelart.measure_prop_meta(subject, blocking,
                                          r_min=4.0, r_max=14.0)
    else:  # "base": the whole mass blocks (rocks, boulders)
        # r_max scales past the 96px prop tier: a landmark's base (ferris
        # A-frames at 160px) legitimately spans wider than any boulder —
        # QC's "circle spans the base" rule would be unsatisfiable at 26
        r_max = 26.0 if target[0] <= 96 else target[0] * 0.45
        meta = pixelart.measure_prop_meta(subject, subject,
                                          r_min=4.0, r_max=r_max)
    meta["size_px"] = list(target)
    return meta


def preview(req_dir: Path, identity: dict, log=print) -> Path | None:
    """Dry-run the recreation: repixel every incoming reference and write a
    review sheet — [reference | recreated sprite 4x] per row, QC verdicts in
    the caption — WITHOUT staging, cataloging, or writing provenance.

    The human-in-the-loop seam: judge the recreation (and which references
    deserve to exist) BEFORE `ingest` commits anything. Re-runnable freely;
    the sheet lands at <req_dir>/preview.png.
    """
    from PIL import ImageDraw
    from automap import asset_creator, asset_qc

    req = json.loads((req_dir / "request.json").read_text())
    family = req["family"]
    fam = asset_creator.FAMILIES[family]
    descriptor = asset_qc.resolve_descriptor(fam["descriptor"], req["substyle"])
    materials = fam.get("materials_by_substyle", {}).get(
        req["substyle"], fam.get("materials", ("foliage", "foliage_dark", "wood")))
    target = _family_sizes(family)[req["size_class"]]
    incoming = sorted((req_dir / "incoming").glob("*.png"))
    if not incoming:
        log(f"[genlab] {req_dir.name}: nothing in incoming/ — drop reference "
            "PNGs there (prompt: prompt.md)")
        return None

    pal = pixelart.master_palette(identity)
    row_h, cap_h, pad = 256, 28, 8
    rows = []
    for src in incoming:
        ref = Image.open(src).convert("RGBA")
        sprite, material, band, names = repixel.repixelize(
            ref, pal, target, descriptor, materials)
        meta = _subject_meta(material, names, descriptor, target)
        checks = asset_qc.run_qc(np.asarray(sprite), meta, pal, descriptor)
        bad = [c for c in checks if not c.ok]
        verdict = "QC PASS" if not bad else \
            "QC FAIL: " + "; ".join(f"{c.name} ({c.detail})" for c in bad)
        # perspective ADVISORY (never a gate): an isometric corner view's
        # base contour bulges downward at center (diamond base); a
        # doctrine-compliant front view's base line runs flat
        subj = (material > 0) & (material < min(
            i for i, m in names.items() if m.startswith("outline:")))
        cols = np.nonzero(subj.any(axis=0))[0]
        hint = ""
        if len(cols) >= 12:
            base_y = np.array([np.nonzero(subj[:, c])[0].max() for c in cols])
            third = len(cols) // 3
            bulge = base_y[third:-third].mean() - \
                np.concatenate([base_y[:third], base_y[-third:]]).mean()
            if bulge > 0.10 * len(cols):
                hint = (f"  [perspective hint: base bulges {bulge:.0f}px at "
                        "center — possible ISOMETRIC corner view]")
        log(f"[genlab] preview {src.name}: {verdict}{hint}")
        ref_t = ref.resize((max(1, int(ref.width * row_h / ref.height)), row_h))
        scale = max(1, row_h // sprite.height)
        spr_t = sprite.resize((sprite.width * scale, sprite.height * scale),
                              Image.NEAREST)
        w = ref_t.width + pad + spr_t.width
        row = Image.new("RGBA", (w, row_h + cap_h), (38, 38, 42, 255))
        row.paste(ref_t, (0, 0))
        row.paste(spr_t, (ref_t.width + pad, (row_h - spr_t.height) // 2),
                  spr_t)
        ImageDraw.Draw(row).text((4, row_h + 6),
                                 f"{src.name} -> {target[0]}x{target[1]}  |  "
                                 f"{verdict}"[:180], fill=(230, 230, 220, 255))
        rows.append(row)

    sheet = Image.new("RGBA", (max(r.width for r in rows),
                               sum(r.height + pad for r in rows)),
                      (38, 38, 42, 255))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height + pad
    out = req_dir / "preview.png"
    sheet.save(out)
    log(f"[genlab] preview sheet -> {out}")
    return out


# --- ingest: reference -> pixel art -> the shared gate ----------------------------

def ingest(req_dir: Path, game_dir: Path, staging_dir: Path, identity: dict,
           log=print) -> dict:
    """RePixel every incoming reference through the standard asset gate.

    Stages sprites + catalog entries exactly like the procedural backend
    (same schema, style token "gen1"); archives index maps + provenance
    beside the request. Returns {"staged": [names], "skipped": [files]}.
    """
    from automap import asset_creator, asset_qc

    req = json.loads((req_dir / "request.json").read_text())
    family, substyle = req["family"], req["substyle"]
    fam = asset_creator.FAMILIES[family]
    descriptor = asset_qc.resolve_descriptor(fam["descriptor"], substyle)
    materials = fam.get("materials_by_substyle", {}).get(
        substyle, fam.get("materials", ("foliage", "foliage_dark", "wood")))
    target = _family_sizes(family)[req["size_class"]]
    identity_name = str(identity.get("name", "identity"))

    incoming = sorted((req_dir / "incoming").glob("*.png"))
    if not incoming:
        log(f"[genlab] {req_dir.name}: nothing in incoming/ — drop reference "
            "PNGs there (prompt: prompt.md)")
        return {"staged": [], "skipped": []}

    pal = pixelart.master_palette(identity)
    staging_dir.mkdir(parents=True, exist_ok=True)
    pixelart.write_palette(staging_dir.parent / "palette", pal)
    catalog_path = staging_dir / "props.json"
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() \
        else {"schema": asset_creator.CATALOG_SCHEMA,
              "identity": identity_name, "props": {}}
    live = asset_creator.load_catalog(game_dir)
    v = asset_creator.next_variant_start(live, catalog, substyle, family,
                                         count=len(incoming))
    prov_dir = req_dir / "provenance"
    prov_dir.mkdir(exist_ok=True)
    already = {json.loads(p.read_text()).get("source_sha12")
               for p in prov_dir.glob("*.json")}

    staged, skipped = [], []
    for src in incoming:
        sha = hashlib.sha256(src.read_bytes()).hexdigest()[:12]
        if sha in already:  # idempotent: a reference is ingested once
            continue
        ref = Image.open(src)
        gate = intent_qc(ref, req)
        sprite, material, band, names = repixel.repixelize(
            ref, pal, target, descriptor, materials)
        # the family descriptor names the blocking element to measure
        meta = _subject_meta(material, names, descriptor, target)
        checks = asset_qc.run_qc(np.asarray(sprite), meta, pal, descriptor)
        bad = [c for c in checks if not c.ok]
        name = f"{substyle}_{v}"
        if bad:
            log(f"[genlab] {src.name}: QC FAIL — "
                + "; ".join(f"{c.name} ({c.detail})" for c in bad)
                + " — not staged (fix the reference or the repixel passes)")
            skipped.append(src.name)
            continue
        sprite.save(staging_dir / f"{name}.png")
        anim = asset_creator.animation_for(family, substyle)
        n_frames = 1
        if anim:
            from automap import animate_px
            n_frames = animate_px.attach_frames(
                staging_dir, name, material, band, names, pal, anim, sprite,
                seed_key=f"{identity_name}:{name}:{anim['kind']}", log=log)
        np.savez_compressed(prov_dir / f"{name}.npz",
                            material=material, band=band)
        (prov_dir / f"{name}.json").write_text(json.dumps({
            "source": src.name,
            "source_sha12": sha,
            "prompt_sha12": req["prompt_sha12"],
            "intent_qc": gate,
            "material_names": {str(k): v2 for k, v2 in names.items()},
        }, indent=2) + "\n")
        w, h = sprite.size
        catalog["props"][name] = {
            "file": f"{name}.png", "size": [w, h], "frames": n_frames,
            "anchor_y": meta["anchor_y"], "collision_r": meta["collision_r"],
            "footprint": meta.get("footprint"),
            "family": family, "substyle": substyle,
            "identity_name": identity_name,
            "style": STYLE_TOKEN, "generator": GENERATOR,
            "provenance": "generated",
        }
        staged.append(name)
        v += 1
    catalog["schema"] = asset_creator.CATALOG_SCHEMA
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n")
    log(f"[genlab] {req_dir.name}: staged {len(staged)} "
        f"({', '.join(staged) or '-'}), skipped {len(skipped)}")
    return {"staged": staged, "skipped": skipped}
