"""NPC Creator (automap/npc_creator.py) — figure recreation contract."""
import json
from pathlib import Path

import numpy as np
from PIL import Image

from automap import npc_creator, pixelart

ROOT = Path(__file__).resolve().parent.parent
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
