"""Buildings: the assembled classic-RPG building family (facade + cornice +
roof as ONE multi-cell prop; rect footprint; variant 0 = the prefab)."""
import json
from pathlib import Path

import numpy as np

from automap import asset_qc, buildings2d
from automap.asset_creator import FAMILIES
from automap.pixelart import master_palette

IDENTITY = json.loads(Path("identities/vaporis.json").read_text())
PAL = master_palette(IDENTITY)
DESC = FAMILIES["building"]["descriptor"]
DIST = FAMILIES["building"]["distinctness"]


def _built(substyle="house", count=2):
    return buildings2d.build_set(PAL, "vaporis", substyle, count, **DIST)


def test_deterministic():
    a = _built()
    b = _built()
    for name in a:
        assert np.array_equal(np.asarray(a[name][0]), np.asarray(b[name][0]))


def test_canvases_are_grid_aligned():
    for sub in buildings2d.PREFABS:
        for name, (img, _) in _built(sub, 2).items():
            assert img.width % 32 == 0 and img.height % 32 == 0, name
            assert img.width <= 8 * 32


def test_prefab_house_anatomy():
    """Variant 0 IS the standard basic build: roof mass on top, cornice
    strip, plaster field below, a wood door at the base center."""
    img, meta = _built("house", 1)["house_0"]
    material, band, names = meta["maps"]
    by_name = {}
    for idx, m in names.items():
        by_name.setdefault(m, idx)
    h, w = material.shape
    roof = material == by_name["rooftile"]
    wall = material == by_name["plaster"]
    ys_roof = np.nonzero(roof.any(axis=1))[0]
    ys_wall = np.nonzero(wall.any(axis=1))[0]
    assert ys_roof.max() < ys_wall.min() + 8      # roof sits above the wall
    # a full-width cornice band separates them
    trim = material == by_name["wood"]
    cornice_rows = trim.sum(axis=1) > w * 0.8
    assert cornice_rows.any()
    # the door: wood pixels straddling meta["door"] at the base
    dx, dy = meta["door"]
    assert trim[dy - 6:dy - 2, dx - 4:dx + 4].any()
    assert meta["anchor_y"] == int(np.nonzero((material > 0).any(axis=1))[0].max())


def test_rect_footprint_matches_geometry():
    for sub in buildings2d.PREFABS:
        img, meta = _built(sub, 1)[f"{sub}_0"]
        fp = meta["footprint"]
        assert fp["kind"] == "rect"
        # bottom edge sits on the anchor row; width spans the facade
        assert abs((fp["center"][1] + fp["half"][1]) - meta["anchor_y"]) <= 1
        assert fp["half"][0] * 2 >= img.width * 0.8


def test_full_qc_gate_passes():
    for sub in buildings2d.PREFABS:
        desc = asset_qc.resolve_descriptor(DESC, sub)
        for name, (img, meta) in _built(sub, 2).items():
            m = dict(meta)
            m.pop("maps")
            checks = asset_qc.run_qc(np.asarray(img), m, PAL, desc)
            bad = [f"{c.name} ({c.detail})" for c in checks if not c.ok]
            assert not bad, (name, bad)


def test_variants_are_distinct_on_interiors():
    from automap import pixelart as px
    built = _built("house", 3)
    arrs = [np.asarray(img) for img, _ in built.values()]
    for i in range(len(arrs)):
        for j in range(i + 1, len(arrs)):
            assert px.interior_difference(arrs[i], arrs[j]) >= DIST["interior_min"]


def test_unknown_substyle_raises():
    import pytest
    with pytest.raises(ValueError, match="unknown building substyle"):
        buildings2d.build_set(PAL, "vaporis", "castle", 1)
