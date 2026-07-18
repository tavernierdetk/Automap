"""NPC Creator (automap/npc_creator.py) — figure recreation contract."""
import json
from pathlib import Path

import numpy as np
from PIL import Image

from automap import npc_creator, pixelart

ROOT = Path(__file__).resolve().parent.parent
GAME = ROOT / "games" / "entropy"
IDENTITY = json.loads((ROOT / "identities" / "vaporis.json").read_text())


def _synthetic_reference() -> Image.Image:
    """A blocky person on magenta — enough for the quantizer contract."""
    img = Image.new("RGB", (512, 768), (255, 0, 255))
    a = np.asarray(img).copy()
    a[80:280, 180:330] = (216, 158, 115)    # head (skin-ish)
    a[280:640, 140:370] = (60, 90, 120)     # robe (cloth-ish)
    a[640:720, 160:230] = (90, 60, 40)      # boots
    a[640:720, 280:350] = (90, 60, 40)
    return Image.fromarray(a)


def test_quantized_figure_is_palette_member_by_construction():
    pal = pixelart.master_palette(IDENTITY)
    sprite = npc_creator.quantize_figure(_synthetic_reference(), pal, (64, 96))
    arr = np.asarray(sprite)
    opaque = arr[arr[..., 3] > 0][:, :3]
    legal: set[tuple] = set()
    for mat in npc_creator.FIGURE_MATERIALS:
        m = pal["materials"].get(mat)
        if m:
            legal.update(tuple(c) for c in np.asarray(m["ramp"], int).tolist())
            legal.add(tuple(int(v) for v in m["outline"]))
    assert opaque.size and all(tuple(p) in legal for p in opaque.tolist())


def test_short_figures_keep_canvas_headroom(tmp_path):
    req = tmp_path / "kid_r1" / "incoming"
    req.mkdir(parents=True)
    _synthetic_reference().save(req / "gen_0.png")
    out = npc_creator.ingest_figure(tmp_path / "kid_r1", IDENTITY,
                                    tmp_path / "frames", "kid",
                                    height_frac=0.68)
    arr = np.asarray(Image.open(out))
    assert arr.shape[:2] == (96, 64)          # full canvas
    ys = np.nonzero(arr[..., 3])[0]
    assert ys.min() >= 20                     # headroom: short person
    assert ys.max() >= 90                     # feet on the ground line


def test_stats_presets_all_within_band():
    for arch, stats in npc_creator.ARCHETYPE_STATS.items():
        assert 24 <= sum(stats.values()) <= 28, arch


# --- the ULPC channel: the animation normalization contract ---------------

def test_engine_face_swaps_front_back_only():
    assert npc_creator.engine_face("Walk_front") == "Walk_back"
    assert npc_creator.engine_face("Walk_back") == "Walk_front"
    assert npc_creator.engine_face("Idle_left") == "Idle_left"
    assert npc_creator.engine_face("Run_right") == "Run_right"


def test_ulpc_fps_map_per_animation_family():
    fps = npc_creator.ulpc_fps_map(
        ["Walk_front", "Idle_front", "Run_back", "Slash_left"])
    assert fps["Walk_front"] == 8
    assert fps["Idle_front"] == 4
    assert fps["Run_back"] == 10
    assert fps["Slash_left"] == 8  # default for non-locomotion families


def test_committed_fair_builds_reference_real_creatures():
    builds = sorted((GAME / "casting" / "builds").glob("*.ulpc.json"))
    assert len(builds) >= 16
    creatures = {p.stem for p in (GAME / "creatures").glob("*.json")}
    for b in builds:
        slug = b.name.replace(".ulpc.json", "")
        assert slug in creatures, f"build without creature doc: {slug}"
        doc = json.loads(b.read_text())
        assert doc["schema"] == "ulpc.build/1.0"
        assert doc["layers"], slug
        cdoc = json.loads((GAME / "creatures" / f"{slug}.json").read_text())
        assert cdoc["visual"]["family"] == "ulpc", slug
