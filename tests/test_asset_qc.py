"""Asset QC harness: each check catches its defect; real trees pass clean."""
import json
from pathlib import Path

import numpy as np

from automap import asset_qc
from automap.asset_creator import FAMILIES
from automap.pixelart import master_palette
from automap.trees_px import build_set

IDENTITY = json.loads(Path("identities/entropy.json").read_text())
PAL = master_palette(IDENTITY)
DESC = FAMILIES["tree"]["descriptor"]


def test_real_tree_set_passes_qc():
    built = build_set(PAL, "entropy", "deciduous", 3)
    report = asset_qc.qc_set(built, PAL, DESC)
    assert report["ok"], asset_qc.format_report(report)


def test_light_direction_catches_bottom_lit():
    img, meta = list(build_set(PAL, "entropy", "deciduous", 1).values())[0]
    arr = np.asarray(img).copy()
    flipped = arr[::-1].copy()  # light now comes from the bottom
    c = asset_qc.check_light_direction(flipped, PAL)
    assert not c.ok


def test_footprint_checks_catch_canopy_blocking():
    img, meta = list(build_set(PAL, "entropy", "deciduous", 1).values())[0]
    arr = np.asarray(img)
    bad = dict(meta, footprint={"center": [img.width / 2, img.height * 0.3],
                                 "r": 30})  # a canopy-sized blocker up high
    c = asset_qc.check_blocking_footprint(arr, bad, DESC)
    assert not c.ok
    missing = dict(meta)
    missing.pop("footprint", None)
    assert not asset_qc.check_blocking_footprint(arr, missing, DESC).ok


def test_alpha_and_palette_catch_violations():
    img, meta = list(build_set(PAL, "entropy", "pine", 1).values())[0]
    arr = np.asarray(img).copy()
    arr[0, 0] = [255, 0, 255, 128]  # translucent off-palette pixel
    assert not asset_qc.check_crisp_alpha(arr).ok
    arr[0, 0, 3] = 255
    assert not asset_qc.check_palette(arr, PAL).ok


def test_rect_footprint_pass_and_fail():
    """Rect footprints (buildings): correct rect passes; wider-than-mass
    fails; footprints without `kind` still take the circle path."""
    import numpy as np
    arr = np.zeros((64, 64, 4), np.uint8)
    arr[20:60, 8:56] = [180, 170, 150, 255]        # a building-ish mass
    desc = {"blocking": "facade_base"}
    good = {"footprint": {"kind": "rect", "center": [32, 40], "half": [24, 20]}}
    assert asset_qc.check_blocking_footprint(arr, good, desc).ok
    wide = {"footprint": {"kind": "rect", "center": [32, 40], "half": [31, 20]}}
    assert not asset_qc.check_blocking_footprint(arr, wide, desc).ok
    floaty = {"footprint": {"kind": "rect", "center": [32, 20], "half": [24, 10]}}
    assert not asset_qc.check_blocking_footprint(arr, floaty, desc).ok
    narrow = {"footprint": {"kind": "rect", "center": [32, 40], "half": [8, 20]}}
    assert not asset_qc.check_blocking_footprint(arr, narrow, desc).ok
    # circle path untouched
    circ = {"footprint": {"center": [32, 59], "r": 20}}
    assert asset_qc.check_blocking_footprint(arr, circ, {"blocking": "base"}).ok
