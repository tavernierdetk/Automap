"""Heightmap -> grid mesh, the core of the terrain-first branch.

Pure numpy/scipy so it's unit-testable without rasterio/trimesh. Turns an
elevation array into a regular triangle grid (Y-up, metric, centered, sitting
on the ground), with per-vertex UVs that map straight onto the orthophoto, and
quads touching nodata cells dropped so the survey boundary is preserved.

flatten_sea handles coastal scans: open water is textureless, so ODM
hallucinates a lumpy sea "surface" that can sit meters ABOVE the real village
(measured on mountain_cross). Blue-dominant cells connected to the raster
border are sea; they get clamped to a flat sea level measured from the
reconstruction points that actually landed on the water.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage


def flatten_sea(
    height: np.ndarray,
    valid: np.ndarray,
    water_like: np.ndarray,
    *,
    points_rc: np.ndarray | None = None,
    points_elev: np.ndarray | None = None,
    sink: float = 0.2,
):
    """Clamp the hallucinated sea surface to a flat level.

    water_like is a bool grid of cells that look like open water (the caller
    composes it: blue-dominant ortho, or point-desert cells that aren't
    vegetation — sun glint reconstructs gray but triangulates nothing). Sea =
    valid water-like cells whose component touches the raster border (the
    open sea always reaches the edge; a blue roof or pool doesn't). Sea level
    is the median elevation of the reconstruction points inside that mask
    (points_rc = (N, 2) row/col grid indices, points_elev their elevations),
    falling back to the 5th percentile of the masked heights when point
    evidence is thin. Sea cells are set slightly below level (sink) so a
    water plane floated at the shoreline covers them.

    Returns (height', sea_mask, sea_level) — (height, all-False, None) when
    there is no sea in frame.
    """
    sea = valid & water_like
    if not sea.any():
        return height, np.zeros_like(valid), None
    labels, n = ndimage.label(sea)
    border = np.unique(np.concatenate(
        [labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    keep = np.isin(labels, border[border > 0])
    if not keep.any():
        return height, np.zeros_like(valid), None

    level = None
    if points_rc is not None and len(points_rc):
        rc = np.asarray(points_rc, int)
        inside = (
            (rc[:, 0] >= 0) & (rc[:, 0] < height.shape[0])
            & (rc[:, 1] >= 0) & (rc[:, 1] < height.shape[1]))
        rc = rc[inside]
        on_sea = keep[rc[:, 0], rc[:, 1]]
        if on_sea.sum() >= 50:
            level = float(np.median(np.asarray(points_elev)[inside][on_sea]))
    if level is None:
        level = float(np.percentile(height[keep], 5))

    out = height.copy()
    out[keep] = level - sink
    # nothing real is below the sea: valid land dipping under sea level is a
    # reconstruction pit — raise it just above so the sea flat is the true
    # terrain minimum and a shoreline water plane never floods inland
    land = valid & ~keep
    out[land] = np.maximum(out[land], level + sink)
    return out, keep, level


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
