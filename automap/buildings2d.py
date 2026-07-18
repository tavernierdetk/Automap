"""Buildings: the classic RPG top-down building look, assembled from pieces.

The 2D counterpart of facades.py's storey-tile idea, restated as pixel art:
a building is FACADE (plaster field, window bays, a door, a stone
foundation) under a CORNICE strip under a ROOF mass (tile courses with a
ridge, hip seams or an awning of canvas stripes) — the Pokémon/Stardew
grammar. The pieces are painter functions; `assemble()` composes them from
a small parameter dict; `PREFABS` are the standard basic builds ("the most
basic build of one of those buildings") — variant 0 of every substyle IS
its prefab, verbatim.

A building ships as ONE whole multi-cell prop (family "building") through
the ordinary asset pipeline — catalog, QC gate, paintable tile atlas — so
y-sorting at the facade base line and editor repainting come free. Its
blocking is a RECT footprint (`{"kind": "rect", "center", "half"}`)
spanning the facade, emitted from known geometry (the assembler placed
every wall pixel) and still verified against pixels by asset_qc. The door
position rides the catalog meta (`door: [x, y]`) so a later slice can drop
an interior teleport exactly on it.

Like every procedural painter here: (material, band) index maps resolved
through the master palette, sel-out outline, fixed top-left key light,
sha-seeded determinism (STYLE_TOKEN "bld1"). No ground shadow — a building
meets the ground with a contact line, not a dither ellipse.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from automap import pixelart as px

STYLE_TOKEN = "bld1"

# vertical recipe (px)
_WALL_H = 38          # one storey of wall
_FOUNDATION_H = 4     # stone base course
_CORNICE_H = 6
_ROOF_INSET = 3       # walls sit inset; the roof overhangs to the canvas edge

# the standard basic builds — variant 0 of each substyle is exactly this
PREFABS: dict[str, dict] = {
    "house": {"cells_w": 3, "storeys": 1, "roof": "hip", "roof_cells": 2,
              "door": "center", "chimney": True, "shutters": True,
              "wall_material": "plaster", "roof_material": "rooftile",
              "trim_material": "wood"},
    "kiosk": {"cells_w": 2, "storeys": 1, "roof": "awning", "roof_cells": 1,
              "door": None, "chimney": False,
              "wall_material": "wood", "roof_material": "canvas",
              "trim_material": "wood"},
    "pavilion": {"cells_w": 5, "storeys": 1, "roof": "awning",
                 "roof_cells": 2, "door": "center", "chimney": False,
                 "wall_material": "plaster", "roof_material": "canvas",
                 "trim_material": "wood"},
    # the town batch: SHOPFRONT read (display window + awning band) and a
    # two-storey inn — the SNES-town grammar (vaporis_town brief)
    "shop": {"cells_w": 4, "storeys": 1, "roof": "gable", "roof_cells": 2,
             "door": 2, "chimney": False, "storefront": True,
             "wall_material": "plaster", "roof_material": "rooftile",
             "trim_material": "wood"},
    "inn": {"cells_w": 5, "storeys": 2, "roof": "hip", "roof_cells": 2,
            "door": "center", "chimney": True, "shutters": True,
            "dormer": True,
            "wall_material": "plaster", "roof_material": "roofslate",
            "trim_material": "wood"},
}


def _geometry(params: dict) -> dict:
    w_px = int(params["cells_w"]) * 32
    wall_h = int(params.get("storeys", 1)) * _WALL_H + _FOUNDATION_H
    roof_h = int(params.get("roof_cells", 2)) * 32
    # +3: bottom margin so the sel-out ring fits BELOW the base — flush
    # against the canvas edge it would wrap to row 0 (roll-based dilate)
    total = roof_h + _CORNICE_H + wall_h + 3
    h_px = ((total + 31) // 32) * 32
    top = h_px - total  # transparent sky rows (chimney may poke into them)
    return {"w": w_px, "h": h_px, "roof_y": top, "roof_h": roof_h,
            "cornice_y": top + roof_h, "wall_y": top + roof_h + _CORNICE_H,
            "wall_h": wall_h, "base_y": h_px - 4,
            "storeys": int(params.get("storeys", 1))}


def _wall_field(material, band, g, idx, stone_idx, rng) -> None:
    x0, x1 = _ROOF_INSET, g["w"] - _ROOF_INSET
    y0, y1 = g["wall_y"], g["base_y"] + 1
    material[y0:y1, x0:x1] = idx
    band[y0:y1, x0:x1] = 2
    # weathering speckle, quiet
    sp = rng.random((y1 - y0, x1 - x0)) < 0.05
    band[y0:y1, x0:x1][sp] = 1
    # value structure (the CT read): deep eave shade at the top, light
    # catching the lower wall, a lit left rim
    band[y0, x0:x1] = 0
    band[y0 + 1:y0 + 3, x0:x1] = 1
    lower = band[y1 - _FOUNDATION_H - 6:y1 - _FOUNDATION_H, x0:x1]
    lower[lower == 2] = 3
    band[y0:y1, x0:x0 + 2] = 3            # lit left rim
    # corner quoins: alternating stone blocks up both wall corners
    qh = 6
    for i, qy in enumerate(range(y1 - _FOUNDATION_H - qh, y0 + 2, -qh)):
        qw = 4 if i % 2 == 0 else 3
        for qx0 in (x0, x1 - qw):
            material[qy:qy + qh - 1, qx0:qx0 + qw] = stone_idx
            band[qy:qy + qh - 1, qx0:qx0 + qw] = 3 if i % 2 == 0 else 2
            band[qy + qh - 2, qx0:qx0 + qw] = 1
    fy = y1 - _FOUNDATION_H                # stone foundation course
    material[fy:y1, x0:x1] = stone_idx
    band[fy:y1, x0:x1] = 2
    for x in range(x0 + int(rng.integers(0, 5)), x1, 9):
        band[fy:y1 - 1, x] = 1             # foundation block joints
    band[y1 - 1, x0:x1] = 0                # ground contact line


def _timbered(material, band, g, wood_idx, rng) -> None:
    """Dark beams over the plaster field — the medieval half-timber read."""
    x0, x1 = _ROOF_INSET, g["w"] - _ROOF_INSET
    y0 = g["wall_y"]
    y1 = g["base_y"] + 1 - _FOUNDATION_H
    for x in range(x0, x1 + 1, 32):          # posts at every bay border
        bx = int(np.clip(x, x0, x1 - 2))
        material[y0:y1, bx:bx + 2] = wood_idx
        band[y0:y1, bx:bx + 2] = 1
        band[y0:y1, bx:bx + 1] = 2
    for s in range(int(g["storeys"])):        # a rail under each storey
        ry = y0 + (s + 1) * _WALL_H - 4
        if ry < y1:
            material[ry:ry + 2, x0:x1] = wood_idx
            band[ry:ry + 2, x0:x1] = 1


def _storefront(material, band, g, door_cell, trim_idx, stone_idx,
                canvas_idx, rng) -> None:
    """The shop read: a wide display window beside the door, a striped
    awning band across the facade under the cornice."""
    y_ground = g["wall_y"] + (g["storeys"] - 1) * _WALL_H
    # display window: spans the bays left of the door
    wx0 = _ROOF_INSET + 5
    wx1 = door_cell * 32 - 6
    if wx1 - wx0 >= 14:
        wy0, wy1 = y_ground + 8, y_ground + 28
        material[wy0:wy1, wx0:wx1] = trim_idx
        band[wy0:wy1, wx0:wx1] = 3
        material[wy0 + 2:wy1 - 3, wx0 + 2:wx1 - 2] = stone_idx
        band[wy0 + 2:wy1 - 3, wx0 + 2:wx1 - 2] = 0
        band[wy0 + 2, wx0 + 2:wx1 - 2] = 4          # glass glint line
        mull = (wx0 + wx1) // 2                     # center mullion
        material[wy0:wy1, mull:mull + 2] = trim_idx
        band[wy0:wy1, mull:mull + 2] = 3
    # awning band across the facade, scalloped
    ax0, ax1 = _ROOF_INSET, g["w"] - _ROOF_INSET
    ay0 = g["wall_y"] + 1
    ay1 = ay0 + 7
    material[ay0:ay1, ax0:ax1] = canvas_idx
    for x in range(ax0, ax1, 8):
        band[ay0:ay1, x:x + 4] = 4
        band[ay0:ay1, x + 4:x + 8] = 1
    band[ay1 - 1, ax0:ax1] = 0                      # shadow under the lip
    for x in range(ax0 + 6, ax1 - 2, 8):            # scallop
        material[ay1 - 2:ay1, x:x + 2] = 0
        band[ay1 - 2:ay1, x:x + 2] = 0


def _window_bay(material, band, g, cell, trim_idx, stone_idx, rng,
                state: str, wy0_row: int | None = None,
                shutter_idx: int | None = None) -> None:
    cx = cell * 32 + 16  # bay centered in its facade cell
    wy0 = g["wall_y"] + 10 if wy0_row is None else wy0_row
    wx0 = cx - 6
    wx1, wy1 = cx + 6, wy0 + 14
    material[wy0:wy1, wx0:wx1] = trim_idx      # frame
    band[wy0:wy1, wx0:wx1] = 3
    band[wy1 - 1, wx0:wx1] = 1                 # sill shadow
    material[wy1, wx0 - 1:wx1 + 1] = stone_idx  # protruding stone sill
    band[wy1, wx0 - 1:wx1 + 1] = 4
    gx0, gy0, gx1, gy1 = wx0 + 2, wy0 + 2, wx1 - 2, wy1 - 3
    material[gy0:gy1, gx0:gx1] = stone_idx     # glass reads dark neutral
    band[gy0:gy1, gx0:gx1] = 0 if state != "lit" else 3
    if state == "shuttered":
        material[gy0:gy1, gx0:gx1] = trim_idx
        band[gy0:gy1, gx0:gx1] = 1
        for x in range(gx0, gx1, 2):           # shutter slats
            band[gy0:gy1, x] = 2
    elif state != "lit":
        band[gy0, gx0] = 4                     # one glint (stone top band)
    if shutter_idx is not None:                 # colored shutters (CT read)
        for sx0 in (wx0 - 3, wx1):
            material[wy0:wy1 - 1, sx0:sx0 + 3] = shutter_idx
            band[wy0:wy1 - 1, sx0:sx0 + 3] = 2
            band[wy0 + 1:wy1 - 2, sx0 + 1] = 1  # slat groove
            band[wy0, sx0:sx0 + 3] = 3


def _door(material, band, g, cx, trim_idx, stone_idx, rng) -> int:
    dw, dh = 16, 27
    x0, x1 = cx - dw // 2, cx + dw // 2
    y1 = g["base_y"] + 1 - _FOUNDATION_H
    y0 = y1 - dh
    # stone frame around an ARCHED wood door (the CT doorway)
    material[y0 - 2:y1, x0 - 2:x1 + 2] = stone_idx
    band[y0 - 2:y1, x0 - 2:x1 + 2] = 3
    band[y0 - 2, x0 - 2:x1 + 2] = 4              # lit arch crown
    material[y0:y1, x0:x1] = trim_idx
    band[y0:y1, x0:x1] = 1
    for corner in (0, 1):                        # rounded top corners
        xx = x0 if corner == 0 else x1 - 2
        material[y0:y0 + 2, xx:xx + 2] = stone_idx
        band[y0:y0 + 2, xx:xx + 2] = 3
    for x in range(x0 + 2, x1 - 1, 4):           # plank lines
        band[y0 + 3:y1, x] = 2
    band[y0 + 2, x0 + 2:x1 - 2] = 3              # lintel light under arch
    band[y0 + 8, x0 + 1:x1 - 1] = 0              # crossbar shadow
    # two-step stone stoop, wider than the door
    material[y1:y1 + _FOUNDATION_H, x0 - 3:x1 + 3] = stone_idx
    band[y1:y1 + 2, x0 - 3:x1 + 3] = 4
    band[y1 + 2:y1 + _FOUNDATION_H, x0 - 3:x1 + 3] = 2
    return cx


def _cornice(material, band, g, trim_idx) -> None:
    y0, y1 = g["cornice_y"], g["cornice_y"] + _CORNICE_H
    material[y0:y1, :] = trim_idx
    band[y0:y1, :] = 2
    band[y0, :] = 4          # lit top edge
    band[y1 - 1, :] = 0      # shadowed underside


def _roof(material, band, g, style, idx, rng) -> None:
    y0, y1 = g["roof_y"], g["roof_y"] + g["roof_h"]
    w = g["w"]
    for y in range(y0, y1):
        t = (y - y0) / max(g["roof_h"] - 1, 1)
        if style == "hip":
            # trapezoid: narrow at the ridge, full at the eave
            half = int((w / 2 - 4) * (0.45 + 0.55 * t)) + 2
        else:
            half = w // 2
        x0, x1 = w // 2 - half, w // 2 + half
        material[y, x0:x1] = idx
        band[y, x0:x1] = 2
    if style == "awning":
        for x in range(0, w, 8):                 # canvas stripes
            band[y0:y1, x:x + 4] = np.where(
                material[y0:y1, x:x + 4] == idx, 4,
                band[y0:y1, x:x + 4])
        for x in range(4, w, 8):
            band[y0:y1, x:x + 4] = np.where(
                material[y0:y1, x:x + 4] == idx, 1,
                band[y0:y1, x:x + 4])
        for x in range(0, w, 8):                 # scalloped valance
            material[y1 - 2:y1, x + 6:x + 8] = 0
            band[y1 - 2:y1, x + 6:x + 8] = 0
    else:
        # SHINGLED slope (the CT roof): brick-offset shingle cells, each
        # course separated by a dark line, every shingle catching light on
        # its top edge; the eave flares wide and bright at the lip
        course, sh_w = 5, 7
        phase = int(rng.integers(0, course))
        for y in range(y0, y1):
            k = (y - y0 + phase) % course
            row = material[y] == idx
            if k == 0:
                band[y][row] = 1                 # course separation
            elif k == 1:
                band[y][row] = 3                 # shingle tops catch light
            off = ((y - y0 + phase) // course % 2) * (sh_w // 2)
            if k != 0:
                for x in range((off + int(y0)) % sh_w, w, sh_w):
                    if material[y, x] == idx:    # vertical shingle joints
                        band[y, x] = 1
        band[y0:y0 + 2][material[y0:y0 + 2] == idx] = 4   # ridge cap
        under = material[y0 + 2] == idx
        band[y0 + 2][under] = 0                            # cap shadow line
        # eave flare: the lip widens and brightens, hard shadow beneath
        for ey in (y1 - 2, y1 - 1):
            row = material[ey] == idx
            xs = np.nonzero(row)[0]
            if len(xs):
                x_lo = max(int(xs.min()) - 1, 0)
                x_hi = min(int(xs.max()) + 2, w)
                material[ey, x_lo:x_hi] = idx
                band[ey, x_lo:x_hi] = 4 if ey == y1 - 2 else 1
        if style == "hip":                        # hip seams, dark diagonals
            for y in range(y0, y1):
                t = (y - y0) / max(g["roof_h"] - 1, 1)
                half = int((w / 2 - 4) * (0.45 + 0.55 * t)) + 2
                for e in (w // 2 - half, w // 2 + half - 1):
                    if material[y, e] == idx:
                        band[y, e] = 0
    # key light: left side lit, right side shaded
    left = material[y0:y1, :3] == idx
    band[y0:y1, :3][left] = np.minimum(band[y0:y1, :3][left] + 1, 4)
    right = material[y0:y1, -3:] == idx
    band[y0:y1, -3:][right] = np.maximum(
        band[y0:y1, -3:][right].astype(int) - 1, 0).astype(band.dtype)


def _dormer(material, band, g, roof_idx, wall_idx, trim_idx, stone_idx,
            rng) -> None:
    """A gabled dormer window breaking the front slope (CT skyline)."""
    cx = g["w"] // 2 + int(rng.integers(-g["w"] // 6, g["w"] // 6 + 1))
    dw, dh = 16, 18
    y1 = g["roof_y"] + g["roof_h"] - 4           # sits above the eave
    y0 = max(y1 - dh, g["roof_y"] + 3)
    x0, x1 = cx - dw // 2, cx + dw // 2
    material[y0 + 4:y1, x0:x1] = wall_idx        # dormer face
    band[y0 + 4:y1, x0:x1] = 3
    material[y0 + 7:y1 - 1, x0 + 4:x1 - 4] = stone_idx   # its window
    band[y0 + 7:y1 - 1, x0 + 4:x1 - 4] = 0
    band[y0 + 7, x0 + 4] = 4
    for i in range(4):                            # little gable cap
        material[y0 + i, x0 + 4 - i:x1 - 4 + i] = roof_idx
        band[y0 + i, x0 + 4 - i:x1 - 4 + i] = 4 if i == 0 else 2
    band[y0 + 3, x0 + 1:x1 - 1] = 0               # cap shadow


def _chimney(material, band, g, stone_idx, rng) -> None:
    cx = g["w"] * 2 // 3
    y1 = g["roof_y"] + 4
    y0 = max(g["roof_y"] - 10, 0)
    material[y0:y1, cx:cx + 8] = stone_idx
    band[y0:y1, cx:cx + 8] = 2
    band[y0, cx:cx + 8] = 3                      # cap
    band[y0:y1, cx + 6:cx + 8] = 1               # shaded side


def _selout(material, band, names) -> None:
    """Sel-out ring: outline hue of the touched material (repixel's rule)."""
    mask = material > 0
    ring = px.outer_ring(mask)
    n_mat = len(names) + 1
    ring_mat = np.zeros(mask.shape, np.uint8)
    for idx in sorted(names):
        near = px.dilate(material == idx)
        ring_mat = np.where(ring & near & (ring_mat == 0),
                            n_mat + idx, ring_mat).astype(np.uint8)
    for idx, mat in list(names.items()):
        names[n_mat + idx] = f"outline:{mat}"
    material[ring_mat > 0] = ring_mat[ring_mat > 0]
    band[ring_mat > 0] = 0


def assemble(pal: dict, params: dict, seed_key: str
             ) -> tuple[Image.Image, dict]:
    """One building from its parameter dict. Deterministic per seed_key."""
    rng = px.rng_for(seed_key)
    g = _geometry(params)
    wall_m = params.get("wall_material", "plaster")
    roof_m = params.get("roof_material", "rooftile")
    trim_m = params.get("trim_material", "wood")
    wanted = [wall_m, roof_m, trim_m, "stone"]
    if params.get("storefront") or params.get("shutters"):
        wanted.append("canvas")
    mats = []
    for m in wanted:
        if m not in mats:
            mats.append(m)
    missing = [m for m in mats if m not in pal["materials"]]
    if missing:
        raise ValueError(f"identity lacks materials {missing}")
    names = {i + 1: m for i, m in enumerate(mats)}
    by_name = {m: i for i, m in names.items()}
    wall_i, roof_i = by_name[wall_m], by_name[roof_m]
    trim_i, stone_i = by_name[trim_m], by_name["stone"]

    material = np.zeros((g["h"], g["w"]), np.uint8)
    band = np.zeros((g["h"], g["w"]), np.uint8)

    _wall_field(material, band, g, wall_i, stone_i, rng)
    if params.get("wall_style") == "timbered":
        _timbered(material, band, g, trim_i, rng)
    door = params.get("door")
    cells = list(range(int(params["cells_w"])))
    door_px = None
    if door is not None:
        door_cell = len(cells) // 2 if door == "center" else int(door)
        door_px = [door_cell * 32 + 16, g["base_y"]]
        _door(material, band, g, door_px[0], trim_i, stone_i, rng)
    else:
        door_cell = None
    states = params.get("windows", "auto")
    storefront_cells = set()
    if params.get("storefront") and door_cell is not None:
        storefront_cells = set(range(door_cell))   # display window's bays
    for s in range(g["storeys"]):
        wy0 = g["wall_y"] + s * _WALL_H + 10
        ground = s == g["storeys"] - 1
        for c in cells:
            if ground and (c == door_cell or c in storefront_cells):
                continue
            state = states[c] if isinstance(states, (list, tuple)) else \
                ("shuttered" if rng.random() < 0.25 else "plain")
            _window_bay(material, band, g, c, trim_i, stone_i, rng, state,
                        wy0_row=wy0,
                        shutter_idx=by_name.get("canvas")
                        if params.get("shutters") else None)
    if params.get("storefront") and door_cell is not None:
        _storefront(material, band, g, door_cell, trim_i, stone_i,
                    by_name["canvas"], rng)
    _cornice(material, band, g, trim_i)
    _roof(material, band, g, params.get("roof", "hip"), roof_i, rng)
    if params.get("dormer") and params.get("roof") != "awning":
        _dormer(material, band, g, roof_i, wall_i, trim_i, stone_i, rng)
    if params.get("chimney"):
        _chimney(material, band, g, stone_i, rng)
    _selout(material, band, names)

    img = px.resolve(material, band, pal, names)
    anchor_y = int(np.nonzero(material.any(axis=1))[0].max())
    block_h = g["wall_h"] + _CORNICE_H
    half = [g["w"] / 2 - _ROOF_INSET, block_h / 2.0]
    meta = {
        "anchor_y": anchor_y,
        "collision_r": round(max(half), 1),   # legacy circle fallback bound
        "footprint": {"kind": "rect",
                      "center": [g["w"] / 2.0, anchor_y - block_h / 2.0],
                      "half": [round(half[0], 1), round(half[1], 1)]},
        "door": door_px,
        "size_px": [g["w"], g["h"]],
        "maps": (material, band, names),
    }
    return img, meta


def _jitter(prefab: dict, rng) -> dict:
    """Variant params: the prefab's family resemblance, never its clone."""
    p = dict(prefab)
    p["cells_w"] = int(np.clip(prefab["cells_w"] + rng.integers(-1, 2), 2, 8))
    if prefab.get("door") is not None and p["cells_w"] >= 3:
        lo = 2 if prefab.get("storefront") else 0   # keep the display bays
        p["door"] = int(rng.integers(lo, p["cells_w"]))
    if prefab.get("chimney") is not None:
        p["chimney"] = bool(rng.random() < 0.5)
    if prefab.get("roof") == "hip" and rng.random() < 0.3:
        p["roof"] = "gable"
    if prefab.get("roof") != "awning":              # town variety (CT read)
        if rng.random() < 0.4:
            p["wall_style"] = "timbered"
        r = rng.random()                             # tri-color rooflines:
        if r < 0.25:                                 # terracotta / slate /
            p["roof_material"] = "roofslate"         # verdigris copper
        elif r < 0.4:
            p["roof_material"] = "verdigris"
        p["dormer"] = bool(rng.random() < 0.4)
        p["shutters"] = bool(rng.random() < 0.6)
    return p


def build_set(pal: dict, identity_name: str, substyle: str, count: int,
              start_variant: int = 0, iou_max: float = 0.97,
              interior_min: float = 0.18
              ) -> dict[str, tuple[Image.Image, dict]]:
    """`count` variants; variant 0 IS the prefab (the standard basic build)."""
    if substyle not in PREFABS:
        raise ValueError(f"unknown building substyle '{substyle}' "
                         f"(have {list(PREFABS)})")
    out: dict[str, tuple[Image.Image, dict]] = {}
    accepted: list[tuple[np.ndarray, np.ndarray]] = []
    for i in range(count):
        v = start_variant + i
        best = None
        for retry in range(5):
            key = f"{identity_name}:building:{substyle}:{v}:{STYLE_TOKEN}" + \
                  (f":retry{retry}" if retry else "")
            params = PREFABS[substyle] if v == 0 else \
                _jitter(PREFABS[substyle], px.rng_for(key, "params"))
            img, meta = assemble(pal, params, key)
            mask = np.asarray(img)[:, :, 3] > 0
            arr = np.asarray(img)
            worst_iou = max((px.silhouette_iou(mask, m)
                             for m, _ in accepted), default=0.0)
            worst_diff = min((px.interior_difference(arr, a)
                              for _, a in accepted), default=1.0)
            score = worst_iou + (interior_min - min(worst_diff, interior_min))
            if best is None or score < best[0]:
                best = (score, img, meta, mask)
            if (worst_iou <= iou_max and worst_diff >= interior_min) or v == 0:
                break
        _, img, meta, mask = best
        accepted.append((mask, np.asarray(img)))
        out[f"{substyle}_{v}"] = (img, meta)
    return out
