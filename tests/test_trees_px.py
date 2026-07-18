"""Pixel-art trees: the plan's quality bars as tests."""
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest

from automap.pixelart import master_palette, palette_colors, silhouette_iou
from automap.trees_px import build_set, build_variant

IDENTITY = json.loads(Path("identities/entropy.json").read_text())
PAL = master_palette(IDENTITY)


@pytest.fixture(scope="module")
def deciduous_set():
    return build_set(PAL, "entropy", "deciduous", 6)


def test_deterministic():
    a = build_set(PAL, "entropy", "deciduous", 2)
    b = build_set(PAL, "entropy", "deciduous", 2)
    for k in a:
        assert a[k][0].tobytes() == b[k][0].tobytes()


def test_palette_membership_and_crisp_alpha(deciduous_set):
    allowed = palette_colors(PAL)
    for name, (img, _) in deciduous_set.items():
        arr = np.asarray(img)
        assert set(np.unique(arr[:, :, 3])) <= {0, 255}, name
        opaque = arr[arr[:, :, 3] == 255][:, :3]
        assert {tuple(c) for c in opaque} <= allowed, name


def test_all_variants_rooted_and_substantial(deciduous_set):
    for name, (img, meta) in deciduous_set.items():
        mask = np.asarray(img)[:, :, 3] > 0
        assert mask.sum() >= mask.size * 0.18, name + " too sparse"
        assert 0 < meta["anchor_y"] <= img.height
        assert meta["collision_r"] > 0


def test_variants_are_siblings_not_clones(deciduous_set):
    # top-down canopies are all near-round: silhouettes stay similar, so the
    # standard is TWO metrics — shape not identical AND interiors differ
    from automap.pixelart import interior_difference
    arrs = [np.asarray(img) for img, _ in deciduous_set.values()]
    masks = [a[:, :, 3] > 0 for a in arrs]
    ious = [silhouette_iou(a, b) for a, b in combinations(masks, 2)]
    diffs = [interior_difference(a, b) for a, b in combinations(arrs, 2)]
    assert max(ious) <= 0.90, f"silhouette clone (max IoU {max(ious):.2f})"
    assert min(diffs) >= 0.30, f"interior clone (min diff {min(diffs):.2f})"


def test_outline_ring_present():
    img, _ = build_variant(PAL, "deciduous", "entropy:tree:deciduous:0:px2",
                           "large")
    arr = np.asarray(img).astype(int)
    mask = arr[:, :, 3] > 0
    interior = mask & np.roll(mask, 1, 0) & np.roll(mask, -1, 0) \
        & np.roll(mask, 1, 1) & np.roll(mask, -1, 1)
    # exclude the dithered ground shadow (isolated checker pixels) from the
    # ring measurement: only consider edge pixels adjacent to interior mass
    edge = mask & ~interior & (np.roll(interior, 1, 0) | np.roll(interior, -1, 0)
                               | np.roll(interior, 1, 1) | np.roll(interior, -1, 1))
    edge_lum = arr[edge][:, :3].mean()
    inner_lum = arr[interior][:, :3].mean()
    assert edge_lum < inner_lum * 0.9  # dark ring hugs the silhouette


def test_substyles_render():
    for sub in ("pine", "dead"):
        s = build_set(PAL, "entropy", sub, 2)
        assert len(s) == 2
