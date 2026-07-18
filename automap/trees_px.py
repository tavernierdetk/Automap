"""Pixel-art tree family — TOP-DOWN, tileset-ready (style token px2).

Studied against reference-grade top-down tree packs (craftpix free set,
2026-07-16 — studied, never copied): the crafts this renderer encodes are

- canopy MASS seen from above: a scalloped/jagged near-round silhouette,
  never a smooth blob;
- texture from many small, individually shaded elements — leaf TUFTS
  (cloud deciduous) or radial leaf SPIKES (conifer) — each with a lit
  top-left arc and a shadowed bottom-right, plus deep shadow pockets where
  elements meet;
- concentric shading from a light center offset to the top-left;
- chunky root TOES peeking from under the canopy's bottom rim;
- a dithered (checkerboard) ground-shadow ellipse — crisp alpha preserved;
- three sizes per type (large/medium/small), variants within each.

Sprites are sized to the 32px tile grid (96/64/32 square) so the packer can
shelf them into ONE tree tileset atlas the Godot editor paints from. All
pixels resolve through the identity MASTER palette; size/collision/sort
metadata ride in the atlas JSON.

Seeds: sha256(identity:tree:substyle:variant:px2[:retryN]) — bumping the
style token deliberately invalidates every generated tree (px1 side-view
sprites are superseded by exactly this mechanism).
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from automap import pixelart as px

STYLE_TOKEN = "px3"
TILE = 32
# 3/4-view canvases (w, h) on the 32px grid: canopy volume up top, VISIBLE
# trunk + root flare below — the RPG hybrid perspective of the reference.
SIZES = {"large": (96, 128), "medium": (64, 96), "small": (32, 64)}
SIZE_ORDER = ["large", "medium", "large", "medium", "small", "large"]

MAT_CANOPY, MAT_TRUNK, MAT_OUT_C, MAT_OUT_W, MAT_SHADOW = 1, 2, 3, 4, 5
BAND_THRESHOLDS = [0.18, 0.38, 0.60, 0.82]


def _polar_silhouette(w, h, cx, cy, base_r, rng, spikes: bool) -> np.ndarray:
    """Near-round canopy with a scalloped (tufts) or jagged (spikes) rim."""
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    ang = np.arctan2(yy - cy, xx - cx)
    dist = np.hypot(xx - cx, yy - cy)
    k = 44 if spikes else 24
    offs = rng.uniform(-1.0, 1.0, size=k)
    idx = ((ang + np.pi) / (2 * np.pi) * k).astype(int) % k
    wobble = offs[idx] * (base_r * 0.06)
    if spikes:
        spike_len = rng.uniform(1.5, 3.5)
        wobble = wobble + (idx % 3 == 0).astype(float) * spike_len
    else:
        wobble = wobble + np.cos(ang * int(rng.integers(7, 11))) * base_r * 0.05
    return dist < (base_r + wobble)


def _tufts(cx, cy, base_r, rng, n_ring, n_core):
    """Small tuft circles: a ring along the rim + a filled core."""
    tufts = []
    for i in range(n_ring):
        a = 2 * np.pi * i / n_ring + float(rng.uniform(-0.2, 0.2))
        rr = base_r * float(rng.uniform(0.62, 0.85))
        tufts.append((cx + np.cos(a) * rr, cy + np.sin(a) * rr,
                      base_r * float(rng.uniform(0.24, 0.36))))
    for _ in range(n_core):
        a = float(rng.uniform(0, 2 * np.pi))
        rr = base_r * float(rng.uniform(0.0, 0.5))
        tufts.append((cx + np.cos(a) * rr, cy + np.sin(a) * rr,
                      base_r * float(rng.uniform(0.28, 0.42))))
    return tufts


def _roots(w, h, cx, top_y, rng, scale=1.0):
    """Chunky root toes splaying downward from under the canopy rim."""
    mask = np.zeros((h, w), bool)
    n = int(rng.integers(3, 6))
    for i in range(n):
        off = (i - (n - 1) / 2) * 5.5 * scale + float(rng.uniform(-1.5, 1.5))
        length = float(rng.uniform(5, 9)) * max(scale, 0.5)
        half = max(2.2 * scale, 1.2)
        for s in range(int(length)):
            y = int(top_y + s * 0.75)
            xw = max(half * (1.0 - s / length * 0.7), 0.8)
            xc = cx + off * (0.6 + 0.4 * s / length)
            x0, x1 = int(xc - xw), int(xc + xw + 1)
            if 0 <= y < h:
                mask[y, max(x0, 0):min(x1, w)] = True
    return mask


def _shadow_ellipse(w, h, cx, cy, rx, ry) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    inside = ((xx - cx) / max(rx, 1)) ** 2 + ((yy - cy) / max(ry, 1)) ** 2 < 1.0
    checker = ((xx.astype(int) + yy.astype(int)) & 1) == 0
    return inside & checker  # 50% dither: soft read, crisp alpha


# --- substyle structures ---------------------------------------------------------

def _trunk_34(w, h, cx, top_y, base_y, rng, s):
    """Visible 3/4-view trunk: tapered column + splayed root toes."""
    mask = np.zeros((h, w), bool)
    lean = float(rng.uniform(-2.5, 2.5)) * s
    span = max(base_y - top_y, 1)
    half_top = max(2.2 * s, 1.4)
    half_base = max(4.2 * s, 2.2)
    for y in range(int(top_y), int(base_y)):
        t = max((y - top_y) / span, 0.0)
        xc = cx + lean * (1.0 - t)
        half = half_top + (half_base - half_top) * t ** 1.6
        x0, x1 = int(xc - half), int(xc + half + 1)
        mask[y, max(x0, 0):min(x1, w)] = True
    mask |= _roots(w, h, cx, base_y - 3 * s, rng, max(s, 0.55))
    return mask


def _structure(substyle, size_px, rng):
    w, h = size_px
    cx = w / 2 + float(rng.uniform(-1.5, 1.5))
    cy = h * 0.34 + float(rng.uniform(-2.0, 2.0))     # canopy center, upper part
    base_r = w * 0.46 * float(rng.uniform(0.92, 1.0))
    s = w / 96.0

    base_y = h - max(5.0 * s, 3.0)

    if substyle == "dead":
        trunk = np.zeros((h, w), bool)
        yy_g, xx_g = np.mgrid[0:h, 0:w].astype(float)

        def branch(x, y, ang, length, width, depth):
            steps = max(int(length), 1)
            for st in range(steps):
                xi = float(np.clip(x + np.cos(ang) * st, 2, w - 3))
                yi = float(np.clip(y - np.sin(ang) * st, 2, h - 3))
                r = max(width * (1.0 - st / steps * 0.45), 0.7)
                trunk[((xx_g - xi) ** 2 + (yy_g - yi) ** 2) <= r * r] = True
            ex = float(np.clip(x + np.cos(ang) * steps, 2, w - 3))
            ey = float(np.clip(y - np.sin(ang) * steps, 2, h - 3))
            if depth > 0:
                for _ in range(int(rng.integers(1, 3))):
                    branch(ex, ey, ang + float(rng.uniform(-0.5, 0.5)),
                           length * 0.62, max(width - 1, 0.7), depth - 1)

        # visible trunk climbing from the base, gnarled branches reaching UP
        trunk |= _trunk_34(w, h, cx, h * 0.45, base_y, rng, s)
        n_arms = int(rng.integers(3, 6))
        for i in range(n_arms):
            a = np.pi / 2 + float(rng.uniform(-0.9, 0.9))
            branch(cx + float(rng.uniform(-3, 3)) * s, h * 0.48,
                   a, h * 0.30 * float(rng.uniform(0.7, 1.0)), 2.4 * s + 0.6, 2)
        return {"canopy": np.zeros((h, w), bool), "trunk": trunk, "tufts": [],
                "cx": cx, "cy": cy, "base_r": base_r, "base_y": base_y,
                "canopy_mat": "foliage", "spiky": False}

    spiky = substyle == "pine"
    ry_mul = 0.80 if not spiky else 0.92   # slightly squashed canopy = 3/4 read
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    canopy = _polar_silhouette(w, h, cx, cy, base_r, rng, spiky)
    canopy &= (np.abs(yy - cy) < base_r * ry_mul + 3)  # squash vertically
    tufts = []
    if not spiky:
        tufts = _tufts(cx, cy, base_r, rng,
                       n_ring=int(rng.integers(8, 13)),
                       n_core=int(rng.integers(4, 8)))
        bump = np.zeros((h, w), bool)
        for tx, ty, tr in tufts:
            bump |= ((xx - tx) ** 2 + (yy - ty) ** 2) < tr * tr
        canopy |= bump
    # THE 3/4 silhouette: a visible trunk from under the canopy to the base
    trunk = _trunk_34(w, h, cx, cy + base_r * 0.35, base_y, rng, s)
    return {"canopy": canopy, "trunk": trunk, "tufts": tufts,
            "cx": cx, "cy": cy, "base_r": base_r, "base_y": base_y,
            "canopy_mat": "foliage_dark" if spiky else "foliage",
            "spiky": spiky}


# --- shared render ----------------------------------------------------------------

def _render(st: dict, pal: dict, rng, size_px) -> tuple[Image.Image, dict]:
    w, h = size_px
    canopy = px.tidy(st["canopy"])
    if canopy.any():
        canopy = px.largest_component(canopy)
    trunk = st["trunk"] & ~canopy
    cx, cy, base_r = st["cx"], st["cy"], st["base_r"]

    material = np.zeros((h, w), np.uint8)
    band = np.full((h, w), 2, np.uint8)

    # ground shadow first, under everything
    sil0 = canopy | trunk
    ys_all = np.nonzero(sil0)[0]
    bottom = int(ys_all.max()) if len(ys_all) else int(st.get("base_y", h - 4))
    shadow = _shadow_ellipse(w, h, cx, min(bottom, h - 2),
                             base_r * 0.70, max(base_r * 0.18, 3))
    material[shadow] = MAT_SHADOW

    material[trunk] = MAT_TRUNK
    material[canopy] = MAT_CANOPY

    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    if canopy.any():
        lx, ly = cx - base_r * 0.30, cy - base_r * 0.32
        d = np.hypot(xx - lx, yy - ly) / max(base_r * 1.15, 1.0)
        sfield = 1.0 - np.clip(d, 0, 1)
        cb = np.digitize(sfield, BAND_THRESHOLDS).astype(int)
        if st["spiky"]:
            # concentric branch rings stepping darker outward, with per-ring
            # angular jitter — reads as fir tiers from above, not a pinwheel
            rr = np.hypot(xx - cx, yy - cy) / max(base_r, 1.0)
            ring = np.clip((rr * 3.6)).astype(int) if False else np.clip((rr * 3.6), 0, 5).astype(int)
            cb = np.clip(4 - ring, 0, 4)
            ang = np.arctan2(yy - cy, xx - cx)
            k = 28
            strips = ((ang + np.pi) / (2 * np.pi) * k).astype(int) % k
            lut = rng.integers(-1, 2, size=(6, k))
            jitter = lut[np.clip(ring, 0, 5), strips]
            outer = rr > 0.18  # keep the very center calm
            cb = np.where(outer, np.clip(cb + jitter, 0, 4), cb)
            # light bias: brighten the top-left half a step
            cb = np.clip(cb + ((xx - cx) + (yy - cy) < -base_r * 0.25).astype(int), 0, 4)
        else:
            for tx, ty, tr in st["tufts"]:
                dd = np.hypot(xx - tx, yy - ty)
                inside = dd < tr
                lit = inside & (np.hypot(xx - (tx - tr * 0.35),
                                         yy - (ty - tr * 0.35)) < tr * 0.62)
                shade = inside & (np.hypot(xx - (tx + tr * 0.4),
                                           yy - (ty + tr * 0.4)) < tr * 0.7) & ~lit
                cb[lit] += 1
                cb[shade] -= 1
                shadow_half = (xx - cx) + (yy - cy) > 0
                pocket = (dd >= tr * 0.86) & (dd < tr * 1.05) & canopy & ~lit & shadow_half
                cb[pocket] -= 1
            cb = np.clip(cb, 0, 4)
        rim = px.rim_depth(canopy, -1, -1, 2)
        cb[rim] = np.minimum(cb[rim], 1)
        band[canopy] = cb[canopy].astype(np.uint8)
        glint = canopy & (np.array(cb) >= 4)
        gys, gxs = np.nonzero(glint)
        if len(gys):
            for _ in range(int(rng.integers(4, 10))):
                i = int(rng.integers(len(gys)))
                band[gys[i], gxs[i]] = 4

    if trunk.any():
        tb = np.full((h, w), 2, np.uint8)
        # key light is top-LEFT: lit rim faces up-left, shade faces down-right
        tb[px.rim_depth(trunk, 0, -1, 1)] = 3
        tb[px.rim_depth(trunk, 1, 1, 1)] = 3
        tb[px.rim_depth(trunk, 0, 1, 1)] = 1
        tb[px.rim_depth(trunk, -1, -1, 1)] = 1
        if canopy.any():
            under = trunk & px.dilate(px.dilate(canopy))
            tb[under] = 0
        else:
            # canopy-less (dead): weathered vertical gradient — sun-bleached
            # upper reaches, dark base — so the light reads top-down too
            t_ys2 = np.nonzero(trunk.any(axis=1))[0]
            span2 = max(t_ys2.max() - t_ys2.min(), 1)
            yy_n = (yy - t_ys2.min()) / span2
            tb = np.where(trunk & (yy_n < 0.38), np.minimum(tb + 1, 3), tb).astype(np.uint8)
            tb = np.where(trunk & (yy_n > 0.72), np.maximum(tb.astype(int) - 1, 0), tb).astype(np.uint8)
        band[trunk] = np.clip(tb[trunk], 0, 3)

    # sel-out outline around the tree (never around the dither shadow)
    sil = canopy | trunk
    ring = px.outer_ring(sil)
    near_canopy = px.dilate(canopy)
    out_mat = np.where(near_canopy, MAT_OUT_C, MAT_OUT_W).astype(np.uint8)
    material[ring] = out_mat[ring]
    band[ring] = 0
    lit_inside = canopy & (band >= 3)
    soft = ring & (np.roll(lit_inside, 1, 0) | np.roll(lit_inside, 1, 1))
    material[soft] = MAT_CANOPY
    band[soft] = 3
    if canopy.any():
        shadow_half2 = (xx - cx) + (yy - cy) > 0
        for ax in (0, 1):
            jump = canopy & np.roll(canopy, 1, ax) & \
                   (np.abs(band.astype(int) - np.roll(band.astype(int), 1, ax)) >= 3)
            sel = jump & canopy & (band >= 2) & shadow_half2
            band[sel] = 1

    names = {MAT_CANOPY: st["canopy_mat"], MAT_TRUNK: "wood",
             MAT_OUT_C: "outline:" + st["canopy_mat"], MAT_OUT_W: "outline:wood"}
    img = px.resolve(material, band, pal, names)
    arr = np.array(img)
    shadow_sel = (material == MAT_SHADOW)
    arr[shadow_sel, :3] = pal["neutrals"][0]
    arr[shadow_sel, 3] = 255
    img = Image.fromarray(arr, "RGBA")

    meta = measure_tree_meta(sil, trunk, fallback_cx=cx)
    meta["size_px"] = size_px
    # the index maps ARE the animation substrate (transient — callers pop
    # this before serializing; animate_px edits bands, never the material)
    meta["maps"] = (material, band, names)
    return img, meta


def measure_tree_meta(sil: np.ndarray, trunk: np.ndarray,
                      fallback_cx: float | None = None) -> dict:
    """Tree-family metadata: the BLOCKING footprint is the TRUNK BASE,
    measured from actual trunk pixels — never derived from the canopy
    (descriptor: blocking=trunk_base)."""
    return px.measure_prop_meta(sil, trunk, fallback_cx=fallback_cx,
                                r_min=4.0, r_max=14.0)


def build_variant(pal: dict, substyle: str, seed_key: str, size_name: str
                  ) -> tuple[Image.Image, dict]:
    size_wh = SIZES[size_name]
    rng = px.rng_for(seed_key)
    st = _structure(substyle, size_wh, rng)
    img, meta = _render(st, pal, rng, size_wh)
    meta["size_name"] = size_name
    return img, meta


def build_set(pal: dict, identity_name: str, substyle: str, count: int,
              start_variant: int = 0, iou_max: float = 0.90,
              interior_min: float = 0.30
              ) -> dict[str, tuple[Image.Image, dict]]:
    """`count` gated variants cycling large/medium/small. Deterministic."""
    out: dict[str, tuple[Image.Image, dict]] = {}
    accepted: list[np.ndarray] = []
    for i in range(count):
        v = start_variant + i
        size_name = SIZE_ORDER[v % len(SIZE_ORDER)]
        best = None
        for retry in range(5):
            key = f"{identity_name}:tree:{substyle}:{v}:{STYLE_TOKEN}" + \
                  (f":retry{retry}" if retry else "")
            img, meta = build_variant(pal, substyle, key, size_name)
            mask = np.asarray(img)[:, :, 3] > 0
            # validity BEFORE distinctness (a broken sprite is maximally distinct)
            rooted = mask[-16:].sum() >= 12       # trunk/roots reach the base
            substantial = mask.sum() >= mask.size * 0.16 and rooted
            if not substantial:
                if best is None:
                    best = (2.0, img, meta, mask)
                continue
            arr = np.asarray(img)
            worst_iou = max((px.silhouette_iou(mask, m) for m, _ in accepted), default=0.0)
            worst_diff = min((px.interior_difference(arr, a) for _, a in accepted), default=1.0)
            score = worst_iou + (interior_min - min(worst_diff, interior_min))
            if best is None or best[0] > 1.0 or score < best[0]:
                best = (score, img, meta, mask)
            if worst_iou <= iou_max and worst_diff >= interior_min:
                break
        _, img, meta, mask = best
        accepted.append((mask, np.asarray(img)))
        out[f"{substyle}_{v}"] = (img, meta)
    return out
