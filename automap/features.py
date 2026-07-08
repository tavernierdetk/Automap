"""Feature detection for the semantic layer.

Types: trees and buildings are detected from the scan; roads and water are
carried in from OSM (automap.osm) and only defined here so features.json has
one home for its schema.

Classical, no-ML first pass (a DeepForest backend can slot in later behind the
same Tree output): a pixel is tree canopy when it is TALL (canopy height model
= DSM - DTM, above a threshold) and GREEN (excess-green vegetation index) and
GREENER THAN BLUE (vetoes water, which reconstructs as tall noise and can pass
excess-green). Local maxima of the canopy height within that mask become
individual trees, so dense woods yield many trees rather than one giant blob.

Candidate peaks then survive three geometric gates learned from the
mountain_cross coastal scene (see docs/explorations/semantic-layer-v2.md):

- edge margin: reconstruction melts near no-data holes and the coverage
  boundary; pixels within a few meters of invalid cells are distrusted.
- slope gate: the interpolated DTM undershoots on cliffs, so steep bare
  terrain reads as canopy; reject peaks where the ground slope is steep.
- prominence gate: broad DSM-DTM offset plateaus (grass on noisy ground) put
  the whole neighbourhood at 2-4 m; a real tree top stands well above the low
  surface nearby.
- area gate: each masked pixel is assigned to its nearest peak; specks too
  small to be a crown are dropped, and the assigned area gives the crown
  radius instead of a fixed constant.
- support gate: the DSM is interpolated wherever the reconstruction was too
  sparse to triangulate, and those melt zones grow tree-shaped phantom bumps;
  a real crown must be backed by enough actual points from the georeferenced
  cloud (pass their metric XZ coordinates as support_xy — vegetation-classified
  points when the cloud carries classification, all points otherwise).
- veto points: melt skirts around buildings are tall, green-bleeding and well
  supported; pass building-classified points as veto_xy and a crown whose
  neighbourhood is more building than vegetation is rejected (it is a building
  candidate, not a tree).

Buildings are detected point-first (detect_buildings): the DSM/DTM rasters
smooth small houses down to under the detection threshold (measured on
mountain_cross: half the building-classified points sit at raster-CHM < 2.7 m),
so instead we cluster the building-classified cloud points directly — they sit
on the actual roofs and carry the true surface height. Clusters are filtered
by shape (misclassified outlier flight lines over water are thin streaks; real
roofs fill their bounding rectangle), by their points' height above the DTM,
by ground slope (cliffs), and by vegetation-point majority (trees). The
footprint is the cluster's minimum-area rotated rectangle.

Coordinates are a metric frame centered on the raster (x = east, z = south),
matching automap.terrain / the terrain glb, so detections drop straight onto it.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree


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


@dataclass
class Building:
    footprint: list          # 4 ordered (x, z) corners, metric centered frame
    height: float            # wall height above ground (m)
    ridge: float             # ridge height above ground (m)
    roof: str                # "flat" | "gable"
    roof_color: tuple        # median ortho RGB, 0-255
    source: str = "scan"     # "scan" | "osm" | "scan+osm"

    def as_feature(self) -> dict:
        return {
            "type": "building",
            "footprint": [[round(float(x), 3), round(float(z), 3)] for x, z in self.footprint],
            "height": round(self.height, 2), "ridge": round(self.ridge, 2),
            "roof": self.roof,
            "roof_color": [int(c) for c in self.roof_color],
            "source": self.source,
        }


@dataclass
class Road:
    path: list               # ordered (x, z) polyline, metric centered frame
    width: float             # meters
    kind: str                # OSM highway class ("residential", "footway", ...)
    source: str = "osm"

    def as_feature(self) -> dict:
        return {
            "type": "road",
            "path": [[round(float(x), 3), round(float(z), 3)] for x, z in self.path],
            "width": round(self.width, 2), "kind": self.kind, "source": self.source,
        }


@dataclass
class Water:
    kind: str                # "sea" (level resolved against terrain at styling time)
    outline: list            # (x, z) samples anchoring the water level (coastline)
    source: str = "osm"

    def as_feature(self) -> dict:
        return {
            "type": "water", "kind": self.kind,
            "outline": [[round(float(x), 3), round(float(z), 3)] for x, z in self.outline],
            "source": self.source,
        }


def excess_green(rgb: np.ndarray) -> np.ndarray:
    """Normalized excess-green index (2G-R-B)/(R+G+B) on an HxWx3 array."""
    r, g, b = (rgb[..., i].astype(np.float64) for i in range(3))
    return (2 * g - r - b) / (r + g + b + 1e-6)


def green_over_blue(rgb: np.ndarray) -> np.ndarray:
    """Normalized (G-B)/(R+G+B). Vegetation is clearly positive; blue-green
    water hovers at or below zero even when excess-green passes."""
    r, g, b = (rgb[..., i].astype(np.float64) for i in range(3))
    return (g - b) / (r + g + b + 1e-6)


def slope_degrees(dem: np.ndarray, pixel_size: float) -> np.ndarray:
    """Terrain slope (degrees) of a DEM; nodata should be pre-filled/NaN-free."""
    gy, gx = np.gradient(dem, pixel_size)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def detect_trees(
    chm: np.ndarray,
    rgb: np.ndarray,
    *,
    pixel_size: float,
    valid: np.ndarray | None = None,
    slope: np.ndarray | None = None,
    min_height: float = 2.0,
    max_height: float = 40.0,
    exg_threshold: float = 0.05,
    gob_threshold: float = 0.02,
    max_slope_deg: float = 30.0,
    edge_margin_m: float = 3.0,
    min_spacing_m: float = 3.0,
    prominence_min: float = 2.0,
    prominence_radius_m: float = 12.0,
    min_area_m2: float = 3.0,
    max_radius_m: float = 8.0,
    support_xy: np.ndarray | None = None,
    veto_xy: np.ndarray | None = None,
    min_support_density: float = 1.0,
) -> list[Tree]:
    """Detect trees from a canopy-height model + RGB orthophoto (same grid).

    slope is the bare-ground (DTM) slope in degrees on the same grid; pass
    None to skip the slope gate (e.g. in tests on flat synthetic ground).
    support_xy / veto_xy are (N, 2) arrays of reconstruction points (x, z) in
    the same centered metric frame; pass None to skip those gates.
    """
    H, W = chm.shape
    if valid is None:
        valid = np.isfinite(chm)
    chm0 = np.nan_to_num(chm, nan=-1e9)

    # trusted = far enough from no-data that reconstruction melt is unlikely.
    # Applied per-peak (not per-pixel) so a melt-zone bump dies outright
    # instead of resurfacing as a ring of flank maxima just inside the margin.
    trusted = valid
    if edge_margin_m > 0:
        margin_px = int(round(edge_margin_m / pixel_size))
        if margin_px > 0:
            trusted = ~ndimage.maximum_filter(~valid, size=2 * margin_px + 1)

    mask = (
        valid
        & (chm0 >= min_height)
        & (excess_green(rgb) >= exg_threshold)
        & (green_over_blue(rgb) >= gob_threshold)
    )
    if slope is not None:
        mask &= slope <= max_slope_deg
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

    # prominence gate: a tree top stands above the low surface nearby; a broad
    # DSM-DTM offset plateau does not. Reference = low percentile of the valid
    # CHM within prominence_radius_m of the peak.
    prom_r = max(int(round(prominence_radius_m / pixel_size)), window)
    keep: list[tuple[float, float, float]] = []
    for (cr, cc), h in zip(cents, heights):
        if h > max_height:  # a whole peak this tall is reconstruction junk
            continue
        if not trusted[min(int(round(cr)), H - 1), min(int(round(cc)), W - 1)]:
            continue
        r0, r1 = max(int(cr) - prom_r, 0), min(int(cr) + prom_r + 1, H)
        c0, c1 = max(int(cc) - prom_r, 0), min(int(cc) + prom_r + 1, W)
        patch = chm0[r0:r1, c0:c1][valid[r0:r1, c0:c1]]
        if patch.size == 0:
            continue
        if h - np.percentile(patch, 10) < prominence_min:
            continue
        keep.append((cr, cc, float(h)))
    if not keep:
        return []

    # assign each masked pixel to its nearest surviving peak (within
    # max_radius_m); assigned area -> crown radius, and too-small crowns drop.
    peak_rc = np.array([(cr, cc) for cr, cc, _ in keep])
    mask_rc = np.argwhere(mask)
    dist, which = cKDTree(peak_rc).query(mask_rc, distance_upper_bound=max_radius_m / pixel_size)
    counts = np.bincount(which[np.isfinite(dist)], minlength=len(keep))
    cell_area = pixel_size * pixel_size

    support = cKDTree(support_xy) if support_xy is not None and len(support_xy) else None
    veto = cKDTree(veto_xy) if veto_xy is not None and len(veto_xy) else None

    trees: list[Tree] = []
    for (cr, cc, h), n_px in zip(keep, counts):
        area = n_px * cell_area
        if area < min_area_m2:
            continue
        radius = min(float(np.sqrt(area / np.pi)), max_radius_m)
        x = (cc - (W - 1) / 2.0) * pixel_size
        z = (cr - (H - 1) / 2.0) * pixel_size
        if support is not None:
            r_q = max(radius, 2.0)
            n_sup = len(support.query_ball_point([x, z], r_q))
            if n_sup / (np.pi * r_q * r_q) < min_support_density:
                continue
            if veto is not None and len(veto.query_ball_point([x, z], r_q)) > n_sup:
                continue
        trees.append(Tree(x=float(x), z=float(z), height=h, radius=radius))
    return trees


def detect_buildings(
    bld_xyh: np.ndarray | None,
    veg_xy: np.ndarray | None = None,
    ground_xy: np.ndarray | None = None,
    *,
    rgb: np.ndarray | None = None,
    slope: np.ndarray | None = None,
    pixel_size: float = 1.0,
    cell_m: float = 1.0,
    min_points: int = 25,
    min_height: float = 2.0,
    max_height: float = 25.0,
    min_area_m2: float = 12.0,
    max_area_m2: float = 1500.0,
    min_fill: float = 0.35,
    min_side_m: float = 2.5,
    max_slope_deg: float = 30.0,
    ground_context_radius_m: float = 15.0,
    min_ground_context: int = 20,
    max_blueness: float = 15.0,
    gable_delta: float = 1.0,
    footprint_pad_m: float = 0.3,
) -> list[Building]:
    """Detect buildings by clustering building-classified cloud points.

    bld_xyh is an (N, 3) array per building-classified point: x, z in the
    centered metric frame and height above the bare ground (point z - DTM).
    veg_xy / ground_xy are (M, 2) for vegetation- / ground-classified points.
    rgb / slope are optional rasters (ortho grid, pixel_size) for roof color
    and the cliff gate. Classification is the primary evidence: without
    points there is no detection. Two water guards: the ground-context gate
    rejects clusters with no reconstructed ground nearby (outlier debris over
    the sea), and blue-dominant clusters are rejected outright — ODM's
    classifier labels the planar sea surface "building", but no roof here is
    bluer than it is red.
    """
    if bld_xyh is None or len(bld_xyh) == 0:
        return []
    bld_xyh = np.asarray(bld_xyh, float)

    # cluster: rasterize points onto a coarse grid, bridge 1-cell gaps, label
    x0, z0 = bld_xyh[:, 0].min(), bld_xyh[:, 1].min()
    cols = ((bld_xyh[:, 0] - x0) / cell_m).astype(int)
    rows = ((bld_xyh[:, 1] - z0) / cell_m).astype(int)
    grid = np.zeros((rows.max() + 3, cols.max() + 3), bool)
    grid[rows + 1, cols + 1] = True
    labels, n = ndimage.label(ndimage.binary_dilation(grid, iterations=1))
    if n == 0:
        return []
    ids = labels[rows + 1, cols + 1]

    veg_counts = np.zeros(n + 1, int)
    if veg_xy is not None and len(veg_xy):
        vc = ((np.asarray(veg_xy)[:, 0] - x0) / cell_m).astype(int) + 1
        vr = ((np.asarray(veg_xy)[:, 1] - z0) / cell_m).astype(int) + 1
        inside = (vr >= 0) & (vr < labels.shape[0]) & (vc >= 0) & (vc < labels.shape[1])
        veg_counts = np.bincount(labels[vr[inside], vc[inside]], minlength=n + 1)

    def _raster_at(raster, xy):
        c = np.clip(np.round(xy[:, 0] / pixel_size + (raster.shape[1] - 1) / 2.0).astype(int),
                    0, raster.shape[1] - 1)
        r = np.clip(np.round(xy[:, 1] / pixel_size + (raster.shape[0] - 1) / 2.0).astype(int),
                    0, raster.shape[0] - 1)
        return raster[r, c]

    ground = cKDTree(ground_xy) if ground_xy is not None and len(ground_xy) else None

    buildings: list[Building] = []
    for i in range(1, n + 1):
        pts = bld_xyh[ids == i]
        if len(pts) < min_points or len(pts) <= veg_counts[i]:
            continue
        if ground is not None:
            n_gnd = len(ground.query_ball_point(pts[:, :2].mean(axis=0),
                                                ground_context_radius_m))
            if n_gnd < min_ground_context:
                continue  # no reconstructed land nearby: debris over water
        area = float(np.count_nonzero(grid & (labels == i))) * cell_m * cell_m
        if not (min_area_m2 <= area <= max_area_m2):
            continue

        hag = pts[:, 2]
        wall = float(np.percentile(hag, 25))
        ridge = float(np.percentile(hag, 95))
        if np.percentile(hag, 75) < min_height or ridge > max_height:
            continue  # too low to be a structure / reconstruction junk

        (cx, cz), (w, h), ang = cv2.minAreaRect(pts[:, :2].astype(np.float32))
        if min(w, h) < min_side_m or area / max(w * h, 1e-6) < min_fill:
            continue  # thin streak (misclassified flight line), not a roof

        if slope is not None:
            if float(np.median(_raster_at(slope, pts[:, :2]))) > max_slope_deg:
                continue  # cliff face

        roof = "gable" if ridge - wall >= gable_delta else "flat"
        color = (128, 128, 128) if rgb is None else \
            tuple(np.median(_raster_at(rgb, pts[:, :2]), axis=0))
        if float(color[2]) - float(color[0]) > max_blueness:
            continue  # blue-dominant: sea surface misclassified as building
        corners = cv2.boxPoints(((cx, cz), (w + 2 * footprint_pad_m, h + 2 * footprint_pad_m), ang))
        buildings.append(Building(
            footprint=[(float(x), float(z)) for x, z in corners],
            height=max(wall, 2.0), ridge=max(ridge, max(wall, 2.0) + 0.1),
            roof=roof, roof_color=color,
        ))
    return buildings
