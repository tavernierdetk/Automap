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
