"""Asset QC: automated, family-agnostic quality control for generated sprites.

The purpose is ITERATION SPEED: a renderer tweak is judged by machine checks
(this module + pytest) in milliseconds, and human/LLM eyeballs are spent only
on final calibration — not on every variant of every iteration.

Two layers:

1. **Generic craft checks** (any pixel-art asset): crisp alpha, master-palette
   membership, single main mass (dithered shadows exempted), outline coverage
   and darkness, light direction (the highlight mass must sit up-left of the
   shadow mass — the fixed key light made measurable), band balance (no
   all-midtone mud, no blown highlights), canvas grid alignment.
2. **Family-descriptor checks**: each family in asset_creator.FAMILIES carries
   a DESCRIPTOR — the conceptual contract of the family — including
   `blocking`, which names the asset's blocking element ("trunk_base" for
   trees: the trunk footprint blocks, the canopy NEVER does). QC verifies the
   emitted footprint against the actual pixels: center inside the lower mass,
   radius no wider than the trunk, canopy rows clear of the circle.

Set-level checks (distinctness) reuse pixelart.silhouette_iou /
interior_difference. Every check returns (name, ok, score, detail); a report
aggregates pass/fail — usable from pytest, the ensure() gate, and the
`13 assets qc` CLI.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from automap import pixelart as px


@dataclass
class Check:
    name: str
    ok: bool
    score: float
    detail: str = ""


def _mask(arr: np.ndarray) -> np.ndarray:
    return arr[:, :, 3] > 0


def _main_mass(arr: np.ndarray) -> np.ndarray:
    """The asset's solid body: opaque pixels minus isolated dither (shadows)."""
    m = _mask(arr)
    n = px.neighbor_count(m)
    solid = m & (n >= 2)
    if not solid.any():
        return solid
    return px.largest_component(solid)


# --- generic checks ---------------------------------------------------------------

def check_crisp_alpha(arr) -> Check:
    vals = set(np.unique(arr[:, :, 3]))
    ok = vals <= {0, 255}
    return Check("crisp_alpha", ok, 1.0 if ok else 0.0, f"alpha values {sorted(vals)}")


def check_palette(arr, pal) -> Check:
    allowed = px.palette_colors(pal)
    opaque = arr[_mask(arr)][:, :3]
    used = {tuple(c) for c in opaque}
    stray = used - allowed
    return Check("palette_membership", not stray,
                 1.0 - len(stray) / max(len(used), 1),
                 f"{len(stray)} stray of {len(used)} colors")


def check_single_mass(arr) -> Check:
    m = _mask(arr)
    n = px.neighbor_count(m)
    solid = m & (n >= 2)
    main = _main_mass(arr)
    frac = main.sum() / max(solid.sum(), 1)
    return Check("single_mass", frac >= 0.92, float(frac),
                 f"main component {frac:.2f} of solid pixels")


def check_outline(arr) -> Check:
    main = _main_mass(arr)
    interior = px.erode(main)
    edge = main & ~interior
    if not edge.any() or not interior.any():
        return Check("outline", False, 0.0, "no measurable edge")
    edge_lum = arr[edge][:, :3].mean()
    inner_lum = arr[interior][:, :3].mean()
    ratio = edge_lum / max(inner_lum, 1.0)
    return Check("outline", ratio < 0.92, float(1.0 - ratio),
                 f"edge/interior luminance {ratio:.2f}")


def resolve_descriptor(descriptor: dict, substyle: str | None) -> dict:
    """Per-substyle descriptor values: a dict-valued key is a substyle
    lookup (key absent for substyles it doesn't name). Lets one family
    carry e.g. `"lighting": {"shaftmouth": "ground_plane"}` while its
    other substyles keep the default."""
    out = {}
    for k, v in descriptor.items():
        if isinstance(v, dict):
            if substyle in v:
                out[k] = v[substyle]
        else:
            out[k] = v
    return out


def check_light_direction(arr, pal, descriptor: dict | None = None) -> Check:
    """Highlight centroid must sit up-left of shadow centroid (fixed key
    light) — judged within the DOMINANT material.

    Global luminance mis-judges multi-material assets: a pale stone footing
    at an asset's base swamps the bronze body's key-light read (round-2
    campaign finding). Ground-plane subjects (a shaft mouth lit radially,
    bright near rim over a dark pit) opt out via descriptor
    `"lighting": "ground_plane"`.
    """
    if (descriptor or {}).get("lighting") == "ground_plane":
        return Check("light_direction", True, 1.0,
                     "ground-plane subject (radial light) — n/a")
    if (descriptor or {}).get("lighting") == "ambient":
        return Check("light_direction", True, 1.0,
                     "albedo-striped subject — centroid read unreliable, n/a")
    main = _main_mass(arr)
    if not main.any():
        return Check("light_direction", False, 0.0, "empty")
    # dominant material = the largest exact-ramp-color population
    code = (arr[:, :, 0].astype(np.int32) << 16) | \
           (arr[:, :, 1].astype(np.int32) << 8) | arr[:, :, 2].astype(np.int32)
    dom, dom_n = None, 0
    for mat in pal["materials"].values():
        ramp = np.array([(c[0] << 16) | (c[1] << 8) | c[2]
                         for c in mat["ramp"]], np.int32)
        sel = main & np.isin(code, ramp)
        if sel.sum() > dom_n:
            dom, dom_n = sel, int(sel.sum())
    judge = dom if dom_n >= 40 else main
    lum = arr[:, :, :3].astype(int).sum(axis=2)
    lo, hi = np.percentile(lum[judge], [25, 75])
    bright = judge & (lum >= hi)
    dark = judge & (lum <= lo)
    if not bright.any() or not dark.any():
        return Check("light_direction", False, 0.0, "no contrast")
    by, bx = np.argwhere(bright).mean(axis=0)
    dy, dx = np.argwhere(dark).mean(axis=0)
    score = float((dx - bx) + (dy - by))  # positive = bright is up-left
    # small negatives are centroid noise on small sprites, not bottom-light
    # (a genuinely bottom-lit mass scores far below the band)
    return Check("light_direction", score > -3.0, score,
                 f"bright({bx:.0f},{by:.0f}) vs dark({dx:.0f},{dy:.0f})")


def check_band_balance(arr, pal) -> Check:
    """Shading must be banded, not mud: mid-tones 20-85%, extremes present."""
    main = _main_mass(arr)
    lum = arr[:, :, :3].astype(int).sum(axis=2)[main]
    if lum.size == 0:
        return Check("band_balance", False, 0.0, "empty")
    lo, hi = np.percentile(lum, [10, 90])
    spread = (hi - lo) / max(float(lum.mean()), 1.0)
    mid_frac = float(((lum > lo) & (lum < hi)).mean())
    ok = spread > 0.25 and 0.2 <= mid_frac <= 0.9
    return Check("band_balance", ok, float(spread),
                 f"spread {spread:.2f}, mid fraction {mid_frac:.2f}")


def check_grid_alignment(arr, tile: int = 32) -> Check:
    h, w = arr.shape[:2]
    ok = w % tile == 0 and h % tile == 0
    return Check("grid_alignment", ok, 1.0 if ok else 0.0, f"{w}x{h}")


# --- descriptor checks --------------------------------------------------------------

def check_blocking_footprint(arr, meta, descriptor) -> Check:
    """The footprint must match the descriptor's blocking concept.

    'trunk_base': circle centered inside the lower solid mass; radius no
    wider than the local mass; the upper (canopy) half must NOT intersect it.
    """
    blocking = descriptor.get("blocking", "base")
    fp = meta.get("footprint")
    if fp is None:
        return Check("blocking_footprint", False, 0.0, "no footprint emitted")
    main = _main_mass(arr)
    h, w = main.shape
    if fp.get("kind") == "rect":
        # RECT footprint (buildings: the facade span). Emitted from known
        # assembler geometry — verified here against the pixels anyway.
        fx, fy = fp["center"]
        hw, hh = fp["half"]
        ys = np.nonzero(main.any(axis=1))[0]
        if len(ys) == 0:
            return Check("blocking_footprint", False, 0.0, "empty mass")
        base_y = ys.max()
        if abs((fy + hh) - base_y) > 3:
            return Check("blocking_footprint", False, 0.0,
                         f"rect bottom {fy + hh:.0f} off the base row {base_y}")
        rows = main[max(int(base_y) - 6, 0):int(base_y) + 1]
        cols = np.nonzero(rows.any(axis=0))[0]
        half_mass = (cols.max() - cols.min()) / 2 if len(cols) else 0
        if hw > half_mass + 4:
            return Check("blocking_footprint", False, 0.0,
                         f"rect half-width {hw:.0f} wider than base "
                         f"half-width {half_mass:.0f}")
        if half_mass >= 8 and hw < half_mass * 0.6:
            return Check("blocking_footprint", False, 0.0,
                         f"rect half-width {hw:.0f} too small for base "
                         f"half-width {half_mass:.0f} (must span the facade)")
        return Check("blocking_footprint", True, 1.0,
                     f"rect at ({fx:.0f},{fy:.0f}) half {hw:.0f}x{hh:.0f}")
    fx, fy = fp["center"]
    r = fp["r"]
    if not (0 <= int(fy) < h and 0 <= int(fx) < w):
        return Check("blocking_footprint", False, 0.0,
                     f"center ({fx},{fy}) outside the canvas")
    if blocking == "trunk_base":
        # the trunk is one solid contact patch: the center must sit ON it
        # (±3: centroids may rest in a small notch)
        if not main[int(fy) - 2:int(fy) + 1,
                    max(int(fx) - 3, 0):int(fx) + 4].any():
            return Check("blocking_footprint", False, 0.0,
                         f"center ({fx},{fy}) not on the trunk")
    else:
        # "base": multi-support bases (bench legs, boulder clusters) put the
        # centroid BETWEEN contact patches — legitimate; require the center
        # within the contact SPAN of the bottom rows instead
        rows0 = main[max(int(fy) - 6, 0):int(fy) + 1]
        cols0 = np.nonzero(rows0.any(axis=0))[0]
        if len(cols0) == 0 or not (cols0.min() - 2 <= fx <= cols0.max() + 2):
            return Check("blocking_footprint", False, 0.0,
                         f"center ({fx},{fy}) outside the base span")
    if blocking == "trunk_base":
        # local mass half-width at the footprint rows
        rows = main[max(int(fy) - 6, 0):int(fy) + 1]
        cols = np.nonzero(rows.any(axis=0))[0]
        half = (cols.max() - cols.min()) / 2 if len(cols) else 0
        if r > half + 4:
            return Check("blocking_footprint", False, float(half / max(r, 1)),
                         f"r {r:.0f} wider than trunk half-width {half:.0f}")
        # the canopy (upper 55% of the mass) must stay clear of the circle
        ys = np.nonzero(main.any(axis=1))[0]
        canopy_limit = ys.min() + (ys.max() - ys.min()) * 0.55
        if fy - r < canopy_limit:
            return Check("blocking_footprint", False, 0.5,
                         f"circle reaches canopy zone (top {fy - r:.0f} < {canopy_limit:.0f})")
    elif blocking == "base":
        # the whole mass blocks: the circle must roughly SPAN the base —
        # neither wider than the mass nor a token dot in the middle
        rows = main[max(int(fy) - 6, 0):int(fy) + 1]
        cols = np.nonzero(rows.any(axis=0))[0]
        half = (cols.max() - cols.min()) / 2 if len(cols) else 0
        if r > half + 4:
            return Check("blocking_footprint", False, float(half / max(r, 1)),
                         f"r {r:.0f} wider than base half-width {half:.0f}")
        if half >= 8 and r < half * 0.5:
            return Check("blocking_footprint", False, float(r / max(half, 1)),
                         f"r {r:.0f} too small for base half-width {half:.0f}")
    return Check("blocking_footprint", True, 1.0,
                 f"{blocking} at ({fx:.0f},{fy:.0f}) r={r:.0f}")


def qc_frames(base_arr: np.ndarray, frame_arrs: list, pal: dict,
              lo: float = 0.02, hi: float = 0.15) -> list[Check]:
    """Animation-frame contract: same silhouette, same palette, visible but
    bounded change (a rustle, not a different asset)."""
    checks = []
    base_a = base_arr[:, :, 3]
    opaque = int((base_a > 0).sum())
    for i, f in enumerate(frame_arrs, start=1):
        same_sil = bool((f[:, :, 3] == base_a).all())
        checks.append(Check(f"frame{i}_silhouette_locked", same_sil,
                            1.0 if same_sil else 0.0,
                            "alpha identical" if same_sil else "alpha CHANGED"))
        pc = check_palette(f, pal)
        checks.append(Check(f"frame{i}_{pc.name}", pc.ok, pc.score, pc.detail))
        diff = (f[:, :, :3] != base_arr[:, :, :3]).any(axis=2) & (base_a > 0)
        frac = float(diff.sum()) / max(opaque, 1)
        checks.append(Check(f"frame{i}_change_fraction", lo <= frac <= hi,
                            frac, f"{frac:.3f} of opaque pixels changed"))
    return checks


GENERIC_CHECKS = ("crisp_alpha", "palette_membership", "single_mass", "outline",
                  "light_direction", "band_balance", "grid_alignment")


def run_qc(arr: np.ndarray, meta: dict, pal: dict, descriptor: dict) -> list[Check]:
    checks = [
        check_crisp_alpha(arr),
        check_palette(arr, pal),
        check_single_mass(arr),
        check_outline(arr),
        check_light_direction(arr, pal, descriptor),
        check_band_balance(arr, pal),
        check_grid_alignment(arr),
        check_blocking_footprint(arr, meta, descriptor),
    ]
    return checks


def qc_set(images_meta: dict, pal: dict, descriptor: dict,
           iou_max: float = 0.90, interior_min: float = 0.30) -> dict:
    """QC a whole variant set: per-asset checks + set-level distinctness."""
    report: dict = {"assets": {}, "set": [], "ok": True}
    arrs = {}
    for name, (img, meta) in images_meta.items():
        arr = np.asarray(img)
        arrs[name] = arr
        checks = run_qc(arr, meta, pal, descriptor)
        report["assets"][name] = checks
        if not all(c.ok for c in checks):
            report["ok"] = False
    names = list(arrs)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = arrs[names[i]], arrs[names[j]]
            iou = px.silhouette_iou(a[:, :, 3] > 0, b[:, :, 3] > 0)
            diff = px.interior_difference(a, b)
            ok = iou <= iou_max and diff >= interior_min
            report["set"].append(Check(f"distinct:{names[i]}~{names[j]}", ok,
                                       float(diff - iou),
                                       f"iou {iou:.2f}, interior {diff:.2f}"))
            if not ok:
                report["ok"] = False
    return report


def format_report(report: dict) -> str:
    lines = []
    for name, checks in report["assets"].items():
        bad = [c for c in checks if not c.ok]
        mark = "ok " if not bad else "FAIL"
        lines.append(f"{mark} {name}" + (
            "" if not bad else "  <- " + "; ".join(f"{c.name} ({c.detail})" for c in bad)))
    for c in report["set"]:
        if not c.ok:
            lines.append(f"FAIL {c.name}  <- {c.detail}")
    lines.append("QC: " + ("ALL PASS" if report["ok"] else "FAILURES PRESENT"))
    return "\n".join(lines)
