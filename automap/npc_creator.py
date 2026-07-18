"""NPC Creator — the Asset Creator's twin for people (R3).

Builds the two halves of an NPC:

1. **The creature document** (``games/<g>/creatures/<slug>.json``,
   creature@) — archetype-flavored stats balanced to the same total band
   the character-admission harness aims for (25–27), persona carrying
   ``region`` (the casting gate's R-005 check reads it).
2. **The figure sprite** — genlab request → gpt-image-1 reference →
   repixel recreation at 64×96 (the 96 px figure contract), staged as a
   creature frames dir (``work/game/<g>/creatures_px/<slug>/Idle/``) and
   registered in ``assets.json`` under ``creature_sprites`` with
   ``"local": true`` so the publisher builds the same manifest it builds
   for reference-repo people.

Figures are NOT props: no ground shadow (creatures ship shadowless like
the player), no blocking footprint, never in the props catalog. The
craft doctrines still bind — three-quarter top-down, palette-strict,
sel-out outline — via the same repixel pipeline.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from automap import genlab, pixelart, repixel
from automap import pixelart as px

FIGURE_TARGET = (64, 96)  # canvas; the standing body fills the height
FIGURE_MATERIALS = ("skin", "skin_deep", "cloth", "canvas", "plaster",
                    "bronze", "rooftile", "roofslate", "verdigris")

# stat presets per archetype — totals sit in the admission band (25–27);
# a slug-seeded swap of one point keeps crowds from being clones
ARCHETYPE_STATS = {
    "scholar":   {"lucidity": 8, "chaos_mastery": 6, "terrain_control": 5,
                  "creature_affinity": 4, "kinesthetic": 3},
    "artisan":   {"kinesthetic": 7, "terrain_control": 6, "lucidity": 5,
                  "creature_affinity": 4, "chaos_mastery": 4},
    "vendor":    {"lucidity": 6, "creature_affinity": 6, "kinesthetic": 5,
                  "terrain_control": 5, "chaos_mastery": 4},
    "official":  {"lucidity": 7, "terrain_control": 7, "kinesthetic": 4,
                  "creature_affinity": 4, "chaos_mastery": 3},
    "performer": {"chaos_mastery": 7, "lucidity": 6, "kinesthetic": 6,
                  "creature_affinity": 4, "terrain_control": 3},
    "laborer":   {"kinesthetic": 8, "terrain_control": 6,
                  "creature_affinity": 4, "lucidity": 4, "chaos_mastery": 3},
    "child":     {"creature_affinity": 7, "chaos_mastery": 7, "kinesthetic": 5,
                  "terrain_control": 4, "lucidity": 3},
}


def npc_stats(slug: str, archetype: str) -> dict[str, int]:
    """Preset flavor + a deterministic one-point swap (total preserved)."""
    base = dict(ARCHETYPE_STATS[archetype])
    keys = sorted(base)
    h = int(hashlib.sha256(slug.encode()).hexdigest(), 16)
    src, dst = keys[h % 5], keys[(h // 5) % 5]
    if src != dst and base[src] > 2 and base[dst] < 9:
        base[src] -= 1
        base[dst] += 1
    return base


def write_creature(game_dir: Path, slug: str, name: str, archetype: str,
                   region: str, home: str, faction: str,
                   xp_reward: int = 0) -> Path:
    doc = {
        "id": slug,
        "name": name,
        "archetype": archetype,
        "stats": npc_stats(slug, archetype),
        "skills": ["attack"],
        "xp_reward": xp_reward,
        "visual": {"family": "figure_px"},
        "persona": {"faction": faction, "home": home, "region": region},
    }
    try:
        import platform_specs
        versions = sorted((Path(platform_specs.__file__).parent.parent
                           / "schemas" / "creature").glob("*.json"))
        if versions:
            platform_specs.validate(doc, "creature", versions[-1].stem)
    except ImportError:
        pass
    out = game_dir / "creatures" / f"{slug}.json"
    out.write_text(json.dumps(doc, indent=2) + "\n")
    return out


def compose_figure_prompt(identity: dict, look: str) -> str:
    """The figure prompt — person-specific composition over the shared
    craft scaffold (compose_prompt owns prop anatomy; people need their
    own: full standing body, front-facing, feet at bottom center)."""
    pal = pixelart.master_palette(identity)
    palette_lines = "\n".join(genlab._hex_ramps(pal, FIGURE_MATERIALS))
    w, h = FIGURE_TARGET
    return f"""Traditional 16-bit pixel art sprite of a single video game character:
{look}.

STYLE — strict traditional pixel art craft:
- crisp, deliberate pixel clusters; no anti-aliasing, no gradients, no noise
- banded shading: exactly 5 flat tones per material, hard steps between bands
- a dark, hue-shifted outline hugging the silhouette (sel-out)

PERSPECTIVE: three-quarter top-down RPG view, the camera slightly above —
the character SEEN STRAIGHT FROM THE FRONT, standing upright, facing the
viewer, both feet on the ground. NOT isometric, NOT rotated, NO high-angle
foreshortening — head up, feet down, like a classic SNES RPG townsperson.

PALETTE — use ONLY these exact colors (identity "{pal.get('identity', '')}"):
{palette_lines}

LIGHT: one fixed key light from the TOP-LEFT.

COMPOSITION:
- exactly ONE character, centered, full body head to toe filling about 90%
  of the frame height, feet at the bottom center
- proportions close to {w}:{h} (downscaled to a {w}x{h} px sprite —
  keep the silhouette chunky: readable head, torso, legs at that scale)
- plain solid background in pure magenta #ff00ff, nothing else in frame
- NO ground/cast shadow of any kind — the background stays pure #ff00ff
  everywhere, including under the feet
- no text, no watermark, no border, no photorealism, no 3D render look
"""


def create_figure_request(npc_dir: Path, identity: dict, identity_path: str,
                          slug: str, look: str) -> Path:
    prompt = compose_figure_prompt(identity, look)
    n = 1
    while (npc_dir / f"{slug}_r{n}").exists():
        n += 1
    req_dir = npc_dir / f"{slug}_r{n}"
    (req_dir / "incoming").mkdir(parents=True)
    (req_dir / "prompt.md").write_text(prompt)
    (req_dir / "request.json").write_text(json.dumps({
        "schema": "npc-figure-request@1",
        "slug": slug, "look": look, "identity": identity_path,
        "target": list(FIGURE_TARGET),
        "prompt_sha12": hashlib.sha256(prompt.encode()).hexdigest()[:12],
    }, indent=2) + "\n")
    return req_dir


def generate_figure(req_dir: Path, count: int = 1, log=print) -> list[Path]:
    """One API call — same provider box as genlab, figure-sized canvas."""
    import base64
    cfg = genlab.imagegen_config()
    req = json.loads((req_dir / "request.json").read_text())
    prompt = (req_dir / "prompt.md").read_text()
    size = genlab._gen_size(tuple(req["target"]))
    log(f"[npc] {req_dir.name}: requesting {count} reference(s) ({size})…")
    out = genlab._post_json(
        "https://api.openai.com/v1/images/generations",
        {"model": cfg.get("model", "gpt-image-1"), "prompt": prompt,
         "n": count, "size": size, "quality": cfg.get("quality", "high")},
        {"Authorization": f"Bearer {cfg['api_key']}"})
    incoming = req_dir / "incoming"
    incoming.mkdir(exist_ok=True)
    start = len(list(incoming.glob("*.png")))
    saved = []
    for i, item in enumerate(out.get("data", [])):
        p = incoming / f"gen_{start + i}.png"
        p.write_bytes(base64.b64decode(item["b64_json"]))
        saved.append(p)
    log(f"[npc] {req_dir.name}: {len(saved)} reference(s) -> incoming/")
    return saved


def quantize_figure(img: Image.Image, pal: dict,
                    target: tuple[int, int]) -> Image.Image:
    """Figure recreation: dominant-color downscale + direct nearest-ramp
    quantization + sel-out ring.

    Props go through palettize→smooth→reband (repixel.repixelize) because
    their references need band DISCIPLINE imposed. Figure references come
    back already banded (the prompt works); imposing the prop pipeline on
    them muddies faces and shifts robes wholesale. Here every subject
    pixel snaps to the nearest ramp color across FIGURE_MATERIALS —
    palette-member by construction, the reference's own shading kept.
    """
    arr = np.asarray(img.convert("RGBA"))
    mask = repixel.subject_mask(arr)
    rgb, mask = repixel.downscale(arr, mask, target)

    ramps: list[tuple[str, np.ndarray]] = []   # (material, [5,3] ramp)
    outlines: dict[str, np.ndarray] = {}
    for mat in FIGURE_MATERIALS:
        m = pal["materials"].get(mat)
        if m is None:
            continue
        ramps.append((mat, np.asarray(m["ramp"], dtype=float)))
        outlines[mat] = np.asarray(m["outline"], dtype=np.uint8)
    colors = np.concatenate([r for _, r in ramps])          # [N,3]
    color_mat = np.concatenate([[i] * len(r) for i, (_, r) in enumerate(ramps)])
    lab = repixel._srgb_to_lab(colors[None, :, :])[0]  # expects 0–255
    px_lab = repixel._srgb_to_lab(rgb[mask][None, :, :3])[0]
    nearest = np.argmin(
        ((px_lab[:, None, :] - lab[None, :, :]) ** 2).sum(-1), axis=1)

    out = np.zeros((*mask.shape, 4), np.uint8)
    out[mask, :3] = colors[nearest].astype(np.uint8)
    out[mask, 3] = 255
    mat_idx = np.full(mask.shape, -1, np.int16)
    mat_idx[mask] = color_mat[nearest]

    # sel-out ring: each ring pixel takes the outline of the material it touches
    ring = px.outer_ring(mask)
    for i, (mat, _) in enumerate(ramps):
        near = px.dilate(mat_idx == i)
        take = ring & near & (out[..., 3] == 0)
        out[take, :3] = outlines[mat]
        out[take, 3] = 255
        ring &= ~take
    return Image.fromarray(out, "RGBA")


def ingest_figure(req_dir: Path, identity: dict, frames_root: Path,
                  slug: str, reference: Path | None = None,
                  height_frac: float = 1.0) -> Path:
    """Reference → repixel recreation → staged Idle frame dir.

    No ground shadow (descriptor without `shadow`), no catalog: the
    output is a creature frames dir the publisher turns into a manifest.

    ``height_frac`` < 1 makes a SHORT person: the engine normalizes the
    TEXTURE to 96 px, so stature lives in canvas headroom — the figure
    is repixeled smaller and bottom-aligned on the full canvas (a child
    at 0.68 stands two-thirds of an adult, feet on the same line).
    """
    refs = sorted((req_dir / "incoming").glob("*.png"))
    if reference is None:
        if not refs:
            raise FileNotFoundError(f"no references in {req_dir}/incoming")
        reference = refs[0]
    pal = pixelart.master_palette(identity)
    w, h = FIGURE_TARGET
    body_h = max(16, int(round(h * height_frac)))
    body_w = max(16, int(round(w * height_frac)))
    sprite = quantize_figure(Image.open(reference), pal, (body_w, body_h))
    if (body_w, body_h) != (w, h):
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        canvas.paste(sprite, ((w - body_w) // 2, h - body_h))
        sprite = canvas
    out_dir = frames_root / slug / "Idle"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{slug}_idle_0.png"
    sprite.save(out)
    return out


# --- the ULPC channel (docs/explorations/ulpc-casting-integration.md) ------
# Composed, fully animated people from the LiberatedPixelCup asset base via
# PixelAssetCreator's sprite-compose. The committed source of truth is the
# build spec at games/<g>/casting/builds/<slug>.ulpc.json; frames stage like
# figure frames and publish through the same stage-12 manifest path.

PIXELASSET_ROOT_DEFAULT = Path.home() / "Cowork" / "PixelAssetCreator"
# the slicer's orientation folders ARE the engine animation contract;
# per-animation fps by prefix (walk cycle 8, idle breath 4, run 10)
ULPC_FPS = {"Walk": 8, "Idle": 4, "Run": 10}
ULPC_DEFAULT_FPS = 8


def ulpc_fps_map(anim_dirs: list[str]) -> dict[str, int]:
    return {d: ULPC_FPS.get(d.split("_")[0], ULPC_DEFAULT_FPS)
            for d in sorted(anim_dirs)}


def engine_face(composer_dir: str) -> str:
    """Composer facing → engine facing. The composer labels LPC row 0
    (walking UP, back visible) 'front'; the engine's 'front' faces the
    camera. Front/back swap; left/right are true."""
    anim, _, face = composer_dir.partition("_")
    face = {"front": "back", "back": "front"}.get(face, face)
    return f"{anim}_{face}" if face else anim


def compose_ulpc(game_dir: Path, slug: str, build_path: Path,
                 frames_root: Path, log=print) -> dict:
    """Run the bridge CLI, normalize to engine animations, relocate.

    Normalization (docs/explorations/ulpc-casting-integration.md):
    - only `walk` is COMPOSED — it is the one animation every LPC layer
      ships, so the character is fully dressed by construction (idle/run
      sheets are missing for most clothing; composing them natively
      strips layers → naked NPCs);
    - `Idle_<face>` is SYNTHESIZED from the walk stance frame (LPC walk
      column 0), `Run_<face>` from the step cycle (columns 1+, played at
      run fps);
    - the composer labels LPC row 0 (walking UP, back visible) "front";
      the engine's "front" faces the camera — front/back swap here.

    Replaces any previously staged frames for the slug — one body per
    person.
    """
    import os
    import shutil
    import subprocess
    import tempfile

    pixelasset = Path(os.environ.get("PIXELASSET_ROOT",
                                     PIXELASSET_ROOT_DEFAULT))
    bridge = Path(__file__).resolve().parent.parent / "tools" / "ulpc_compose.mjs"
    with tempfile.TemporaryDirectory(prefix=f"ulpc_{slug}_") as tmp:
        # walk-only compose regardless of the spec's ambitions (see above)
        build = json.loads(build_path.read_text())
        build["animations"] = ["walk"]
        walk_build = Path(tmp) / "build.walk.json"
        walk_build.write_text(json.dumps(build))
        # cwd = the PixelAssetCreator checkout: resolveUlpcSheetDefs walks
        # candidates from process.cwd(); the result goes to a file because
        # the composer's logger owns stdout
        result_file = Path(tmp) / "result.json"
        run = subprocess.run(
            ["node", str(bridge), str(walk_build), tmp, slug,
             str(result_file)],
            cwd=pixelasset, capture_output=True, text=True)
        if run.returncode != 0 or not result_file.exists():
            raise RuntimeError(f"ulpc compose failed for {slug}:\n{run.stderr}")
        result = json.loads(result_file.read_text())
        frames_src = Path(tmp) / "ulpc_frames"
        walk_dirs = sorted(p.name for p in frames_src.iterdir()
                           if p.is_dir() and p.name.startswith("Walk_"))
        if not walk_dirs:
            raise RuntimeError(f"ulpc compose produced no walk frames for {slug}")

        dest = frames_root / slug
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        for d in walk_dirs:
            face = engine_face(d).split("_", 1)[1]
            frames = sorted((frames_src / d).glob("*.png"))
            stance, cycle = frames[0], (frames[1:] or frames)
            walk_out = dest / f"Walk_{face}"
            walk_out.mkdir()
            for f in frames:
                shutil.copy2(f, walk_out / f.name)
            idle_out = dest / f"Idle_{face}"
            idle_out.mkdir()
            shutil.copy2(stance, idle_out / f"{slug}_idle_000.png")
            run_out = dest / f"Run_{face}"
            run_out.mkdir()
            for i, f in enumerate(cycle):
                shutil.copy2(f, run_out / f"{slug}_run_{i:03d}.png")
        anim_dirs = sorted(p.name for p in dest.iterdir() if p.is_dir())
    for w in result.get("warnings", []):
        log(f"[ulpc] {slug}: WARN {w.get('category')}/{w.get('variant')} "
            f"({w.get('reason')})")
    return {"animations": anim_dirs, "warnings": result.get("warnings", [])}


def register_sprite(game_dir: Path, slug: str, frames_dir: str,
                    fps: int | dict = 4) -> None:
    """Add/refresh the local creature_sprites entry in assets.json."""
    assets_path = game_dir / "assets.json"
    spec = json.loads(assets_path.read_text())
    entries = [c for c in spec.get("creature_sprites", [])
               if c.get("slug") != slug]
    entries.append({"slug": slug, "frames_dir": frames_dir,
                    "fps": fps, "local": True})  # fps: int, or per-anim dict
    spec["creature_sprites"] = sorted(entries, key=lambda c: c["slug"])
    assets_path.write_text(json.dumps(spec, indent=2) + "\n")
