"""Tests for tree and building detection (semantic layer)."""
import numpy as np

from automap.features import (
    detect_buildings,
    detect_trees,
    excess_green,
    green_over_blue,
    slope_degrees,
)


def _two_bumps(H=60, W=60, peak=8.0, sigma=4.0, centers=((15, 15), (40, 45))):
    yy, xx = np.mgrid[0:H, 0:W]
    chm = np.zeros((H, W))
    for cy, cx in centers:
        chm += peak * np.exp(-(((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * sigma ** 2)))
    return chm


def _green(H, W):
    rgb = np.zeros((H, W, 3), np.uint8)
    rgb[..., 0], rgb[..., 1], rgb[..., 2] = 40, 200, 40
    return rgb


def test_excess_green():
    green = np.array([[[40, 200, 40]]], np.uint8)
    gray = np.array([[[128, 128, 128]]], np.uint8)
    assert excess_green(green)[0, 0] > 0.2
    assert abs(excess_green(gray)[0, 0]) < 0.05


def test_detect_finds_bumps():
    chm = _two_bumps()
    trees = detect_trees(chm, _green(60, 60), pixel_size=1.0,
                         min_height=2.0, exg_threshold=0.05, min_spacing_m=5.0)
    assert 2 <= len(trees) <= 4
    assert max(t.height for t in trees) > 6.0        # peak ~8 m


def test_detect_none_when_short():
    trees = detect_trees(np.full((30, 30), 0.5), _green(30, 30),
                         pixel_size=1.0, min_height=2.0)
    assert trees == []


def test_detect_none_when_not_green():
    chm = _two_bumps(40, 40, centers=((20, 20),))
    gray = np.full((40, 40, 3), 120, np.uint8)       # tall but not vegetation
    assert detect_trees(chm, gray, pixel_size=1.0, min_height=2.0, exg_threshold=0.1) == []


def test_detect_coords_centered():
    # single central bump -> tree near origin in the centered metric frame
    chm = _two_bumps(41, 41, centers=((20, 20),))
    trees = detect_trees(chm, _green(41, 41), pixel_size=2.0, min_height=2.0, min_spacing_m=6.0)
    assert trees
    t = min(trees, key=lambda t: t.x ** 2 + t.z ** 2)
    assert abs(t.x) < 2.0 and abs(t.z) < 2.0         # center pixel -> ~origin


def test_water_bump_rejected():
    # tall reconstruction noise over blue-green water: excess-green passes but
    # green-over-blue vetoes it
    chm = _two_bumps(40, 40, centers=((20, 20),))
    water = np.zeros((40, 40, 3), np.uint8)
    water[..., 0], water[..., 1], water[..., 2] = 60, 130, 160
    assert excess_green(water)[0, 0] >= 0.05         # would have passed before
    assert green_over_blue(water)[0, 0] < 0.02
    assert detect_trees(chm, water, pixel_size=1.0) == []


def test_steep_slope_rejected():
    # same green bump, but on a cliff face (DTM slope above the gate)
    chm = _two_bumps(40, 40, centers=((20, 20),))
    steep = np.full((40, 40), 45.0)
    assert detect_trees(chm, _green(40, 40), pixel_size=1.0, slope=steep) == []
    flat = np.zeros((40, 40))
    assert detect_trees(chm, _green(40, 40), pixel_size=1.0, slope=flat)


def test_too_tall_peak_is_junk():
    # a 60 m spike is reconstruction junk, and its flanks must not survive as
    # ring detections either
    chm = _two_bumps(60, 60, peak=60.0, centers=((30, 30),))
    assert detect_trees(chm, _green(60, 60), pixel_size=1.0, max_height=40.0) == []


def test_offset_plateau_rejected():
    # a broad DSM-DTM offset (grass on noisy ground) is tall and green but has
    # no prominent peak
    chm = np.full((60, 60), 3.0)
    assert detect_trees(chm, _green(60, 60), pixel_size=1.0) == []


def test_edge_melt_rejected():
    # same bump, but hugging a no-data region (reconstruction melt zone):
    # the edge margin distrusts it; far from the hole it survives
    chm = _two_bumps(40, 40, centers=((20, 12),))
    near = np.ones((40, 40), bool)
    near[:, :8] = False                              # no-data 4 px from the bump
    assert detect_trees(chm, _green(40, 40), pixel_size=1.0,
                        valid=near, edge_margin_m=6.0) == []
    assert detect_trees(chm, _green(40, 40), pixel_size=1.0,
                        valid=near, edge_margin_m=2.0)


def test_tiny_speck_rejected():
    # a single-pixel spike is below any believable crown area
    chm = np.zeros((40, 40))
    chm[20, 20] = 5.0
    assert detect_trees(chm, _green(40, 40), pixel_size=1.0) == []


def test_unsupported_bump_rejected():
    # a phantom DSM bump with no reconstruction points beneath it is melt;
    # the same bump with dense point support is a tree
    chm = _two_bumps(40, 40, centers=((20, 20),))
    rng = np.random.default_rng(7)
    far = rng.uniform(-20, -15, (200, 2))            # dense support elsewhere
    assert detect_trees(chm, _green(40, 40), pixel_size=1.0, support_xy=far) == []
    under = rng.uniform(-3, 3, (200, 2))             # dense support at the bump
    assert detect_trees(chm, _green(40, 40), pixel_size=1.0, support_xy=under)


def test_building_veto():
    # a supported bump whose neighbourhood is more building than vegetation is
    # a building candidate, not a tree
    chm = _two_bumps(40, 40, centers=((20, 20),))
    rng = np.random.default_rng(9)
    veg = rng.uniform(-7, 7, (300, 2))
    bld = rng.uniform(-7, 7, (900, 2))
    assert detect_trees(chm, _green(40, 40), pixel_size=1.0,
                        support_xy=veg, veto_xy=bld) == []
    assert detect_trees(chm, _green(40, 40), pixel_size=1.0,
                        support_xy=veg, veto_xy=bld[:100])


def test_radius_tracks_crown_size():
    big = _two_bumps(80, 80, sigma=6.0, centers=((40, 20),))
    small = _two_bumps(80, 80, sigma=2.5, centers=((40, 60),))
    trees = detect_trees(big + small, _green(80, 80), pixel_size=1.0, min_spacing_m=5.0)
    assert len(trees) == 2
    left = min(trees, key=lambda t: t.x)
    right = max(trees, key=lambda t: t.x)
    assert left.radius > right.radius + 1.0


def test_slope_degrees():
    # a 1:1 ramp is 45 degrees everywhere
    dem = np.tile(np.arange(50, dtype=float), (50, 1))
    s = slope_degrees(dem, pixel_size=1.0)
    assert abs(s[25, 25] - 45.0) < 1.0
    assert slope_degrees(np.zeros((20, 20)), pixel_size=1.0).max() < 1e-9


# --- buildings ---------------------------------------------------------------

def _roof_points(w=20, d=10, hag=4.0, gable=False, x0=0.0, z0=0.0):
    """Building-classified points over a w x d m roof, ~1 pt/m^2, (x, z, hag)."""
    xx, zz = np.meshgrid(np.arange(w) + 0.5, np.arange(d) + 0.5)
    x, z = xx.ravel() + x0, zz.ravel() + z0
    h = np.full(len(x), float(hag))
    if gable:
        # eaves at hag, ridge line along the long (x) axis at hag + 3
        h = hag + 3.0 * (1.0 - np.abs(zz.ravel() - d / 2.0) / (d / 2.0))
    return np.column_stack([x, z, h])


def _poly_area(footprint):
    c = np.asarray(footprint)
    x, z = c[:, 0], c[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(z, 1)) - np.dot(z, np.roll(x, 1)))


def test_building_box_detected():
    blds = detect_buildings(_roof_points())
    assert len(blds) == 1
    b = blds[0]
    assert 3.0 <= b.height <= 4.5
    assert b.roof == "flat"
    assert 150 <= _poly_area(b.footprint) <= 300    # ~200 m^2 + padding
    f = b.as_feature()
    assert f["type"] == "building" and len(f["footprint"]) == 4


def test_building_gable_roof():
    b = detect_buildings(_roof_points(gable=True))[0]
    assert b.roof == "gable"
    assert b.ridge > b.height + 1.0


def test_building_needs_classified_points():
    assert detect_buildings(None) == []
    assert detect_buildings(np.zeros((0, 3))) == []


def test_two_buildings_separate_clusters():
    pts = np.vstack([_roof_points(), _roof_points(x0=40.0, z0=30.0)])
    assert len(detect_buildings(pts)) == 2


def test_vegetation_cluster_is_not_a_building():
    pts = _roof_points()
    veg = np.vstack([pts[:, :2], pts[:, :2] + 0.1])  # veg outnumbers bld pts
    assert detect_buildings(pts, veg) == []


def test_low_cluster_rejected():
    assert detect_buildings(_roof_points(hag=0.8)) == []   # hedge, not a house


def test_streak_rejected():
    # a misclassified flight line over water: 60 m long, ~1 m wide
    x = np.linspace(0, 60, 120)
    pts = np.column_stack([x, 0.3 * np.sin(x), np.full(120, 5.0)])
    assert detect_buildings(pts) == []


def test_no_ground_context_rejected():
    # a cluster with no reconstructed ground nearby is debris over water
    pts = _roof_points()
    rng = np.random.default_rng(5)
    land_far = rng.uniform(200, 260, (500, 2))
    assert detect_buildings(pts, None, land_far) == []
    land_near = rng.uniform(-10, 30, (500, 2))
    assert detect_buildings(pts, None, land_near)


def test_cliff_cluster_rejected():
    pts = _roof_points()
    steep = np.full((100, 100), 45.0)
    flat = np.zeros((100, 100))
    assert detect_buildings(pts, slope=steep, pixel_size=1.0) == []
    assert detect_buildings(pts, slope=flat, pixel_size=1.0)


def test_building_too_small_rejected():
    assert detect_buildings(_roof_points(w=3, d=3)) == []  # 9 m^2 < min area


def test_blue_cluster_is_water():
    pts = _roof_points()
    sea = np.zeros((100, 100, 3), np.uint8)
    sea[..., 0], sea[..., 1], sea[..., 2] = 70, 100, 130   # blue-dominant
    assert detect_buildings(pts, rgb=sea, pixel_size=1.0) == []
    roof = np.full((100, 100, 3), 90, np.uint8)            # neutral gray
    assert detect_buildings(pts, rgb=roof, pixel_size=1.0)
