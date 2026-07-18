"""Traditional-pixel-art toolkit: the Asset Creator's shared craft layer.

The discipline this module enforces, in order of importance:

1. **One master palette per identity.** `master_palette()` derives every
   material's ramp (foliage/wood/stone/water/earth + outline darks) from the
   visual-identity colors, deterministically. Every asset resolves its pixels
   THROUGH the palette — set-membership is validated by tests, and artists
   get the same colors as `palette.png` for editor/Aseprite touch-ups.
2. **Indices, not colors.** Generators paint integer maps (material, band);
   `resolve()` performs the only RGB lookup. Crisp alpha (0/255) and palette
   limits hold by construction.
3. **Deliberate pixels.** np.roll morphology for stair-stepped silhouettes,
   hand-authored clump stamps instead of per-pixel noise, sel-out outlines
   (dark hued ring, softened on the lit side), banded shading from a fixed
   top-left light.

Pure numpy/PIL, sha256-determinism, no network — the tiles2d/props2d
contract. `silhouette_iou()` is the variant-distinctness metric shared by
the generator's gate and the test suite.
"""
from __future__ import annotations

import colorsys
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

LIGHT = (-0.55, -0.55, 0.62)  # top-left key light, everywhere

RAMP_V = [0.42, 0.68, 1.00, 1.28, 1.55]
RAMP_S = [1.20, 1.25, 1.00, 0.80, 0.60]
SHADOW_HUE, HIGHLIGHT_HUE = 230.0 / 360.0, 60.0 / 360.0

# material -> (identity color attribute, hue-shift span multiplier)
MATERIALS = {
    "foliage": ("canopy_color", 1.0),
    "foliage_dark": ("canopy_color", 1.0),   # darkened base, see master_palette
    "wood": ("trunk_color", 0.5),
    "stone": ("cliff_color", 0.35),
    "water": ("water_color", 0.6),
    "earth": ("path_color", 0.5),
}


def rng_for(*key_parts) -> np.random.Generator:
    digest = hashlib.sha256(":".join(str(p) for p in key_parts).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


# --- palette ------------------------------------------------------------------

def _circular_lerp(h: float, target: float, t: float) -> float:
    d = target - h
    if d > 0.5:
        d -= 1.0
    elif d < -0.5:
        d += 1.0
    return (h + d * t) % 1.0


def ramp(rgb, steps: int = 5, hue_span: float = 1.0) -> list[tuple[int, int, int]]:
    """One material ramp, darkest first, base at the middle step."""
    h, s, v = colorsys.rgb_to_hsv(*[float(c) for c in rgb])
    v0 = min(max(v, 0.30), 0.62)
    mid = steps // 2
    out = []
    for i in range(steps):
        t = (i - mid) / max(mid, 1)
        vi = min(1.0, v0 * RAMP_V[i] if steps == 5 else v0 * (0.5 + 0.5 * (i + 1)))
        si = min(1.0, s * RAMP_S[i] if steps == 5 else s)
        target = HIGHLIGHT_HUE if t > 0 else SHADOW_HUE
        hi = _circular_lerp(h, target, abs(t) * 0.35 * hue_span)
        r, g, b = colorsys.hsv_to_rgb(hi, si, vi)
        out.append((int(round(r * 255)), int(round(g * 255)), int(round(b * 255))))
    return out


def outline_color(ramp_colors: list[tuple[int, int, int]], hue_span: float = 1.0
                  ) -> tuple[int, int, int]:
    r, g, b = [c / 255.0 for c in ramp_colors[0]]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h = _circular_lerp(h, SHADOW_HUE, 0.06 * hue_span)
    r2, g2, b2 = colorsys.hsv_to_rgb(h, min(1.0, s * 1.05), v * 0.55)
    return (int(round(r2 * 255)), int(round(g2 * 255)), int(round(b2 * 255)))


def master_palette(identity: dict) -> dict:
    """The identity's ONE palette: named ramps + outline darks + neutrals.

    Returns {"identity", "materials": {name: {"ramp": [[r,g,b]x5],
    "outline": [r,g,b]}}, "neutrals": [...]} — ~34 colors for the built-in
    ramps. The identity's optional `materials` block (visual-identity 2.4)
    appends EXTRA named ramps — bronze, verdigris, marble … — built with
    the exact same construction; entries are rgb01 (default hue_span 0.5,
    the restrained swing that suits metals) or {color, hue_span}.
    """
    pal: dict = {"schema": "palette/1.0",
                 "identity": str(identity.get("name", "identity")),
                 "materials": {}, "neutrals": [[20, 18, 22], [236, 233, 226]]}
    for mat, (attr, span) in MATERIALS.items():
        base = list(identity.get(attr, (0.5, 0.5, 0.5)))
        if mat == "foliage_dark":
            base = [c * 0.72 for c in base]
        colors = ramp(base, 5, span)
        pal["materials"][mat] = {"ramp": [list(c) for c in colors],
                                 "outline": list(outline_color(colors, span))}
    for mat, spec in identity.get("materials", {}).items():
        if isinstance(spec, dict):
            base, span = list(spec["color"]), float(spec.get("hue_span", 0.5))
        else:
            base, span = list(spec), 0.5
        colors = ramp(base, 5, span)
        pal["materials"][mat] = {"ramp": [list(c) for c in colors],
                                 "outline": list(outline_color(colors, span))}
    return pal


def palette_colors(pal: dict) -> set[tuple[int, int, int]]:
    out: set = set(tuple(n) for n in pal["neutrals"])
    for m in pal["materials"].values():
        out |= {tuple(c) for c in m["ramp"]}
        out.add(tuple(m["outline"]))
    return out


def write_palette(out_dir: Path, pal: dict) -> None:
    """palette.json + a labeled swatch sheet for color-picking."""
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = dict(pal)
    doc["hex"] = {mat: ["#%02x%02x%02x" % tuple(c) for c in m["ramp"]]
                  for mat, m in pal["materials"].items()}
    (out_dir / "palette.json").write_text(json.dumps(doc, indent=2) + "\n")
    mats = list(pal["materials"].items())
    cell = 24
    img = np.zeros(((len(mats) + 1) * cell, 6 * cell, 3), dtype=np.uint8)
    for row, (mat, m) in enumerate(mats):
        for col, c in enumerate(m["ramp"]):
            img[row * cell:(row + 1) * cell, col * cell:(col + 1) * cell] = c
        img[row * cell:(row + 1) * cell, 5 * cell:6 * cell] = m["outline"]
    for col, n in enumerate(pal["neutrals"]):
        img[len(mats) * cell:, col * cell:(col + 1) * cell] = n
    Image.fromarray(img, "RGB").save(out_dir / "palette.png")


# --- morphology (np.roll, 4-neighborhood) --------------------------------------

def dilate(m: np.ndarray) -> np.ndarray:
    return m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)


def erode(m: np.ndarray) -> np.ndarray:
    return m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)


def neighbor_count(m: np.ndarray) -> np.ndarray:
    return (np.roll(m, 1, 0).astype(int) + np.roll(m, -1, 0)
            + np.roll(m, 1, 1) + np.roll(m, -1, 1))


def tidy(m: np.ndarray, rounds: int = 2) -> np.ndarray:
    """Closing + despeckle: deliberate 1-2px stair-steps, no stray pixels."""
    out = erode(dilate(m))
    for _ in range(rounds):
        n = neighbor_count(out)
        out = (out & (n >= 2)) | (~out & (n >= 3))
    return out


def largest_component(m: np.ndarray) -> np.ndarray:
    """Keep only the largest 4-connected component (flood fill, pure numpy)."""
    remaining = m.copy()
    best = np.zeros_like(m)
    while remaining.any():
        seed = np.zeros_like(m)
        yx = np.argwhere(remaining)[0]
        seed[yx[0], yx[1]] = True
        while True:
            grown = dilate(seed) & remaining
            if (grown == seed).all():
                break
            seed = grown
        if seed.sum() > best.sum():
            best = seed
        remaining &= ~seed
    return best


# --- texture stamps (hand-authored leaf clumps) ---------------------------------

_CLUMPS = [
    np.array([[0, 1, 1, 0], [1, 1, 1, 1], [0, 1, 1, 1]], bool),
    np.array([[0, 1, 1], [1, 1, 1], [1, 1, 0], [0, 1, 0]], bool),
    np.array([[1, 1, 0, 0], [1, 1, 1, 1], [0, 0, 1, 1]], bool),
    np.array([[0, 0, 1, 1], [1, 1, 1, 0], [1, 1, 0, 0]], bool),
]
CLUMPS = _CLUMPS + [np.flip(c, 1) for c in _CLUMPS] + [np.flip(c, 0) for c in _CLUMPS]


def stamp(band: np.ndarray, where_mask: np.ndarray, rng, count: int,
          delta: int, band_lo: int, band_hi: int) -> None:
    """Scatter clump stamps onto `band` (in place), clipped to [lo, hi]."""
    ys, xs = np.nonzero(where_mask)
    if len(ys) == 0:
        return
    for _ in range(count):
        i = int(rng.integers(len(ys)))
        c = CLUMPS[int(rng.integers(len(CLUMPS)))]
        y0, x0 = ys[i] - c.shape[0] // 2, xs[i] - c.shape[1] // 2
        y1, x1 = y0 + c.shape[0], x0 + c.shape[1]
        if y0 < 0 or x0 < 0 or y1 > band.shape[0] or x1 > band.shape[1]:
            continue
        region = band[y0:y1, x0:x1]
        sel = c & (where_mask[y0:y1, x0:x1])
        region[sel] = np.clip(region[sel].astype(int) + delta,
                              band_lo, band_hi).astype(band.dtype)


# --- shading -------------------------------------------------------------------

def lobe_shading(lobes: list[tuple[float, float, float]], shape) -> np.ndarray:
    """Per-lobe pseudo-height field -> n·L scalar in [0..1]-ish."""
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]].astype(float)
    h = np.zeros(shape, dtype=float)
    for cx, cy, r in lobes:
        cap = np.clip(r * r - ((xx - cx) ** 2 + (yy - cy) ** 2), 0, None) / max(r, 1e-6)
        h = np.maximum(h, cap)
    gy, gx = np.gradient(h)
    k = 6.0
    norm = np.sqrt(gx * gx + gy * gy + k * k)
    lx, ly, lz = LIGHT
    s = (-gx * lx + -gy * ly + k * lz) / norm
    return (s - s.min()) / max(s.max() - s.min(), 1e-6)


def rim_depth(mask: np.ndarray, dy: int, dx: int, depth: int) -> np.ndarray:
    """Pixels within `depth` steps of the (dy,dx)-facing silhouette edge."""
    out = np.zeros_like(mask)
    m = mask.copy()
    for _ in range(depth):
        m = m & np.roll(np.roll(m, dy, 0), dx, 1)
    return mask & ~m


# --- outline -------------------------------------------------------------------

def ground_shadow(subject: np.ndarray, foot_y: int,
                  squash: float = 0.28) -> np.ndarray:
    """SHAPE-AWARE ground shadow: the subject's own silhouette squashed
    vertically onto the ground line, 50% checker-dithered (crisp alpha).

    Replaces the one-blob ellipse: a wide picnic table casts a table-wide
    low shadow, a round canopy an oval, a twin-posted frame two lobes —
    the shadow always agrees with the shape that casts it.
    """
    h, w = subject.shape
    out = np.zeros_like(subject, dtype=bool)
    ys, xs = np.nonzero(subject)
    if len(ys) == 0:
        return out
    foot_y = int(min(foot_y, h - 1))
    y2 = foot_y - ((foot_y - ys) * squash).astype(int)
    np.clip(y2, 0, h - 1, out=y2)
    out[y2, xs] = True
    out |= np.roll(out, 1, axis=0)          # 1px vertical fill for solidity
    yy, xx = np.mgrid[0:h, 0:w]
    checker = ((xx + yy) & 1) == 0
    return out & checker & ~subject


def outer_ring(mask: np.ndarray) -> np.ndarray:
    return dilate(mask) & ~mask


# --- derived metadata ------------------------------------------------------------

def measure_prop_meta(sil: np.ndarray, blocking_mask: np.ndarray,
                      fallback_cx: float | None = None,
                      r_min: float = 4.0, r_max: float = 14.0) -> dict:
    """anchor/footprint MEASURED from pixels — family-agnostic.

    anchor_y = lowest silhouette row (the visual foot). The BLOCKING
    footprint is measured from the bottom rows of `blocking_mask` — the
    family descriptor names what that is (a tree's trunk, a boulder's whole
    base) and QC verifies the result against the pixels.
    """
    h = sil.shape[0]
    ys2 = np.nonzero(sil)[0]
    foot_y = int(ys2.max()) if len(ys2) else h - 2
    fx = float(fallback_cx if fallback_cx is not None else sil.shape[1] / 2)
    fr = r_min + 1.0
    if blocking_mask.any():
        t_ys = np.nonzero(blocking_mask.any(axis=1))[0]
        # bottom 7 rows — the SAME window asset_qc's blocking_footprint
        # check re-measures (an 8th row caught a cart tub above its wheels:
        # measured span wider than the checked span, guaranteed FAIL)
        base_rows = blocking_mask[max(t_ys.max() - 6, 0):t_ys.max() + 1]
        cols = np.nonzero(base_rows.any(axis=0))[0]
        if len(cols):
            # center = PIXEL CENTROID of the contact rows — the midpoint of
            # the extremes lands in the valley of a multi-lobe base (slabs,
            # boulder clusters), off the actual mass
            fx = float(np.nonzero(base_rows)[1].mean())
            fr = float(np.clip((cols.max() - cols.min()) / 2.0 + 2.0,
                               r_min, r_max))
        fy = float(t_ys.max())
    else:
        fy = float(foot_y)
    return {"anchor_y": foot_y,
            "collision_r": fr,
            "footprint": {"center": [round(fx, 1), round(fy, 1)], "r": round(fr, 1)}}


# --- metrics -------------------------------------------------------------------

def silhouette_iou(a: np.ndarray, b: np.ndarray, size=(32, 48)) -> float:
    """Letterboxed silhouette IoU — the variant-distinctness metric.

    Bbox-cropped, then scaled by the MIN ratio and centered (aspect
    preserved): a tall tree and a wide tree stay distinguishable, while
    translation/scale are normalized away.
    """
    w, h = size

    def norm(m):
        ys, xs = np.nonzero(m)
        out = np.zeros((h, w), bool)
        if len(ys) == 0:
            return out
        crop = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        ch, cw = crop.shape
        scale = min(w / cw, h / ch)
        nw, nh = max(1, int(round(cw * scale))), max(1, int(round(ch * scale)))
        img = Image.fromarray(crop.astype(np.uint8) * 255).resize((nw, nh), Image.NEAREST)
        y0, x0 = (h - nh) // 2, (w - nw) // 2
        out[y0:y0 + nh, x0:x0 + nw] = np.asarray(img) > 127
        return out

    na, nb = norm(a), norm(b)
    union = (na | nb).sum()
    return float((na & nb).sum()) / max(float(union), 1.0)


def resolve(material: np.ndarray, band: np.ndarray, pal: dict,
            material_names: dict[int, str]) -> Image.Image:
    """(material idx map, band map) -> RGBA through the master palette."""
    h, w = material.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    for idx, name in material_names.items():
        if name.startswith("outline:"):
            colors = [pal["materials"][name.split(":")[1]]["outline"]] * 5
        else:
            colors = pal["materials"][name]["ramp"]
        sel = material == idx
        if not sel.any():
            continue
        b = np.clip(band[sel], 0, len(colors) - 1)
        lut = np.array(colors, dtype=np.uint8)
        rgba[sel, :3] = lut[b]
        rgba[sel, 3] = 255
    return Image.fromarray(rgba, "RGBA")


def interior_difference(a_rgba: np.ndarray, b_rgba: np.ndarray, size=(32, 32)) -> float:
    """Fraction of differing pixels where two normalized sprites overlap.

    The distinctness metric for near-round top-down forms, whose silhouettes
    are inherently similar — variety lives in the interior detail."""
    def box(arr):
        m = arr[:, :, 3] > 0
        ys, xs = np.nonzero(m)
        if len(ys) == 0:
            return np.zeros((size[1], size[0], 4), np.uint8)
        crop = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        return np.asarray(Image.fromarray(crop).resize(size, Image.NEAREST))
    A, B = box(a_rgba), box(b_rgba)
    both = (A[:, :, 3] > 0) & (B[:, :, 3] > 0)
    if both.sum() == 0:
        return 1.0
    diff = (A[:, :, :3] != B[:, :, :3]).any(axis=2) & both
    return float(diff.sum()) / float(both.sum())
