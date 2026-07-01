"""Feature detection for the semantic layer. First type: trees.

Classical, no-ML first pass (a DeepForest backend can slot in later behind the
same Tree output): a pixel is tree canopy when it is both TALL (canopy height
model = DSM - DTM, above a threshold) and GREEN (excess-green vegetation index).
Local maxima of the canopy height within that mask become individual trees, so
dense woods yield many trees rather than one giant blob.

Coordinates are a metric frame centered on the raster (x = east, z = south),
matching automap.terrain / the terrain glb, so detections drop straight onto it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass
class Tree:
    x: float
    z: float
    height: float
    radius: float

    def as_feature(self) -> dict:
        return {
            "type": "tree",
            "x": round(self.x, 3), "z": round(self.z, 3),
            "height": round(self.height, 2), "radius": round(self.radius, 2),
        }


def excess_green(rgb: np.ndarray) -> np.ndarray:
    """Normalized excess-green index (2G-R-B)/(R+G+B) on an HxWx3 array."""
    r, g, b = (rgb[..., i].astype(np.float64) for i in range(3))
    return (2 * g - r - b) / (r + g + b + 1e-6)


def detect_trees(
    chm: np.ndarray,
    rgb: np.ndarray,
    *,
    pixel_size: float,
    valid: np.ndarray | None = None,
    min_height: float = 2.0,
    exg_threshold: float = 0.05,
    min_spacing_m: float = 3.0,
) -> list[Tree]:
    """Detect trees from a canopy-height model + RGB orthophoto (same grid)."""
    H, W = chm.shape
    if valid is None:
        valid = np.isfinite(chm)
    chm0 = np.nan_to_num(chm, nan=-1e9)
    mask = valid & (chm0 >= min_height) & (excess_green(rgb) >= exg_threshold)
    if not mask.any():
        return []

    window = max(int(round(min_spacing_m / pixel_size)), 3)
    chm_m = np.where(mask, chm0, -1e9)
    peaks = mask & (chm_m >= ndimage.maximum_filter(chm_m, size=window, mode="nearest") - 1e-6)

    labels, n = ndimage.label(peaks)
    if n == 0:
        return []
    idx = np.arange(1, n + 1)
    cents = ndimage.center_of_mass(np.ones_like(labels, dtype=float), labels, idx)
    heights = ndimage.maximum(chm0, labels, idx)

    r = min_spacing_m / 2.0
    trees: list[Tree] = []
    for (cr, cc), h in zip(cents, heights):
        x = (cc - (W - 1) / 2.0) * pixel_size
        z = (cr - (H - 1) / 2.0) * pixel_size
        trees.append(Tree(x=float(x), z=float(z), height=float(h), radius=r))
    return trees
