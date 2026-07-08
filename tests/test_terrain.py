"""Tests for the heightmap -> grid mesh core (terrain-first)."""
import numpy as np

from automap.terrain import build_grid_mesh


def test_dimensions_centering_extent():
    verts, faces, uvs = build_grid_mesh(np.zeros((3, 4)), pixel_size=2.0)
    assert verts.shape == (12, 3)
    assert uvs.shape == (12, 2)
    assert faces.shape[0] == 12                       # (2*3) quads * 2 tris
    assert abs(verts[:, 0].mean()) < 1e-4             # centered in X
    assert abs(verts[:, 2].mean()) < 1e-4             # centered in Z
    assert np.isclose(np.ptp(verts[:, 0]), 3 * 2.0)   # (W-1)*px
    assert np.isclose(np.ptp(verts[:, 2]), 2 * 2.0)   # (H-1)*px
    assert uvs.min() >= 0.0 and uvs.max() <= 1.0


def test_height_sits_on_ground():
    verts, _, _ = build_grid_mesh(np.array([[10.0, 11.0], [12.0, 13.0]]), pixel_size=1.0)
    assert np.isclose(verts[:, 1].min(), 0.0)         # base (min) subtracted
    assert np.isclose(verts[:, 1].max(), 3.0)         # 13 - 10


def test_nodata_quads_dropped():
    mask = np.ones((3, 3), dtype=bool)
    mask[0, 0] = False
    _, faces, _ = build_grid_mesh(np.zeros((3, 3)), pixel_size=1.0, valid_mask=mask)
    assert faces.shape[0] == 6                         # 4 quads - 1 touching nodata = 3 -> 6 tris


def test_winding_faces_up():
    # a ramp; every face normal must point +Y (guards the winding flip regression)
    verts, faces, _ = build_grid_mesh(np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]]), pixel_size=1.0)
    n = np.cross(verts[faces[:, 1]] - verts[faces[:, 0]],
                 verts[faces[:, 2]] - verts[faces[:, 0]])
    assert np.all(n[:, 1] > 0)


def test_z_exaggeration():
    h = np.array([[0.0, 0.0], [4.0, 4.0]])
    verts, _, _ = build_grid_mesh(h, pixel_size=1.0, z_exaggeration=2.0)
    assert np.isclose(verts[:, 1].max(), 8.0)          # 4 * 2.0


def _coastal_world():
    """Left half sea (hallucinated high + noisy), right half land at 5-8 m."""
    H, W = 30, 40
    h = np.full((H, W), 6.0)
    h[:, 20:] += 2.0                                  # land plateau
    rng = np.random.default_rng(2)
    h[:, :20] = 12.0 + rng.uniform(-8, 8, (H, 20))    # sea smear above AND below land
    water_like = np.zeros((H, W), bool)
    water_like[:, :20] = True
    valid = np.ones((H, W), bool)
    return h, valid, water_like


def test_flatten_sea_clamps_to_point_level():
    from automap.terrain import flatten_sea
    h, valid, water = _coastal_world()
    rows, cols = np.mgrid[5:25, 2:18]                 # points on the sea
    rc = np.column_stack([rows.ravel(), cols.ravel()])
    elev = np.full(len(rc), 1.0)                      # true sea level 1 m
    h2, sea, level = flatten_sea(h, valid, water, points_rc=rc, points_elev=elev)
    assert level == 1.0
    assert sea[:, :20].all() and not sea[:, 20:].any()
    assert np.allclose(h2[sea], 1.0 - 0.2)
    assert (h2[:, 20:] == h[:, 20:]).all()            # land untouched


def test_flatten_sea_percentile_fallback_and_no_sea():
    from automap.terrain import flatten_sea
    h, valid, water = _coastal_world()
    h2, sea, level = flatten_sea(h, valid, water)     # no points -> p5 of sea heights
    assert sea.any() and level < 8.0
    h3, sea3, level3 = flatten_sea(h, valid, np.zeros_like(water))
    assert level3 is None and not sea3.any() and (h3 == h).all()


def test_flatten_sea_raises_land_pits():
    from automap.terrain import flatten_sea
    h, valid, water = _coastal_world()
    h[10, 30] = -6.0                                  # melt pit below sea level
    rows, cols = np.mgrid[5:25, 2:18]
    rc = np.column_stack([rows.ravel(), cols.ravel()])
    h2, sea, level = flatten_sea(h, valid, water,
                                 points_rc=rc, points_elev=np.full(len(rc), 1.0))
    assert h2[10, 30] == 1.0 + 0.2                    # raised just above the sea
    assert h2[5, 30] == h[5, 30]                      # normal land untouched


def test_flatten_sea_ignores_interior_water():
    from automap.terrain import flatten_sea
    h = np.full((20, 20), 5.0)
    water = np.zeros((20, 20), bool)
    water[8:12, 8:12] = True                          # a blue pool/roof, not the sea
    h2, sea, level = flatten_sea(h, np.ones((20, 20), bool), water)
    assert level is None and not sea.any()
