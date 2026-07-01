"""Heightmap -> grid mesh, the core of the terrain-first branch.

Pure numpy so it's unit-testable without rasterio/trimesh. Turns an elevation
array into a regular triangle grid (Y-up, metric, centered, sitting on the
ground), with per-vertex UVs that map straight onto the orthophoto, and quads
touching nodata cells dropped so the survey boundary is preserved.
"""
from __future__ import annotations

import numpy as np


def build_grid_mesh(
    height: np.ndarray,
    *,
    pixel_size: float,
    valid_mask: np.ndarray | None = None,
    z_exaggeration: float = 1.0,
):
    """Return (vertices, faces, uvs).

    height       : (H, W) elevation in metres.
    pixel_size   : metres between adjacent grid cells.
    valid_mask   : (H, W) bool; quads with any invalid corner are dropped.
    vertices     : (H*W, 3) float32, Y-up, centered on origin, min-Y = 0.
    faces        : (M, 3) int32, wound CCW so the surface faces +Y.
    uvs          : (H*W, 2) float32, (col, row) normalized for the orthophoto.
    """
    H, W = height.shape
    if valid_mask is None:
        valid_mask = np.ones((H, W), dtype=bool)

    xs = (np.arange(W) - (W - 1) / 2.0) * pixel_size       # east  -> +X
    zs = (np.arange(H) - (H - 1) / 2.0) * pixel_size       # south -> +Z
    xx, zz = np.meshgrid(xs, zs)

    h = np.where(valid_mask, height, np.nan)
    base = np.nanmin(h) if np.isfinite(h).any() else 0.0
    yy = np.where(valid_mask, (height - base) * z_exaggeration, 0.0)

    verts = np.stack([xx, yy, zz], axis=-1).reshape(-1, 3).astype(np.float32)

    u = np.arange(W) / max(W - 1, 1)
    v = np.arange(H) / max(H - 1, 1)
    uu, vv = np.meshgrid(u, v)
    uvs = np.stack([uu, 1.0 - vv], axis=-1).reshape(-1, 2).astype(np.float32)

    idx = np.arange(H * W).reshape(H, W)
    tl, tr = idx[:-1, :-1], idx[:-1, 1:]
    bl, br = idx[1:, :-1], idx[1:, 1:]
    quad_ok = (
        valid_mask[:-1, :-1] & valid_mask[:-1, 1:]
        & valid_mask[1:, :-1] & valid_mask[1:, 1:]
    )
    tl, tr, bl, br = tl[quad_ok], tr[quad_ok], bl[quad_ok], br[quad_ok]
    # Wound so the surface normal points up (+Y) for a Y-up viewer.
    tri1 = np.stack([tl, bl, tr], axis=-1)
    tri2 = np.stack([tr, bl, br], axis=-1)
    faces = np.concatenate([tri1, tri2], axis=0).astype(np.int32)

    return verts, faces, uvs
