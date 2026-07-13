"""Minimap — a cartographic top-down render of the per-scene world model.

Not a screenshot: the map is drawn from `features.json` (footprints, roads,
water) in the visual identity's colors, so the minimap wears the same look
the scene does — one more consumer of the world model + identity contract.

Stage 6 emits `<glb stem>.minimap.png` + `.minimap.json` beside the styled
glb; stage 7 publishes them as `minimap.png`/`minimap.json` next to the
scene (the env.json pattern). The JSON carries the world→pixel transform the
runtime component needs:

    { "origin_x": west world x of pixel (0,0), "origin_z": north world z,
      "m_per_px": meters per pixel, "width": px, "height": px }

Pixel mapping: u = (x - origin_x) / m_per_px, v = (z - origin_z) / m_per_px
— +z is south (down on the map), so the map is north-up.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

DEFAULT_M_PER_PX = 1.5
MAX_PX = 1400


def _px(rgb) -> tuple[int, int, int]:
    return tuple(int(round(float(c) * 255)) for c in rgb[:3])


def _shade(rgb, f: float):
    return tuple(min(1.0, float(c) * f) for c in rgb[:3])


def render_minimap(features: list, bounds_xz: tuple, identity,
                   m_per_px: float = DEFAULT_M_PER_PX) -> tuple[Image.Image, dict]:
    """Rasterize the world model onto an identity-colored map.

    bounds_xz = (min_x, min_z, max_x, max_z) — normally the terrain glb's
    footprint so the map covers exactly the walkable world.
    """
    min_x, min_z, max_x, max_z = (float(v) for v in bounds_xz)
    span_x, span_z = max_x - min_x, max_z - min_z
    m_per_px = max(m_per_px, span_x / MAX_PX, span_z / MAX_PX)
    w = max(int(np.ceil(span_x / m_per_px)), 8)
    h = max(int(np.ceil(span_z / m_per_px)), 8)

    def uv(pt):
        return ((float(pt[0]) - min_x) / m_per_px, (float(pt[1]) - min_z) / m_per_px)

    img = Image.new("RGB", (w, h), _px(_shade(identity.grass_color, 0.9)))
    draw = ImageDraw.Draw(img)

    for f in features:
        if f.get("type") == "water" and f.get("outline"):
            pts = [uv(p) for p in f["outline"]]
            if len(pts) >= 3:
                draw.polygon(pts, fill=_px(identity.water_color))

    for f in features:
        if f.get("type") == "road" and f.get("path"):
            kind_dirt = f.get("kind") in ("footway", "path", "track", "steps")
            color = identity.path_color if kind_dirt else identity.road_color
            width_px = max(int(round(f.get("width", 5.0) / m_per_px)), 1)
            pts = [uv(p) for p in f["path"]]
            if len(pts) >= 2:
                draw.line(pts, fill=_px(color), width=width_px, joint="curve")

    bld = _px(_shade(identity.wall_color, 0.8))
    edge = _px(_shade(identity.wall_color, 0.5))
    for f in features:
        if f.get("type") == "building" and f.get("footprint"):
            pts = [uv(p) for p in f["footprint"]]
            if len(pts) >= 3:
                draw.polygon(pts, fill=bld, outline=edge)

    meta = {"origin_x": min_x, "origin_z": min_z, "m_per_px": m_per_px,
            "width": w, "height": h}
    return img, meta


def write_minimap(features: list, bounds_xz: tuple, identity, out_png: str | Path,
                  m_per_px: float = DEFAULT_M_PER_PX) -> dict:
    """Render and write the png + its transform json; returns the meta."""
    out_png = Path(out_png)
    img, meta = render_minimap(features, bounds_xz, identity, m_per_px)
    img.save(out_png)
    Path(str(out_png)[: -len(out_png.suffix)] + ".json").write_text(
        json.dumps(meta, indent=2) + "\n")
    return meta
