"""Animation frames: index-space sway, locked silhouette, packed atlas."""
import json

import numpy as np
from PIL import Image

from automap import animate_px, asset_creator, asset_qc, pixelart, trees_px

IDENTITY = {"name": "t", "canopy_color": (0.22, 0.42, 0.2),
            "trunk_color": (0.34, 0.26, 0.18), "cliff_color": (0.47, 0.45, 0.43),
            "water_color": (0.16, 0.36, 0.44), "path_color": (0.56, 0.45, 0.31)}
ANIM = asset_creator.FAMILIES["tree"]["animation"]


def _tree(substyle="deciduous"):
    pal = pixelart.master_palette(IDENTITY)
    img, meta = trees_px.build_variant(pal, substyle, "t:anim:seed", "medium")
    return pal, img, meta


def test_sway_locks_silhouette_and_palette_and_moves_leaves():
    pal, img, meta = _tree()
    material, band, names = meta["maps"]
    frames = animate_px.sway_frames(material, band, names, pal,
                                    ANIM["mutable"], img, 2, "k")
    assert len(frames) == 1
    checks = asset_qc.qc_frames(np.asarray(img), [np.asarray(f) for f in frames], pal)
    bad = [f"{c.name} ({c.detail})" for c in checks if not c.ok]
    assert not bad, bad


def test_sway_is_deterministic():
    pal, img, meta = _tree()
    material, band, names = meta["maps"]
    a = animate_px.sway_frames(material, band, names, pal, ANIM["mutable"], img, 2, "k")
    b = animate_px.sway_frames(material, band, names, pal, ANIM["mutable"], img, 2, "k")
    assert np.array_equal(np.asarray(a[0]), np.asarray(b[0]))


def test_dead_trees_do_not_animate():
    pal, img, meta = _tree("dead")
    material, band, names = meta["maps"]
    frames = animate_px.sway_frames(material, band, names, pal,
                                    ANIM["mutable"], img, 2, "k")
    assert frames == []          # no mutable pixels -> static, frames stays 1


def test_ensure_stages_frame_files_and_catalog_count(tmp_path):
    game = tmp_path / "game"
    (game / "content" / "props").mkdir(parents=True)
    asset_creator.ensure(game, tmp_path / "staging", IDENTITY,
                         "tree", "deciduous", 2, log=lambda m: None)
    cat = json.loads((tmp_path / "staging" / "props.json").read_text())
    for name, e in cat["props"].items():
        assert e["frames"] >= 1
        if e["frames"] > 1:
            assert (tmp_path / "staging" / f"{name}.f1.png").exists()
    assert any(e["frames"] > 1 for e in cat["props"].values())


def test_atlas_packs_frames_side_by_side(tmp_path):
    game = tmp_path / "game"
    (game / "content" / "props").mkdir(parents=True)
    asset_creator.ensure(game, tmp_path / "staging", IDENTITY,
                         "tree", "deciduous", 1, log=lambda m: None)
    cat = json.loads((tmp_path / "staging" / "props.json").read_text())
    atlas, meta = asset_creator.pack_prop_atlas(tmp_path / "staging", cat, "tree")
    assert meta["schema"] == "props-tileset/2.0" and meta["family"] == "tree"
    t = meta["tiles"]["deciduous_0"]
    assert t["frames"] == 2
    cx, cy = t["cell"]
    cw, ch = t["size_cells"]
    a = np.asarray(atlas)
    base = a[cy * 32:(cy + ch) * 32, cx * 32:(cx + cw) * 32]
    f1 = a[cy * 32:(cy + ch) * 32, (cx + cw) * 32:(cx + 2 * cw) * 32]
    assert (f1[:, :, 3] > 0).any()                        # frame drawn
    assert np.array_equal(base[:, :, 3], f1[:, :, 3])     # same silhouette
    assert (base[:, :, :3] != f1[:, :, :3]).any()         # but it moves
