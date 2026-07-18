"""Tile-atlas generator: determinism, identity-driven color, mechanics flags."""
import json

from automap.tiles2d import CLASSES, TILE, VARIANTS, build_atlas, write_atlas

IDENTITY = {"name": "t", "grass_color": (0.3, 0.6, 0.2), "path_color": (0.6, 0.5, 0.3),
            "water_color": (0.1, 0.3, 0.5), "cliff_color": (0.5, 0.5, 0.5),
            "canopy_color": (0.2, 0.4, 0.2)}


def test_atlas_shape_and_determinism():
    a, _ = build_atlas(IDENTITY)
    b, _ = build_atlas(IDENTITY)
    from automap.tiles2d import TRANSITIONS
    assert a.size == (TILE * VARIANTS, TILE * (len(CLASSES) + 4 * len(TRANSITIONS)))
    assert a.tobytes() == b.tobytes()  # byte-identical re-runs


def test_identity_drives_tile_color():
    img, meta = build_atlas(IDENTITY)
    import numpy as np
    arr = np.asarray(img, dtype=float) / 255.0
    row = meta["classes"]["water"]["row"]
    tile = arr[row * TILE:(row + 1) * TILE, :TILE]
    mean = tile.mean(axis=(0, 1))
    assert mean[2] > mean[0]  # water reads blue, not gray


def test_mechanics_defaults_and_override():
    _, meta = build_atlas(IDENTITY)
    assert meta["classes"]["grass"]["walkable"] is True
    assert meta["classes"]["water"]["walkable"] is False
    assert meta["classes"]["water"]["hazard"] is True
    assert meta["classes"]["path"]["speed_mod"] > 1.0
    _, swimming = build_atlas(IDENTITY, mechanics={"water": {"walkable": True}})
    assert swimming["classes"]["water"]["walkable"] is True


def test_write_atlas_emits_pair(tmp_path):
    meta = write_atlas(tmp_path / "terr", IDENTITY)
    assert (tmp_path / "terr.png").exists()
    doc = json.loads((tmp_path / "terr.tiles.json").read_text())
    assert doc["atlas"] == "terr.png" and set(doc["classes"]) == set(CLASSES)


def test_transition_sets_render_both_terrains():
    import numpy as np
    from automap.tiles2d import TRANSITIONS
    img, meta = build_atlas(IDENTITY)
    assert set(meta["transitions"]) == set(TRANSITIONS)
    arr = np.asarray(img, dtype=float) / 255.0
    t = meta["transitions"]["path"]
    # mask 0b0001 (TL only): the tile must contain path pixels in the TL
    # quadrant and grass pixels in the BR quadrant
    row, col = t["start_row"] + 1 // 4, 1 % 4
    tile = arr[row * TILE:(row + 1) * TILE, col * TILE:(col + 1) * TILE]
    tl = tile[:8, :8].mean(axis=(0, 1))
    br = tile[-8:, -8:].mean(axis=(0, 1))
    assert abs(tl[0] - br[0]) + abs(tl[1] - br[1]) > 0.1  # two different terrains
    # mask 15 = fully overlay
    row15, col15 = t["start_row"] + 15 // 4, 15 % 4
    full = arr[row15 * TILE:(row15 + 1) * TILE, col15 * TILE:(col15 + 1) * TILE]
    assert abs(full[:8, :8].mean() - full[-8:, -8:].mean()) < 0.12


def test_atlas_grows_by_transition_rows():
    from automap.tiles2d import CLASSES, TRANSITIONS
    img, _ = build_atlas(IDENTITY)
    assert img.size[1] == TILE * (len(CLASSES) + 4 * len(TRANSITIONS))


# ---- atlas specs: the director's terrain vocabulary (correction plan S2)

MINE_SPEC = {
    "classes": [
        {"name": "earth", "painter": "earth", "color": [0.33, 0.27, 0.21],
         "walkable": True, "speed_mod": 1.0, "hazard": False},
        {"name": "wall", "painter": "rock", "color": [0.3, 0.3, 0.33],
         "relief": "raised", "walkable": False},
        {"name": "water", "painter": "water", "color": [0.08, 0.2, 0.18],
         "walkable": False, "hazard": True},
        {"name": "moss", "painter": "moss", "color": [0.2, 0.33, 0.16],
         "speed_mod": 0.9},
        {"name": "rail_v", "painter": "rail", "color": [0.4, 0.26, 0.13],
         "on": "earth", "args": {"orientation": "v"}},
    ],
    "transitions": [
        {"name": "wall", "base": "earth", "overlay": "wall"},
        {"name": "water", "base": "earth", "overlay": "water"},
    ],
}


def test_spec_defines_the_vocabulary():
    img, meta = build_atlas(IDENTITY, spec=MINE_SPEC)
    assert set(meta["classes"]) == {"earth", "wall", "water", "moss", "rail_v"}
    assert img.size == (TILE * VARIANTS, TILE * (5 + 4 * 2))
    # flags come from the spec, with defaults for what it omits
    assert meta["classes"]["moss"]["walkable"] is True
    assert meta["classes"]["moss"]["speed_mod"] == 0.9
    assert meta["classes"]["water"]["hazard"] is True
    a, _ = build_atlas(IDENTITY, spec=MINE_SPEC)
    assert a.tobytes() == img.tobytes()  # spec atlases are deterministic too


def test_spec_literal_colors_ignore_identity_terrain():
    """An underground atlas owes nothing to the surface identity fields."""
    import numpy as np
    img, meta = build_atlas(IDENTITY, spec=MINE_SPEC)
    arr = np.asarray(img, dtype=float) / 255.0
    row = meta["classes"]["earth"]["row"]
    mean = arr[row * TILE:(row + 1) * TILE, :TILE].mean(axis=(0, 1))
    # earth reads brown (r > g > b), nothing like IDENTITY's green grass
    assert mean[0] > mean[1] > mean[2]


def test_transition_base_is_the_spec_floor():
    _, meta = build_atlas(IDENTITY, spec=MINE_SPEC)
    assert meta["transitions"]["water"]["base"] == "earth"
    assert meta["transitions"]["wall"]["overlay"] == "wall"


def test_rock_tiles_as_one_mass():
    """`rock` carries no per-tile lighting — a wall is a mass, not bricks.

    `stone` (the free-standing blocker) keeps its lit-top/dark-bottom read;
    rock rows must NOT band at tile seams.
    """
    import numpy as np
    img, meta = build_atlas(IDENTITY, spec=MINE_SPEC)
    arr = np.asarray(img, dtype=float) / 255.0
    row = meta["classes"]["wall"]["row"]
    tile = arr[row * TILE:(row + 1) * TILE, :TILE]
    top, mid, bottom = tile[:2].mean(), tile[14:18].mean(), tile[-2:].mean()
    assert abs(top - mid) < 0.05 and abs(bottom - mid) < 0.05
    # the surface `stone` blocker still self-shades (legacy look preserved)
    img_d, meta_d = build_atlas(IDENTITY)
    arr_d = np.asarray(img_d, dtype=float) / 255.0
    srow = meta_d["classes"]["stone"]["row"]
    stile = arr_d[srow * TILE:(srow + 1) * TILE, :TILE]
    assert stile[:2].mean() > stile[14:18].mean() > stile[-2:].mean()


def test_raised_transition_grows_a_footing_shadow():
    """Where a raised mass meets the floor, the floor darkens (footing)."""
    import numpy as np
    img, meta = build_atlas(IDENTITY, spec=MINE_SPEC)
    arr = np.asarray(img, dtype=float) / 255.0
    erow = meta["classes"]["earth"]["row"]
    earth_mean = arr[erow * TILE:(erow + 1) * TILE, :TILE].mean()

    def base_side_mean(pair):  # mask 3 = top half overlay, bottom half base
        t = meta["transitions"][pair]
        row, col = t["start_row"] + 3 // 4, 3 % 4
        tile = arr[row * TILE:(row + 1) * TILE, col * TILE:(col + 1) * TILE]
        return tile[17:23, :].mean()  # floor rows hugging the contour

    # wall (raised) shades the floor beneath it; water (flat) does not
    assert base_side_mean("wall") < earth_mean * 0.93
    assert base_side_mean("water") > earth_mean * 0.9


def test_animated_water_packs_phase_frames():
    """A class with animation frames widens its row: variant v's frames sit
    at columns v*frames..v*frames+frames-1 (Godot's tile-animation layout).
    Frame 0 is byte-identical to the static tile; later frames drift the
    swell phase, never the tile."""
    import numpy as np
    import copy
    spec = copy.deepcopy(MINE_SPEC)
    water = next(c for c in spec["classes"] if c["name"] == "water")
    water["animation"] = {"frames": 3}
    img, meta = build_atlas(IDENTITY, spec=spec)
    assert img.size[0] == TILE * VARIANTS * 3
    assert meta["classes"]["water"]["frames"] == 3
    assert meta["schema"] == "tiles/1.2"
    assert "frames" not in meta["classes"]["earth"]  # static classes opt out
    arr = np.asarray(img)
    row = meta["classes"]["water"]["row"]
    static, _ = build_atlas(IDENTITY, spec=MINE_SPEC)
    sarr = np.asarray(static)

    def tile(a, col):
        return a[row * TILE:(row + 1) * TILE, col * TILE:(col + 1) * TILE]

    for v in range(VARIANTS):
        assert np.array_equal(tile(arr, v * 3), tile(sarr, v))  # frame 0
        assert not np.array_equal(tile(arr, v * 3), tile(arr, v * 3 + 1))


def test_rail_overlays_its_underlay():
    """Rails read as two lines over earth; tiles connect along the run."""
    import numpy as np
    img, meta = build_atlas(IDENTITY, spec=MINE_SPEC)
    arr = np.asarray(img, dtype=float) / 255.0
    row = meta["classes"]["rail_v"]["row"]
    tile = arr[row * TILE:(row + 1) * TILE, :TILE]
    # the lit rail heads run full height at fixed columns → same x in every
    # variant, so vertical neighbors connect
    col_brightness = tile.mean(axis=(0, 2))
    rails = sorted(col_brightness.argsort()[-2:])
    assert rails == [10, 22]
    earth_row = meta["classes"]["earth"]["row"]
    earth = arr[earth_row * TILE:(earth_row + 1) * TILE, :TILE]
    # between the rails the underlay shows through (earth-ish, not rail metal)
    assert abs(tile[:, 14:18].mean() - earth[:, 14:18].mean()) < 0.08


def test_blocking_ledge_transition():
    """Elevation v1: a `blocks: true` pair rides tiles.json so the baker
    walls the terrace boundary; stairs is a first-class painter."""
    import copy
    spec = copy.deepcopy(MINE_SPEC)
    spec["classes"].append({"name": "terrace", "painter": "flagstone",
                            "color": [0.6, 0.6, 0.55], "relief": "ledge",
                            "walkable": True})
    spec["classes"].append({"name": "stairs", "painter": "stairs",
                            "color": [0.6, 0.58, 0.5], "walkable": True})
    spec["transitions"].append({"name": "terrace", "base": "earth",
                                "overlay": "terrace", "blocks": True})
    img, meta = build_atlas(IDENTITY, spec=spec)
    assert meta["transitions"]["terrace"]["blocks"] is True
    assert "blocks" not in meta["transitions"]["water"]  # only when asked
    assert meta["classes"]["stairs"]["walkable"] is True
