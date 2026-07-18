"""Procedural 2D tile atlases: the SceneCreationDirector's texture tool.

facades.py's 2D sibling. An atlas is a small grid of TILE-px tiles — one row
per tile CLASS, VARIANTS columns of deterministic variation — rendered by a
PAINTER LIBRARY executing an ATLAS SPEC. The spec is the director's
vocabulary: which classes a scene's ground speaks (a mine says earth / wall /
moss / rail; a meadow says grass / path / bush), what color each is (an
identity attribute name or a literal RGB), which mechanics flags it carries
(walkable / speed_mod / hazard), and which transition pairs blend at class
boundaries — the base of a transition is whatever the scene's floor is,
never hardcoded. Specs are committed under `games/<game>/atlases/`; the
built-in DEFAULT_SPEC is the original surface five, byte-identical to
pre-spec atlases.

The flags travel in `<name>.tiles.json` beside the PNG; the Godot scene
baker turns them into TileSet physics + custom data generically (any class
names, any transition pairs), so collision and movement rules EMERGE from
the atlas — never authored per-scene.

Determinism: every pixel derives from sha256(identity name, class, variant) —
re-runs are byte-identical, PYTHONHASHSEED-proof (str hash() is salted).
Pure numpy/PIL, network-free; a diffusion backend can fill the same
atlas+tiles.json slot later without downstream changes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

TILE = 32
VARIANTS = 4

Rgb = tuple[float, float, float]

_FLAG_DEFAULTS = {"walkable": True, "speed_mod": 1.0, "hazard": False}

# The original surface vocabulary — the default when no spec is given.
# Class order = atlas row order; `color` is an identity attribute name
# (a spec may use a literal [r, g, b] instead).
DEFAULT_SPEC: dict = {
    "classes": [
        {"name": "grass", "painter": "grass", "color": "grass_color",
         "walkable": True, "speed_mod": 1.0, "hazard": False},
        {"name": "path", "painter": "path", "color": "path_color",
         "walkable": True, "speed_mod": 1.15, "hazard": False},
        {"name": "water", "painter": "water", "color": "water_color",
         "walkable": False, "speed_mod": 1.0, "hazard": True},
        {"name": "stone", "painter": "stone", "color": "cliff_color",
         "walkable": False, "speed_mod": 1.0, "hazard": False},
        {"name": "bush", "painter": "clump", "color": "canopy_color",
         "on": "grass", "walkable": False, "speed_mod": 1.0, "hazard": False},
    ],
    "transitions": [
        {"name": "path", "base": "grass", "overlay": "path"},
        {"name": "water", "base": "grass", "overlay": "water"},
    ],
}

# Legacy views of the default vocabulary (tests + older callers).
CLASSES: dict[str, dict] = {
    c["name"]: {k: c[k] for k in ("color", "walkable", "speed_mod", "hazard")}
    for c in DEFAULT_SPEC["classes"]}
TRANSITIONS: dict[str, dict] = {
    t["name"]: {"base": t["base"], "overlay": t["overlay"]}
    for t in DEFAULT_SPEC["transitions"]}
CORNER_ORDER = ["tl", "tr", "bl", "br"]


def _rng(identity_name: str, cls: str, variant: int) -> np.random.Generator:
    digest = hashlib.sha256(f"{identity_name}:{cls}:{variant}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


def _base(color: Rgb, rng: np.random.Generator, noise: float) -> np.ndarray:
    arr = np.empty((TILE, TILE, 3), dtype=float)
    arr[:, :, 0], arr[:, :, 1], arr[:, :, 2] = color
    arr *= 1.0 + rng.uniform(-noise, noise, size=(TILE, TILE, 1))
    return arr


# ---------------------------------------------------------------- painters
# A painter renders one tile of one class. Simple painters take (color, rng);
# overlay painters (clump, rail) also take the already-painted underlay tile
# of their `on` class — the SAME rng paints underlay then overlay, so every
# tile stays a pure function of (identity, class, variant).

def _grass(color: Rgb, rng) -> np.ndarray:
    arr = _base(color, rng, 0.05)
    for _ in range(14):  # blade speckles
        x, y = int(rng.integers(0, TILE)), int(rng.integers(0, TILE - 2))
        arr[y:y + 2, x] *= float(rng.uniform(0.75, 1.3))
    return arr


def _path(color: Rgb, rng) -> np.ndarray:
    arr = _base(color, rng, 0.07)
    for _ in range(4):  # pebbles
        x, y = int(rng.integers(2, TILE - 4)), int(rng.integers(2, TILE - 4))
        arr[y:y + 2, x:x + 3] *= float(rng.uniform(1.1, 1.25))
        arr[y + 2, x:x + 3] *= 0.85
    return arr


def _water(color: Rgb, rng, frame: int = 0, frames: int = 1) -> np.ndarray:
    """Water. With frames > 1, frame k re-renders the SAME tile (same rng
    stream → same base noise) with the swell bands phase-shifted and the
    glints nudged sideways — Godot cycles the frames as tile animation.
    frame 0 is byte-identical to the static tile."""
    arr = _base(color, rng, 0.03)
    phase = float(rng.uniform(0.0, np.pi)) + 2 * np.pi * frame / max(frames, 1)
    ys = np.arange(TILE)
    band = 0.08 * np.sin(ys * 0.7 + phase) + 0.05 * np.sin(ys * 0.23 + phase * 2)
    arr *= (1.0 + band)[:, None, None]
    for _ in range(3):  # glints
        x, y = int(rng.integers(0, TILE - 5)), int(rng.integers(0, TILE))
        arr[y, (x + 2 * frame) % (TILE - 5):][:int(rng.integers(3, 6))] *= 1.25
    return arr


def _stone(color: Rgb, rng) -> np.ndarray:
    arr = _base(color, rng, 0.06)
    for _ in range(3):  # cracks
        x = float(rng.integers(4, TILE - 4))
        for y in range(TILE):
            x += float(rng.uniform(-0.8, 0.8))
            arr[y, int(np.clip(x, 1, TILE - 2))] *= 0.7
    arr[0:2, :] *= 1.15   # raised read: lit top edge,
    arr[-2:, :] *= 0.7    # shadowed bottom
    return arr


def _rock(color: Rgb, rng) -> np.ndarray:
    """Rock MASS — an area of living stone, meant to tile seamlessly.

    Unlike `stone` (a free-standing blocker that self-shades every tile,
    reading as one raised block), rock carries no per-tile lighting — a
    carved wall must read as one mass, not a grid of bricks. Edge lighting
    belongs to the boundary: give the class `"relief": "raised"` and its
    transition tiles grow a footing shadow where the mass meets the floor.
    Strata sit at fixed depths (small per-variant wander) so bedding planes
    read across neighboring tiles.
    """
    arr = _base(color, rng, 0.06)
    for y0 in (9, 22):  # bedding planes, continuous-ish across the map
        y = y0 + int(rng.integers(-1, 2))
        arr[y, :] *= 0.78
        arr[y + 1, :] *= 1.08
    for _ in range(3):  # cracks
        x = float(rng.integers(4, TILE - 4))
        for y in range(TILE):
            x += float(rng.uniform(-0.8, 0.8))
            arr[y, int(np.clip(x, 1, TILE - 2))] *= 0.7
    return arr


def _earth(color: Rgb, rng) -> np.ndarray:
    """Packed earth — a worked floor: scuffed, trodden, embedded grit."""
    arr = _base(color, rng, 0.06)
    for _ in range(5):  # scuffs: soft darker smears where feet drag
        x, y = int(rng.integers(0, TILE - 8)), int(rng.integers(0, TILE))
        arr[y, x:x + int(rng.integers(5, 10))] *= float(rng.uniform(0.85, 0.93))
    for _ in range(3):  # embedded grit, duller than a path's loose pebbles
        x, y = int(rng.integers(1, TILE - 3)), int(rng.integers(1, TILE - 2))
        arr[y, x:x + 2] *= float(rng.uniform(1.08, 1.15))
        arr[y + 1, x:x + 2] *= 0.9
    return arr


def _moss(color: Rgb, rng) -> np.ndarray:
    """Moss carpet — soft rounded clumps, lighter crowns, shaded rims."""
    arr = _base(color, rng, 0.05)
    yy, xx = np.mgrid[0:TILE, 0:TILE]
    for _ in range(6):
        cy, cx = float(rng.uniform(0, TILE)), float(rng.uniform(0, TILE))
        radius = float(rng.uniform(3.0, 6.0))
        d = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
        inside = d < radius
        arr[inside] *= float(rng.uniform(1.06, 1.16))
        arr[inside & (d > radius - 1.5)] *= 0.92
    return arr


def _flagstone(color: Rgb, rng) -> np.ndarray:
    """Dressed flagstone paving — the BUILT floor a fairground square is
    laid with (Millennial-Fair study): offset stone courses, darker
    joints, per-stone value so the surface reads worked, not flat."""
    arr = _base(color, rng, 0.04)
    sh, sw = 8, 11
    phase = int(rng.integers(0, sh))
    for k in range(-1, TILE // sh + 2):
        y0 = k * sh + phase
        off = (k % 2) * (sw // 2)
        if 0 <= y0 < TILE:
            arr[y0, :] *= 0.78                       # course joint
        for j in range(-1, TILE // sw + 2):
            x0 = j * sw + off
            v = float(rng.uniform(0.9, 1.1))         # per-stone value
            ys, ye = max(y0 + 1, 0), min(y0 + sh, TILE)
            xs, xe = max(x0, 0), min(x0 + sw - 1, TILE)
            if ys < ye and xs < xe:
                arr[ys:ye, xs:xe] *= v
                arr[ys, xs:xe] *= 1.08               # lit stone top
            if 0 <= x0 + sw - 1 < TILE and ys < ye:
                arr[ys:ye, x0 + sw - 1] *= 0.82      # vertical joint
    return arr


def _canopy(color: Rgb, rng) -> np.ndarray:
    """Treetop mass — the fair's enclosing wall of foliage: layered leaf
    clumps at two scales with dark interior holes; tiles seamlessly."""
    arr = _base(color, rng, 0.09)
    for _ in range(26):  # leaf clumps
        x, y = int(rng.integers(0, TILE - 2)), int(rng.integers(0, TILE - 2))
        arr[y:y + 2, x:x + 2] *= float(rng.uniform(0.85, 1.3))
    for _ in range(4):   # deep shadow holes between crowns
        x, y = int(rng.integers(0, TILE - 4)), int(rng.integers(0, TILE - 4))
        arr[y:y + 3, x:x + 3] *= 0.55
    for _ in range(6):   # sunlit crown tips
        x, y = int(rng.integers(0, TILE - 2)), int(rng.integers(0, TILE - 2))
        arr[y, x:x + 2] *= 1.35
    return arr


def _flowers(color: Rgb, rng, underlay: np.ndarray) -> np.ndarray:
    """A flowerbed border strip: blooms scattered over the underlay —
    the accent-color edging CT walks are lined with."""
    arr = underlay
    for _ in range(10):
        x, y = int(rng.integers(0, TILE - 1)), int(rng.integers(0, TILE - 1))
        bloom = np.array(color) * float(rng.uniform(0.85, 1.15))
        arr[y, x] = bloom
        if rng.random() < 0.5:
            arr[y, x + 1] = bloom * 0.85
    for _ in range(4):   # pale blooms for sparkle
        x, y = int(rng.integers(0, TILE)), int(rng.integers(0, TILE))
        arr[y, x] = np.clip(np.array(color) * 1.7, 0, 1)
    return arr


def _stairs(color: Rgb, rng) -> np.ndarray:
    """Stone steps — the cut through a terrace ledge (elevation v1).
    Horizontal treads: lit nosing, flat tread, dark riser, repeating."""
    arr = _base(color, rng, 0.03)
    step = 6
    phase = 0  # steps align across a stair run — no per-tile phase
    for y in range(TILE):
        k = (y + phase) % step
        if k == 0:
            arr[y, :] *= 1.22          # lit nosing
        elif k in (step - 2, step - 1):
            arr[y, :] *= 0.72          # riser in shadow
    for _ in range(3):                  # wear marks
        x, y = int(rng.integers(2, TILE - 4)), int(rng.integers(0, TILE))
        arr[y, x:x + 3] *= float(rng.uniform(0.9, 1.08))
    return arr


def _hedge(color: Rgb, rng) -> np.ndarray:
    """Clipped hedge — a CONNECTED leafy mass, meant to tile seamlessly.

    rock's tiling behavior with leaf texture: no per-tile self-shading
    (a hedge wall is one mass; its edges come from `relief: "raised"`
    transitions), dense clump speckle, a flat clipped top read via a
    subtle horizontal trim line that carries across tiles.
    """
    arr = _base(color, rng, 0.07)
    for _ in range(22):  # leaf clumps, dense
        x, y = int(rng.integers(0, TILE - 2)), int(rng.integers(0, TILE - 2))
        arr[y:y + 2, x:x + 2] *= float(rng.uniform(0.8, 1.25))
    y_trim = 6 + int(rng.integers(-1, 2))   # the clipped-top line
    arr[y_trim, :] *= 1.12
    arr[y_trim + 1, :] *= 0.9
    return arr


def _clump(color: Rgb, rng, underlay: np.ndarray) -> np.ndarray:
    """A rounded mass (bush, fungus cluster) sitting on its underlay class."""
    arr = underlay
    cy, cx = TILE / 2 + float(rng.uniform(-2, 2)), TILE / 2 + float(rng.uniform(-2, 2))
    yy, xx = np.mgrid[0:TILE, 0:TILE]
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    radius = 12.0 + float(rng.uniform(-1.5, 1.5))
    inside = r < radius
    canopy = np.empty_like(arr)
    canopy[:, :, 0], canopy[:, :, 1], canopy[:, :, 2] = color
    canopy *= 1.0 + rng.uniform(-0.08, 0.08, size=(TILE, TILE, 1))
    rim = (r >= radius - 2.5) & inside
    canopy[rim] *= 0.7
    arr[inside] = canopy[inside]
    for _ in range(5):  # highlights
        x, y = int(rng.integers(0, TILE)), int(rng.integers(0, TILE))
        if r[y, x] < radius - 3:
            arr[y, x] *= 1.3
    return arr


def _rail(color: Rgb, rng, underlay: np.ndarray, orientation: str = "v") -> np.ndarray:
    """A rail pair + sleepers over the underlay; tiles connect along the run.

    `orientation` "v" (rails run top-bottom) or "h" (left-right). The rail
    head catches light on one side, drops shadow on the other; sleepers are
    darker wood bars. Deterministic sleeper phase keeps adjacent tiles from
    visibly repeating without breaking the line read.
    """
    arr = underlay
    a = arr if orientation == "v" else arr.transpose(1, 0, 2)
    rgb = np.asarray(color, dtype=float)
    sleeper = rgb * 0.5
    for y in range(int(rng.integers(0, 6)), TILE, 6):
        a[y:y + 2, 5:TILE - 5] = sleeper * float(rng.uniform(0.92, 1.05))
    for x in (9, 21):  # the gauge
        a[:, x] = rgb * 0.45       # web in shadow
        a[:, x + 1] = rgb * 1.3    # lit rail head
    return arr


PAINTERS = {"grass": _grass, "path": _path, "water": _water, "stone": _stone,
            "rock": _rock, "earth": _earth, "moss": _moss, "hedge": _hedge,
            "flagstone": _flagstone, "canopy": _canopy, "stairs": _stairs}
OVERLAY_PAINTERS = {"clump": _clump, "rail": _rail, "flowers": _flowers}


def _color(spec_color, get) -> Rgb:
    if isinstance(spec_color, str):
        return tuple(get(spec_color, (0.5, 0.5, 0.5)))
    return tuple(spec_color)


# painters that can render phase-shifted animation frames
ANIMATED_PAINTERS = {"water"}


def _render(cspec: dict, by_name: dict, get, rng,
            frame: int = 0, frames: int = 1) -> np.ndarray:
    """Render one tile of a spec class (recursing into its `on` underlay)."""
    rgb = _color(cspec["color"], get)
    painter = cspec["painter"]
    if painter in OVERLAY_PAINTERS:
        on = by_name[cspec.get("on", "grass")]
        underlay = _render(on, by_name, get, rng)
        return OVERLAY_PAINTERS[painter](rgb, rng, underlay,
                                         **cspec.get("args", {}))
    if painter in ANIMATED_PAINTERS:
        return PAINTERS[painter](rgb, rng, frame=frame, frames=frames)
    return PAINTERS[painter](rgb, rng)


# Terrain transition pairs: 16-tile corner-match sets (marching-squares style)
# appended below the class rows. Each tile's mask says which of its four
# corners belong to the OVERLAY terrain (bit order: TL, TR, BL, BR); the
# boundary is the 0.5 iso-contour of the bilinear corner field, perturbed by
# noise for an organic edge, with a darkened rim so the blend reads.
# Mechanics: transition tiles carry the BASE class flags (a path edge or a
# lapping shoreline is stood on grass; the overlay's own cells keep their
# full-tile mechanics, so water interiors still block).

def _transition_tile(base: np.ndarray, overlay: np.ndarray, mask: int,
                     rng: np.random.Generator, relief: str = "flat") -> np.ndarray:
    # bilinear field over the tile from corner occupancy (1 = overlay)
    c_tl, c_tr, c_bl, c_br = [(mask >> i) & 1 for i in range(4)]
    u = (np.arange(TILE) + 0.5) / TILE
    uu, ww = np.meshgrid(u, u)  # ww rows (y), uu cols (x)
    f = (c_tl * (1 - uu) * (1 - ww) + c_tr * uu * (1 - ww)
         + c_bl * (1 - uu) * ww + c_br * uu * ww)
    # a dressed curb runs straight; organic blends wander
    amp = 0.03 if relief == "curb" else 0.09
    f = f + rng.uniform(-amp, amp, size=f.shape)
    out = base.copy()
    inside = f > 0.5
    out[inside] = overlay[inside]
    rim = inside & (f < 0.58)
    out[rim] *= 0.82
    if relief == "curb":
        # an ARCHITECTURAL edge (Millennial-Fair study): a dressed stone
        # curb runs the boundary instead of an organic blend — the crisp
        # edging line between a paved square and its lawn islands
        curb = np.abs(f - 0.5) <= 0.14
        out[curb] = np.array([0.62, 0.59, 0.53])[None, :] \
            * (1.0 + rng.uniform(-0.06, 0.06, size=(int(curb.sum()), 1)))
        seam = np.abs(f - 0.5) <= 0.04
        out[seam] *= 0.8
        lit = curb & (f > 0.5) & (np.abs(f - 0.5) > 0.09)
        out[lit] *= 1.12
        return out
    if relief == "raised":
        # the overlay is a MASS standing on the base: a footing shadow on
        # the floor hugging the contour (what sells "carved from rock"),
        # and a lit crest just inside it
        footing = ~inside & (f > 0.32)
        out[footing] *= 0.72
        crest = inside & (f >= 0.58) & (f < 0.68)
        out[crest] *= 1.12
    if relief == "ledge":
        # ELEVATION v1: the overlay is a raised terrace — a masonry drop
        # face rings it on the base side, deep shadow at its foot, a lit
        # lip on the terrace edge. The pair usually also sets
        # `blocks: true` so the baker walls the boundary; stairs cells
        # interrupt the pair and become the way up.
        face = ~inside & (f > 0.26)
        out[face] = overlay[face] * 0.7
        joints = face & (np.arange(TILE)[None, :] % 6 < 1)
        out[joints] *= 0.8
        foot = ~inside & (f > 0.18) & (f <= 0.26)
        out[foot] *= 0.62
        lip = inside & (f < 0.62)
        out[lip] *= 1.15
    return out


def build_atlas(identity, *, mechanics: dict | None = None,
                spec: dict | None = None) -> tuple[Image.Image, dict]:
    """Render the atlas + its tiles.json metadata dict.

    `identity` is a VisualIdentity or a plain dict (the identity file form).
    `spec` is the atlas vocabulary (classes + transitions); DEFAULT_SPEC —
    the surface five — when omitted.
    `mechanics` overrides per-class flags — the game-mechanics parameter:
    e.g. {"water": {"walkable": True}} for a game with swimming.
    """
    get = (lambda k, d: getattr(identity, k, d)) if not isinstance(identity, dict) \
        else (lambda k, d: identity.get(k, d))
    name = str(get("name", "identity"))
    spec = spec or DEFAULT_SPEC
    classes: list[dict] = spec["classes"]
    transitions: list[dict] = spec.get("transitions", [])
    by_name = {c["name"]: c for c in classes}

    # animated classes pack frames as ADJACENT columns (variant v, frame k
    # at column v*frames+k) — Godot's native tile-animation layout, so the
    # baker just sets the frame count on each variant tile. Transition
    # tiles stay static (known gap: an animated pool's rim doesn't move).
    def _frames(c: dict) -> int:
        return int(c.get("animation", {}).get("frames", 1))
    max_frames = max([1] + [_frames(c) for c in classes])

    n_rows = len(classes) + 4 * len(transitions)
    sheet = np.zeros((TILE * n_rows, TILE * VARIANTS * max_frames, 3), dtype=float)
    meta: dict = {"schema": "tiles/1.2" if max_frames > 1 else "tiles/1.1",
                  "tile_size": TILE, "variants": VARIANTS,
                  "identity": name, "classes": {}, "transitions": {},
                  "corner_order": CORNER_ORDER}
    for row, cspec in enumerate(classes):
        cls = cspec["name"]
        n_fr = _frames(cspec)
        for v in range(VARIANTS):
            for k in range(n_fr):
                rng = _rng(name, cls, v)  # same seed per frame: only the
                col = v * n_fr + k        # phase moves, never the tile
                sheet[row * TILE:(row + 1) * TILE, col * TILE:(col + 1) * TILE] = \
                    _render(cspec, by_name, get, rng, frame=k, frames=n_fr)
        flags = {k: cspec.get(k, d) for k, d in _FLAG_DEFAULTS.items()}
        flags.update((mechanics or {}).get(cls, {}))
        meta["classes"][cls] = {"row": row, **flags}
        if n_fr > 1:
            meta["classes"][cls]["frames"] = n_fr

    row_cursor = len(classes)
    for tspec in transitions:
        pair = tspec["name"]
        base_spec, over_spec = by_name[tspec["base"]], by_name[tspec["overlay"]]
        for mask in range(16):
            rng = _rng(name, f"trans:{pair}", mask)
            base_tile = _render(base_spec, by_name, get, rng)
            over_tile = _render(over_spec, by_name, get, rng)
            tile = _transition_tile(base_tile, over_tile, mask, rng,
                                    relief=over_spec.get("relief", "flat"))
            row = row_cursor + mask // VARIANTS
            col = mask % VARIANTS
            sheet[row * TILE:(row + 1) * TILE, col * TILE:(col + 1) * TILE] = tile
        meta["transitions"][pair] = {
            "base": tspec["base"], "overlay": tspec["overlay"],
            "start_row": row_cursor,
            "masks": 16,
            # a blocking pair (terrace ledges) walls its boundary tiles;
            # stairs cells interrupt the pair and stay open
            **({"blocks": True} if tspec.get("blocks") else {}),
        }
        row_cursor += 4

    img = Image.fromarray((np.clip(sheet, 0.0, 1.0) * 255).astype(np.uint8), "RGB")
    return img, meta


def write_atlas(out_base: Path, identity, *, mechanics: dict | None = None,
                spec: dict | None = None) -> dict:
    """Write <out_base>.png + <out_base>.tiles.json; returns the metadata."""
    img, meta = build_atlas(identity, mechanics=mechanics, spec=spec)
    out_base.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_base.with_suffix(".png"))
    meta["atlas"] = out_base.with_suffix(".png").name
    out_base.with_suffix(".tiles.json").write_text(json.dumps(meta, indent=2) + "\n")
    return meta
