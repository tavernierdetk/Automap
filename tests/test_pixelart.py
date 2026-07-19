"""Pixel-art toolkit: the craft disciplines as tests — one master palette,
crisp alpha, deliberate silhouettes, distinctness metric."""
import numpy as np

from automap.pixelart import (
    dilate, erode, largest_component, master_palette, outer_ring,
    palette_colors, ramp, resolve, rim_depth, silhouette_iou, tidy,
)

IDENTITY = {"name": "t", "canopy_color": (0.22, 0.42, 0.2),
            "trunk_color": (0.34, 0.26, 0.18), "cliff_color": (0.47, 0.45, 0.43),
            "water_color": (0.16, 0.36, 0.44), "path_color": (0.56, 0.45, 0.31)}


def test_master_palette_is_bounded_and_deterministic():
    a, b = master_palette(IDENTITY), master_palette(IDENTITY)
    assert a == b
    colors = palette_colors(a)
    assert 20 <= len(colors) <= 40  # ~34: shared, finite, project-wide


def test_ramp_hue_shifts_shadows_cool_highlights_warm():
    import colorsys
    r = ramp((0.22, 0.42, 0.2))  # green base
    hues = [colorsys.rgb_to_hsv(*(c / 255.0 for c in col))[0] * 360 for col in r]
    assert hues[0] > hues[2] > hues[4]  # darkest coolest, lightest warmest
    vals = [colorsys.rgb_to_hsv(*(c / 255.0 for c in col))[2] for col in r]
    assert vals == sorted(vals)  # monotonically brighter


def test_resolve_uses_only_palette_colors_and_crisp_alpha():
    pal = master_palette(IDENTITY)
    material = np.zeros((10, 10), np.uint8)
    material[2:8, 2:8] = 1
    band = np.full((10, 10), 2, np.uint8)
    img = resolve(material, band, pal, {1: "foliage"})
    arr = np.asarray(img)
    assert set(np.unique(arr[:, :, 3])) <= {0, 255}
    opaque = arr[arr[:, :, 3] == 255][:, :3]
    allowed = palette_colors(pal)
    assert {tuple(c) for c in opaque} <= allowed


def test_morphology_and_components():
    m = np.zeros((12, 12), bool)
    m[3:9, 3:9] = True
    m[0, 0] = True  # speck
    t = tidy(m)
    assert not t[0, 0] and t[5, 5]
    m2 = np.zeros((12, 12), bool)
    m2[2:5, 2:5] = True
    m2[8:11, 8:11] = True
    keep = largest_component(m2)
    assert keep.sum() == 9 and keep[3, 3]
    ring = outer_ring(t)
    assert ring.any() and not (ring & t).any()


def test_rim_depth_faces_the_right_way():
    m = np.zeros((10, 10), bool)
    m[2:8, 2:8] = True
    br = rim_depth(m, -1, -1, 2)  # bottom-right rim
    assert br[7, 7] and not br[2, 2]


def test_silhouette_iou_separates_shapes():
    a = np.zeros((40, 40), bool); a[5:35, 10:30] = True           # tall box
    b = np.zeros((40, 40), bool); b[10:30, 5:35] = True           # wide box
    c = a.copy()
    assert silhouette_iou(a, c) > 0.95
    assert silhouette_iou(a, b) < 0.85


def test_master_palette_custom_materials():
    """visual-identity 2.4: identity `materials` appends extra named ramps."""
    from automap.pixelart import master_palette, palette_colors
    ident = {"name": "v", "canopy_color": (0.3, 0.5, 0.3),
             "materials": {"bronze": [0.45, 0.30, 0.12],
                           "verdigris": {"color": [0.30, 0.55, 0.45],
                                         "hue_span": 0.3}}}
    pal = master_palette(ident)
    assert "bronze" in pal["materials"] and "verdigris" in pal["materials"]
    assert len(pal["materials"]["bronze"]["ramp"]) == 5
    # extras are ordinary palette members: bounded, deterministic, usable
    assert master_palette(ident) == pal
    n_builtin = len(master_palette({"name": "v"})["materials"])
    assert len(pal["materials"]) == n_builtin + 2
    assert len(palette_colors(pal)) > len(palette_colors(master_palette({"name": "v"})))


def test_with_extra_materials_extends_without_mutating():
    """A family (item icons) can repixel against master + its own accent ramps;
    the base palette is copied, not mutated."""
    from automap.pixelart import master_palette, with_extra_materials
    base = master_palette({"name": "v"})
    n0 = len(base["materials"])
    ext = with_extra_materials(base, {"potion_red": {"color": [0.82, 0.16, 0.18]},
                                      "gold": [0.87, 0.68, 0.22]})
    assert len(base["materials"]) == n0                 # original untouched
    assert "potion_red" in ext["materials"] and "gold" in ext["materials"]
    assert len(ext["materials"]["potion_red"]["ramp"]) == 5
    assert len(ext["materials"]) == n0 + 2


def test_ground_shadow_follows_the_silhouette():
    """The shadow agrees with its caster: wide table -> wide low shadow,
    narrow post -> narrow shadow; anchored at the foot line."""
    import numpy as np
    from automap.pixelart import ground_shadow
    h, w = 64, 64
    table = np.zeros((h, w), bool)
    table[30:40, 8:56] = True          # a wide table top
    table[38:56, 12:16] = True         # legs
    table[38:56, 48:52] = True
    sh = ground_shadow(table, 55)
    ys, xs = np.nonzero(sh)
    assert xs.max() - xs.min() >= 40    # table-wide, not a blob
    assert ys.min() >= 46               # squashed low near the foot line
    post = np.zeros((h, w), bool)
    post[10:56, 30:34] = True
    shp = ground_shadow(post, 55)
    _, xsp = np.nonzero(shp)
    assert xsp.max() - xsp.min() <= 8   # narrow caster, narrow shadow
    assert not (sh & table).any()       # never over the subject itself
