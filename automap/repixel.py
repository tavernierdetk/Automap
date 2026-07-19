"""RePixel: recreate a reference image as proper pixel art (ONE component).

The genlab counterpart of a procedural painter: where trees_px paints
(material, band) index maps from scratch, repixelize() RECOVERS index maps
from an arbitrary reference image (an image-generation model's output) and
then applies the exact same craft rules — so palette membership, crisp
alpha, banded shading and sel-out outlines hold BY CONSTRUCTION, and the
recovered maps are the same animation substrate the procedural path has.

Ordered passes (transform only — validation stays in asset_qc, the single
gate both backends share):

1. normalize   — subject mask from alpha or dominant border color; single
                 crisp mass (largest_component + tidy at target scale)
2. downscale   — DOMINANT-color reduce onto the target canvas (each cell
                 takes its most common quantized color — hard edges survive
                 where a mean would blend them); coverage decides opacity
3. palettize   — nearest master-palette color per pixel in CIELAB with
                 lightness downweighted (a material is a chroma family),
                 over the family's allowed materials -> (material, band)
4. smooth      — majority-vote material regions (a tree is foliage+wood
                 zones, not per-pixel speckle)
5. re-band     — per material region, re-quantize source luminance into
                 crisp bands ANCHORED to the observed band range (kills mud
                 without inventing near-white extremes)
6. sel-out     — outline ring in the nearest material's hued outline dark,
                 softened beside lit bands; dithered ground shadow re-added
                 per the family descriptor (the prompt asks for none)
7. resolve     — pixelart.resolve() through the master palette

Pure numpy/PIL, deterministic, no network.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from automap import pixelart as px
from automap import trees_px

# band indices below this many source pixels keep the palettized band
# (too small a region for meaningful luminance quantiles)
_MIN_REBAND_PX = 12


# --- color space -----------------------------------------------------------------

def _srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB uint8 (..., 3) -> CIELAB float (..., 3). Pure numpy, D65."""
    c = rgb.astype(float) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T
    white = np.array([0.95047, 1.0, 1.08883])
    v = xyz / white
    f = np.where(v > (6 / 29) ** 3, np.cbrt(v), v / (3 * (6 / 29) ** 2) + 4 / 29)
    lab = np.empty_like(f)
    lab[..., 0] = 116 * f[..., 1] - 16
    lab[..., 1] = 500 * (f[..., 0] - f[..., 1])
    lab[..., 2] = 200 * (f[..., 1] - f[..., 2])
    return lab


# --- passes ---------------------------------------------------------------------

def subject_mask(arr: np.ndarray, tol: float = 30.0) -> np.ndarray:
    """Foreground mask: real alpha if present, else remove the background by a
    corner-seeded flood fill that grows by LOCAL colour similarity — so it
    follows a gradient or a soft shadow and stops at the subject's hard edge
    (a single global colour key can't, which is why self-hosted SD refs left
    grey/shadow residue). Falls back to keying the median border colour when
    the flood is degenerate (subject touches a corner, near-uniform image)."""
    if arr.shape[2] == 4 and (arr[:, :, 3] < 250).any():
        return arr[:, :, 3] > 127
    rgb = np.ascontiguousarray(arr[:, :, :3], dtype=np.uint8)
    h, w = rgb.shape[:2]
    ff = np.zeros((h + 2, w + 2), np.uint8)            # cv2 flood mask (+2 ring)
    lo = up = (int(tol),) * 3
    flags = 4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8)   # 4-conn, neighbour range
    for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        cv2.floodFill(rgb, ff, seed, 0, lo, up, flags)
    fg = ~(ff[1:-1, 1:-1] > 0)
    frac = float(fg.mean())
    if frac < 0.02 or frac > 0.98:                     # removed nothing / everything
        rgbf = rgb.astype(float)
        border = np.concatenate([rgbf[0], rgbf[-1], rgbf[:, 0], rgbf[:, -1]])
        fg = np.linalg.norm(rgbf - np.median(border, axis=0), axis=2) > tol
    return fg


def downscale(arr: np.ndarray, mask: np.ndarray, target: tuple[int, int],
              bottom_reserve: int = 4, side_margin: int = 2,
              coverage: float = 0.45) -> tuple[np.ndarray, np.ndarray]:
    """BOX-reduce the subject onto the target canvas (w, h).

    Returns (rgb uint8 HxWx3, mask HxW). The subject is bbox-cropped, fitted
    preserving aspect, bottom-aligned with a reserve for the ground shadow.
    """
    tw, th = target
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return np.zeros((th, tw, 3), np.uint8), np.zeros((th, tw), bool)
    crop_rgb = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1, :3]
    crop_m = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    ch, cw = crop_m.shape
    avail_w, avail_h = tw - 2 * side_margin, th - bottom_reserve - 1
    scale = min(avail_w / cw, avail_h / ch)
    nw, nh = max(1, int(round(cw * scale))), max(1, int(round(ch * scale)))
    # DOMINANT-color reduce: each target cell takes the mean of its most
    # common quantized color among subject pixels. A plain BOX mean blends
    # colors across detail boundaries into off-palette intermediates that
    # palettize into the wrong material — the round-2 "mush" finding
    # (references arrive as crisp pixel clusters; keep their colors real).
    ys_i, xs_i = np.nonzero(crop_m)
    cell = (np.minimum(ys_i * nh // ch, nh - 1) * nw
            + np.minimum(xs_i * nw // cw, nw - 1)).astype(np.int64)
    cols = crop_rgb[ys_i, xs_i].astype(np.int64)
    qbin = ((cols[:, 0] >> 4) << 8) | ((cols[:, 1] >> 4) << 4) | (cols[:, 2] >> 4)
    key = cell * 4096 + qbin
    uniq, inv, counts = np.unique(key, return_inverse=True, return_counts=True)
    sums = np.zeros((len(uniq), 3))
    np.add.at(sums, inv, cols)
    bin_mean = sums / counts[:, None]
    ucell = uniq // 4096
    order = np.lexsort((counts, ucell))          # per cell, winner sorts last
    sorted_cells = ucell[order]
    present = np.unique(sorted_cells)
    winners = order[np.searchsorted(sorted_cells, present, side="right") - 1]
    small_rgb = np.zeros((nh, nw, 3), np.uint8)
    small_rgb[present // nw, present % nw] = \
        np.clip(bin_mean[winners], 0, 255).astype(np.uint8)
    cov = Image.fromarray((crop_m * 255).astype(np.uint8), "L") \
        .resize((nw, nh), Image.BOX)
    small_m = (np.asarray(cov).astype(float) / 255.0) >= coverage
    out_rgb = np.zeros((th, tw, 3), np.uint8)
    out_m = np.zeros((th, tw), bool)
    x0 = (tw - nw) // 2
    y0 = th - bottom_reserve - nh
    out_rgb[y0:y0 + nh, x0:x0 + nw] = small_rgb
    out_m[y0:y0 + nh, x0:x0 + nw] = small_m
    out_m = px.tidy(out_m)
    if out_m.any():
        out_m = px.largest_component(out_m)
    return out_rgb, out_m


def palettize(rgb: np.ndarray, mask: np.ndarray, pal: dict,
              materials: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray, dict]:
    """Nearest palette color in CIELAB over the allowed materials.

    Returns (material idx map, band map, names {idx: material}) — indices
    start at 1; 0 is empty.

    A family may allow materials the identity never defined (rock allows
    bronze for ore veins; a plain identity has no bronze): palettize over
    the intersection, so base families degrade gracefully instead of
    requiring every identity to carry every optional material.
    """
    available = tuple(m for m in materials if m in pal["materials"])
    if not available:
        raise ValueError(f"identity '{pal.get('identity', '?')}' defines none "
                         f"of the requested materials {materials}")
    names = {i + 1: m for i, m in enumerate(available)}
    lut_rgb, lut_mat, lut_band = [], [], []
    for idx, mat in names.items():
        for b, c in enumerate(pal["materials"][mat]["ramp"]):
            lut_rgb.append(c)
            lut_mat.append(idx)
            lut_band.append(b)
    lut_lab = _srgb_to_lab(np.array(lut_rgb, np.uint8))
    material = np.zeros(mask.shape, np.uint8)
    band = np.zeros(mask.shape, np.uint8)
    if mask.any():
        pix_lab = _srgb_to_lab(rgb[mask])
        diff = pix_lab[:, None, :] - lut_lab[None, :, :]
        # hue-weighted ΔE: a material is a CHROMA family more than a
        # lightness — unweighted distance sent warm sandy stone into the
        # wood/bronze mids (round-2 finding); band lightness is re-derived
        # by reband anyway
        diff[..., 0] *= 0.55
        d = np.linalg.norm(diff, axis=2)
        nearest = d.argmin(axis=1)
        material[mask] = np.array(lut_mat, np.uint8)[nearest]
        band[mask] = np.array(lut_band, np.uint8)[nearest]
    return material, band, names


def smooth_materials(material: np.ndarray, mask: np.ndarray,
                     rounds: int = 2) -> np.ndarray:
    """Majority-vote material labels among the 8-neighborhood (in place-ish)."""
    out = material.copy()
    labels = [int(v) for v in np.unique(out[mask])] if mask.any() else []
    for _ in range(rounds):
        counts = []
        for lab in labels:
            m = (out == lab).astype(int)
            n = sum(np.roll(np.roll(m, dy, 0), dx, 1)
                    for dy in (-1, 0, 1) for dx in (-1, 0, 1))
            counts.append(n)
        if not counts:
            break
        stack = np.stack(counts)
        winner = np.array(labels, np.uint8)[stack.argmax(axis=0)]
        out = np.where(mask, winner, out).astype(np.uint8)
    return out


def reband(rgb: np.ndarray, material: np.ndarray, band: np.ndarray,
           names: dict) -> np.ndarray:
    """Per material region, re-quantize source luminance into crisp bands —
    ANCHORED to the band range palettize actually observed.

    Stretching every region across the full 5-band ramp invented extremes:
    12% of any mid-grey stone mass became the ramp's near-white top band
    (round-2 "white blotches / milky canopy" finding). The luminance
    re-quantize keeps banding deliberate; the observed [lo, hi] keeps it
    honest about the region's true range.
    """
    lum = rgb.astype(int).sum(axis=2)
    out = band.copy()
    for idx in names:
        sel = material == idx
        if sel.sum() < _MIN_REBAND_PX:
            continue
        blo, bhi = np.percentile(band[sel], [5, 95]).astype(int)
        levels = bhi - blo + 1
        if levels < 2:
            out[sel] = blo
            continue
        edges = np.percentile(lum[sel],
                              np.linspace(0, 100, levels + 1)[1:-1])
        out[sel] = (blo + np.digitize(lum[sel], edges)).astype(np.uint8)
    return out


# --- the component ---------------------------------------------------------------

def repixelize(img: Image.Image, pal: dict, target: tuple[int, int],
               descriptor: dict, materials: tuple[str, ...] = ("foliage",
               "foliage_dark", "wood")) -> tuple[Image.Image, np.ndarray,
                                                 np.ndarray, dict]:
    """Reference image -> (RGBA sprite, material map, band map, names).

    The returned index maps are the animation substrate; `names` includes
    the outline entries so pixelart.resolve() can be re-run on edited maps.
    """
    arr = np.asarray(img.convert("RGBA"))
    mask = subject_mask(arr)
    rgb, mask = downscale(arr, mask, target)
    material, band, names = palettize(rgb, mask, pal, materials)
    material = smooth_materials(material, mask)
    band = reband(rgb, material, band, names)

    # sel-out outline: ring pixels take the hued outline of the material they
    # touch; soften beside lit interior bands (same craft rules as trees_px)
    ring = px.outer_ring(mask)
    n_mat = len(names) + 1
    ring_mat = np.zeros(mask.shape, np.uint8)
    for idx, mat in sorted(names.items()):
        near = px.dilate(material == idx)
        ring_mat = np.where(ring & near & (ring_mat == 0),
                            n_mat + idx, ring_mat).astype(np.uint8)
    out_names = dict(names)
    for idx, mat in names.items():
        out_names[n_mat + idx] = f"outline:{mat}"
    material = np.where(ring_mat > 0, ring_mat, material).astype(np.uint8)
    band = np.where(ring_mat > 0, 0, band).astype(np.uint8)
    lit_inside = mask & (band >= 3)
    soft = (ring_mat > 0) & (np.roll(lit_inside, 1, 0) | np.roll(lit_inside, 1, 1))
    if names:
        first_idx = min(names)
        material[soft] = first_idx
        band[soft] = 3

    sprite = px.resolve(material, band, pal, out_names)

    # ground shadow per the family descriptor (the prompt forbids one in the
    # reference so we never have to key it out)
    if descriptor.get("shadow") == "dither_ellipse":
        # (value name is historical: the shadow is now SILHOUETTE-projected
        # — shape-aware, still checker-dithered)
        full = mask | (ring_mat > 0)
        ys, _ = np.nonzero(full)
        if len(ys):
            sh = px.ground_shadow(full, min(int(ys.max()), mask.shape[0] - 2))
            a = np.array(sprite)
            a[sh, :3] = pal["neutrals"][0]
            a[sh, 3] = 255
            sprite = Image.fromarray(a, "RGBA")
    return sprite, material, band, out_names
