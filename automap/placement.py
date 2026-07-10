"""Where a dropped-in building lands in the scene frame.

Building substitution needs a rigid transform that puts an external IFC
model onto the world-model building it replaces. Two cases (the drop-in
script chooses):

- **georeferenced** — the IFC carries an IfcMapConversion, so its local
  coords are known in UTM; combined with the scene's own UTM anchor (raster
  center = frame origin) this fixes position and orientation exactly.
- **footprint-fit** — a generic plan in local coordinates: align its
  footprint's centroid and principal (long) axis to the target building's
  detected footprint. Metric scale is trusted (both are meters); only a
  yaw + translation is solved.

Everything here is 2D + a yaw about the vertical: buildings sit on the
ground, so horizontal placement is what matters and vertical seating is a
terrain drape done later (presentation stage), keyed by ground_xz.

Frames: IFC model space is x=east, y=north, z=up. The scene frame is
x=east, z=south, y=up, so the horizontal map is (x, y) -> (x, -y) plus the
solved yaw/translation. Returns a Placement the caller bakes into the glb.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Placement:
    yaw_deg: float               # rotation about the vertical (scene frame)
    translate_xz: tuple          # (x, z) offset in the scene frame (meters)
    ground_xz: tuple             # (x, z) where terrain is sampled to seat it

    def apply_xz(self, pts_xz: np.ndarray) -> np.ndarray:
        """Map (N,2) scene-frame x,z points through the placement."""
        a = np.radians(self.yaw_deg)
        rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        return pts_xz @ rot.T + np.asarray(self.translate_xz)


def _centroid_and_axis(footprint) -> tuple[np.ndarray, float]:
    """Centroid and long-axis angle (deg, atan2) of an (N,2) x,z polygon."""
    pts = np.asarray(footprint, float)
    c = pts.mean(axis=0)
    # principal axis via the footprint's longest edge (footprints here are
    # min-area rectangles, so the longest edge is the orientation)
    edges = np.roll(pts, -1, axis=0) - pts
    lengths = np.linalg.norm(edges, axis=1)
    e = edges[int(np.argmax(lengths))]
    return c, float(np.degrees(np.arctan2(e[1], e[0])))


def fit_footprint(source_xz, target_xz) -> Placement:
    """Yaw + translation mapping the source footprint onto the target.

    Both are (N,2) footprints already in the scene frame (source = the IFC's
    footprint mapped x,-y; target = the world-model building's). Aligns long
    axes and centroids; the ±180° ambiguity of a rectangle's axis is resolved
    by picking the yaw whose mapped source overlaps the target best.
    """
    src = np.asarray(source_xz, float)
    tgt = np.asarray(target_xz, float)
    c_src, a_src = _centroid_and_axis(src)
    c_tgt, a_tgt = _centroid_and_axis(tgt)

    best = None
    for flip in (0.0, 180.0):
        yaw = a_tgt - a_src + flip
        a = np.radians(yaw)
        rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        # self-contained translate so apply_xz works on RAW points:
        #   f(p) = (p - c_src) R^T + c_tgt = p R^T + (c_tgt - c_src R^T)
        trans = c_tgt - c_src @ rot.T
        p = Placement(yaw_deg=yaw, translate_xz=tuple(trans), ground_xz=tuple(c_tgt))
        err = np.abs(np.sort(p.apply_xz(src), 0) - np.sort(tgt, 0)).sum()
        if best is None or err < best[0]:
            best = (err, p)
    return best[1]


def from_georeference(src_anchor: dict, scene_anchor: dict,
                      target_footprint) -> Placement:
    """Placement from an IFC's IfcMapConversion vs the scene's UTM anchor.

    Both anchors are {eastings, northings, crs}. The IFC's local origin sits
    at src_anchor in UTM; the scene frame's origin sits at scene_anchor. A
    local point (x_e, y_n) therefore lands at scene
    (x = (E_src + x_e) - E_scene,  z = -((N_src + y_n) - N_scene)).
    True-north rotation between model and grid is assumed ~0 for v1 (recorded
    as a follow-up); ground_xz is the target centroid so the drape is stable.
    """
    if src_anchor.get("crs") and scene_anchor.get("crs") \
            and src_anchor["crs"] != scene_anchor["crs"]:
        raise ValueError(
            f"CRS mismatch: IFC {src_anchor['crs']} vs scene {scene_anchor['crs']} "
            "(reproject the IFC first, or use footprint-fit)")
    dx = src_anchor["eastings"] - scene_anchor["eastings"]
    dz = -(src_anchor["northings"] - scene_anchor["northings"])
    c_tgt = np.asarray(target_footprint, float).mean(axis=0)
    return Placement(yaw_deg=0.0, translate_xz=(dx, dz), ground_xz=tuple(c_tgt))
