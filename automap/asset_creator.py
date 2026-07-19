"""Asset Creator: resolve against the game's asset base, generate only the gap.

The resolver reads the game's LIVE catalog (content/props/props.json) and
judges fitness per family — for variety families like trees, fitness means
"enough distinct variants of the right style", never "one exists":

- an entry fits a request iff family, identity and substyle match AND its
  style is the current generator token (trees_px.STYLE_TOKEN) OR its
  provenance is "manual" — an artist's touch-up IS the right asset;
- legacy props/1.0 blob entries carry no family/style and never fit —
  superseding them is the point.

The creator generates only the missing count, seeds continuing from the
highest existing variant index, and stages to work/game/<game>/props/ where
stage 12 publishes with the hash guard (hand-edited files are never
overwritten). Recipes — the requests themselves — live committed at
games/<game>/asset_requests.json, so `PRODUCE=1` CI regenerates everything
from text.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from automap import pixelart, trees_px

CATALOG_SCHEMA = "props/1.1"

# family -> request defaults + the fitness rule inputs
# Each family carries a DESCRIPTOR — its conceptual contract. `blocking`
# names the blocking element (QC verifies the emitted footprint against the
# pixels): a tree blocks at its TRUNK BASE; the canopy never blocks.
FAMILIES: dict[str, dict] = {
    "tree": {
        "generator": "trees_px",
        "substyles": ("deciduous", "pine", "dead"),
        "default_min_variants": 4,
        # accepted style tokens: procedural (px3) or genlab (gen1) — plus
        # provenance "manual", which always fits (an artist's touch-up IS
        # the right asset)
        "style_tokens": {"px3", "gen1"},
        "tileset": True,          # published as a paintable tile atlas
        # master-palette materials this family may resolve to (genlab
        # palettizes references over exactly these)
        "materials": ("foliage", "foliage_dark", "wood"),
        "descriptor": {
            "blocking": "trunk_base",
            "texture_motifs": "leaf clumps, bark streaks", "anchor": "trunk",
                       "perspective": "high_front",
            "shadow": "dither_ellipse",
        },
        # per-size-class canvases on the 32px grid (w, h)
        "sizes": {"large": (96, 128), "medium": (64, 96), "small": (32, 64)},
        # frame variations: which materials may move, everything else —
        # silhouette, outline, trunk, footprint — is LOCKED per frame
        "animation": {"kind": "foliage_sway", "frames": 2,
                      "mutable": ("foliage", "foliage_dark")},
    },
    "rock": {
        # no procedural painter (yet): genlab IS this family's generator —
        # `assets request` + `assets ingest`; ensure() only reports the gap
        "generator": "genlab",
        # "ore" (the mine batch): mined heaps with metallic veins — the
        # reason bronze joined the family materials
        "substyles": ("boulder", "rock", "ore"),
        "default_min_variants": 3,
        "style_tokens": {"gen1"},
        "tileset": True,          # rocks paint as tiles too
        "materials": ("stone", "bronze"),
        "descriptor": {
            # a rock blocks at its WHOLE base — the footprint spans the mass
            "blocking": "base",
            "texture_motifs": "stone facets, crack lines, chipped edges", "anchor": "base",
                       "perspective": "high_front",
            "shadow": "dither_ellipse",
        },
        "sizes": {"large": (64, 64), "medium": (32, 32), "small": (32, 32)},
        # rocks don't animate: no `animation` key -> frames stay 1
    },
    "stump": {
        # genlab-only, like rocks — retires the last legacy blob prop
        "generator": "genlab",
        "substyles": ("stump", "log"),
        "default_min_variants": 2,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("wood",),
        "descriptor": {
            "blocking": "base",
            "texture_motifs": "growth rings, bark streaks", "anchor": "base",
                       "perspective": "high_front",
            "shadow": "dither_ellipse",
        },
        "sizes": {"large": (64, 32), "medium": (32, 32), "small": (32, 32)},
    },
    # --- the vaporis batch: architectural/mechanical families (all genlab;
    # extra materials — bronze/verdigris/flame — come from visual-identity
    # 2.4 `materials`, so these families REQUIRE an identity that defines
    # them; flame/water/shimmer animation reuses the generic band-drift)
    "column": {
        "generator": "genlab",
        "substyles": ("intact", "broken", "piped"),
        "default_min_variants": 3,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("stone", "bronze", "verdigris"),
        # plain marble must never snap into the piped variant's bronze
        "materials_by_substyle": {"intact": ("stone",),
                                  "broken": ("stone",)},
        "descriptor": {"blocking": "base",
                       "texture_motifs": "flute shadows, pipe seams, patina drips",
                       "anchor": "plinth",
                       "perspective": "high_front",
                       "shadow": "dither_ellipse"},
        "sizes": {"large": (64, 192), "medium": (64, 128), "small": (32, 64)},
    },
    "statue": {
        "generator": "genlab",
        "substyles": ("robed", "founder"),
        "default_min_variants": 2,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("stone", "verdigris", "bronze"),
        "descriptor": {"blocking": "base",
                       "texture_motifs": "toga folds, patina streaks",
                       "anchor": "pedestal",
                       # dark bronze over pale marble pedestal = albedo
                       # composition; the centroid check misreads it
                       "lighting": "ambient",
                       "perspective": "high_front",
                       "shadow": "dither_ellipse"},
        "sizes": {"large": (64, 160), "medium": (64, 128), "small": (32, 64)},
    },
    "brazier": {
        "generator": "genlab",
        "substyles": ("standing", "lantern"),
        "default_min_variants": 1,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("bronze", "flame"),
        "descriptor": {"blocking": "base",
                       "texture_motifs": "rivet dots, flame licks", "anchor": "base",
                       "perspective": "high_front",
                       "shadow": "dither_ellipse"},
        "sizes": {"medium": (64, 128), "small": (32, 64), "large": (96, 128)},
        "animation": {"kind": "flame_flicker", "frames": 2,
                      "mutable": ("flame",)},
    },
    "fountain": {
        "generator": "genlab",
        "substyles": ("tiered",),
        "default_min_variants": 1,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("stone", "water", "verdigris"),
        "descriptor": {"blocking": "base",
                       "texture_motifs": "water ripples, stone rim highlights",
                       "anchor": "basin",
                       "perspective": "high_front",
                       "shadow": "dither_ellipse"},
        "sizes": {"large": (128, 128), "medium": (96, 96), "small": (32, 32)},
        "animation": {"kind": "water_spray", "frames": 2,
                      "mutable": ("water",)},
    },
    "machine": {
        "generator": "genlab",
        "substyles": ("gearstack", "boiler", "cart", "winch"),
        "default_min_variants": 2,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("bronze", "verdigris", "stone"),
        "descriptor": {"blocking": "base",
                       "texture_motifs": "rivet lines, pipe seams, gear teeth",
                       "anchor": "footing",
                       # machines compose bronze bodies on pale stone
                       # plinths — albedo + AO the centroid check misreads
                       "lighting": "ambient",
                       "perspective": "high_front",
                       "shadow": "dither_ellipse"},
        "sizes": {"large": (128, 128), "medium": (64, 96), "small": (32, 32)},
        # gears cannot ROTATE in band space — heat shimmer is the honest limit.
        # carts and winches are dead metal wherever they stand — shimmer on
        # them reads as haunting, not machinery (mine_hall finding F6); a
        # scene-level cold/hot switch for boilers is a separate, later seam
        "animation": {"kind": "heat_shimmer", "frames": 2,
                      "mutable": ("bronze",),
                      "static_substyles": ("cart", "winch")},
    },
    "topiary": {
        "generator": "genlab",
        "substyles": ("sphere", "spiral"),
        "default_min_variants": 2,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("foliage", "foliage_dark", "wood"),
        "descriptor": {"blocking": "base",
                       "texture_motifs": "clipped leaf clusters",
                       "anchor": "stem",
                       "perspective": "high_front",
                       "shadow": "dither_ellipse"},
        "sizes": {"medium": (64, 96), "small": (32, 64), "large": (96, 128)},
        "animation": {"kind": "foliage_sway", "frames": 2,
                      "mutable": ("foliage", "foliage_dark")},
    },
    "bench": {
        "generator": "genlab",
        "substyles": ("marble", "picnic"),
        "default_min_variants": 1,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("stone", "wood"),
        "descriptor": {"blocking": "base",
                       "texture_motifs": "stone grain, chiseled edges",
                       "anchor": "supports",
                       "perspective": "high_front",
                       "shadow": "dither_ellipse"},
        "sizes": {"large": (96, 64), "medium": (64, 32), "small": (32, 32),
                  "set": (128, 96)},
    },
    "support": {
        # the abandoned-mine batch: wood-only structural frames (two posts +
        # lintel) — blocks at its whole base like the bench (contact SPAN,
        # not centroid: the gap between the posts is open air)
        "generator": "genlab",
        "substyles": ("timber",),
        "default_min_variants": 2,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("wood",),
        "descriptor": {"blocking": "base",
                       "texture_motifs": "axe-cut facets, wood grain",
                       "anchor": "posts",
                       "prompt_notes": (
                           "the opening between the posts is walkable NEGATIVE "
                           "SPACE — keep it clearly open and readable, nothing "
                           "fills the doorway",),
                       "perspective": "high_front",
                       "shadow": "dither_ellipse"},
        "sizes": {"large": (128, 192), "medium": (64, 96), "small": (32, 32)},
    },
    "furniture": {
        # interior furnishing — the school/inn/shop batch. Wood-dominant
        # pieces (desk/bookcase/lectern) plus a slate chalkboard; placed as
        # props[], footprint-blocking. Size-class carries the ASPECT: a desk
        # is wide-low (medium), a bookcase/chalkboard tall (large), a lectern
        # narrow-tall (small) — pick the class per substyle at request time.
        "generator": "genlab",
        "substyles": ("desk", "bookcase", "lectern", "chalkboard"),
        "default_min_variants": 1,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("wood", "stone", "slate"),
        # only the chalkboard reaches for slate; the rest stay wood/stone so
        # a desk never snaps a slate-grey panel
        "materials_by_substyle": {"desk": ("wood", "stone"),
                                  "bookcase": ("wood", "stone"),
                                  "lectern": ("wood", "stone"),
                                  "chalkboard": ("slate", "wood")},
        "descriptor": {"blocking": "base",
                       "texture_motifs": "plank grain, panel seams, "
                                         "drawer lines, shelf edges",
                       "anchor": "base",
                       # dark slate boards + oak in candlelight compose as
                       # albedo; the up-left key-light centroid check misreads
                       "lighting": "ambient",
                       "perspective": "high_front",
                       # box-like pieces gate against the isometric corner
                       # view; the lectern is a stem (book-rest on a post) so
                       # its base dips at center regardless — exempt it
                       "perspective_gate": {"desk": True, "bookcase": True,
                                            "chalkboard": True, "lectern": False},
                       "shadow": "dither_ellipse"},
        # (w, h) — the aspect per class, chosen per substyle at request time
        "sizes": {"large": (96, 128), "medium": (96, 64), "small": (64, 96)},
    },
    "icon": {
        # item inventory icons — one per item, subject supplied per-item by the
        # Item Director (create_request subject=...), not from genlab.SUBJECTS.
        # Referenced by item.icon (props catalog), never painted as tiles.
        "generator": "genlab",
        "substyles": ("weapon", "armor", "consumable", "accessory", "key", "tool"),
        "default_min_variants": 1,
        "style_tokens": {"gen1"},
        "tileset": False,
        # repixel snaps subject pixels ONLY to the ramps named here (repixel.py
        # filters `available` to this list) — so the icon color language must be
        # listed, not just present in the palette. Vivid accents first, then the
        # scene neutrals for wood/metal/glass that need no coding.
        "materials": ("potion_red", "mana_blue", "gold", "steel",
                      "poison_green", "flame_orange", "leather_tan", "amethyst",
                      "bronze", "verdigris", "wood", "stone", "water",
                      "foliage"),
        # icons live by a color LANGUAGE the muted scene palette can't speak;
        # these saturated accent ramps extend the palette FOR ICON REPIXEL ONLY
        # (with_extra_materials) so red=health / blue=mana / gold=key survive
        # quantization. Scene props never see them (nearest-snap keeps muted
        # pixels on muted ramps).
        "palette_extra": {
            "potion_red":   {"color": [0.82, 0.16, 0.18], "hue_span": 0.35},
            "mana_blue":    {"color": [0.22, 0.42, 0.86], "hue_span": 0.35},
            "gold":         {"color": [0.87, 0.68, 0.22], "hue_span": 0.35},
            "steel":        {"color": [0.66, 0.70, 0.77], "hue_span": 0.30},
            "poison_green": {"color": [0.46, 0.72, 0.26], "hue_span": 0.35},
            "flame_orange": {"color": [0.92, 0.48, 0.13], "hue_span": 0.35},
            "leather_tan":  {"color": [0.60, 0.40, 0.22], "hue_span": 0.35},
            "amethyst":     {"color": [0.56, 0.30, 0.72], "hue_span": 0.35},
        },
        "descriptor": {"blocking": "none",
                       "texture_motifs": "bold enamel shapes, crisp readable "
                                         "silhouette, a single trade emblem",
                       "anchor": "center",
                       # a flat emblem: no key-light centroid, no ground shadow,
                       # not gated for isometric (it's not a scene object)
                       "lighting": "ambient",
                       "perspective": "flat",
                       "shadow": "none",
                       # local-model steering that OVERRIDES the global suffix:
                       # the GMIC game-icon LoRA (silhouette + mass that survives
                       # the 24px menu) stacked with the pixel LoRA (variant B of
                       # the A/B/C test). `game icon institute` is GMIC's trigger.
                       "imagegen_suffix":
                           ", game icon institute, pixel_art, "
                           "<lora:GameIconResearch_Pixel_Lora:0.7>, "
                           "<lora:PX64NOCAP_epoch_10:0.8>, single centered game "
                           "item icon, one object, plain solid flat white "
                           "background, no person, no frame, no border",
                       "imagegen_negative":
                           "isometric, 3d render, realistic, photograph, "
                           "person, character, face, hand, two objects, "
                           "ornate frame, rounded frame, border, drop shadow, "
                           "floor, room, text, watermark, lowres, blurry"},
        "sizes": {"small": (32, 32), "medium": (48, 48), "large": (64, 64)},
    },
    "shopsign": {
        # the town's language: hanging trade signs on bracket posts,
        # ICON-first (a mortar, a garment, crossed blades — no readable
        # text; icons are how SNES towns speak)
        "generator": "genlab",
        "substyles": ("apothecary", "garments", "smith", "inn", "general"),
        "default_min_variants": 1,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("wood", "bronze", "canvas", "verdigris"),
        "descriptor": {"blocking": "base",
                       "texture_motifs": "carved icon relief, bracket "
                                         "scrollwork, wood grain",
                       "anchor": "post",
                       "prompt_notes": (
                           "the sign board carries ONE bold trade icon and "
                           "NO text — the icon is painted in BRIGHT "
                           "VERDIGRIS-GREEN AND CREAM ENAMEL standing out "
                           "sharply against the dark wooden board (never "
                           "wood-on-wood carving), and must read at a "
                           "glance at small size",),
                       # enamel-contrast icons are albedo BY DOCTRINE
                       "lighting": "ambient",
                       "perspective": "high_front",
                       "shadow": "dither_ellipse"},
        "sizes": {"large": (64, 128), "medium": (32, 96), "small": (32, 64)},
    },
    "clutter": {
        # the lived-in layer: crates, barrels — the satellites every stall
        # cluster wants (fair concept lesson: clusters, not singles)
        "generator": "genlab",
        "substyles": ("crates", "barrel"),
        "default_min_variants": 2,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("wood", "bronze", "verdigris"),
        "descriptor": {"blocking": "base",
                       "texture_motifs": "plank grain, rope loops, "
                                         "hoop lines",
                       "anchor": "base",
                       "perspective": "high_front",
                       "shadow": "dither_ellipse"},
        "sizes": {"large": (96, 96), "medium": (64, 96), "small": (32, 32)},
    },
    "building": {
        # the classic RPG top-down building: facade + cornice + roof,
        # assembled by automap/buildings2d.py from wall/window/door/
        # cornice/roof pieces. Variant 0 of each substyle IS its prefab —
        # the standard basic build. Blocking is a RECT footprint spanning
        # the facade (kind: "rect"); the door position rides catalog meta
        # for a later interior-teleport slice. Rectangular siblings
        # legitimately share silhouettes — distinctness is judged on
        # interiors with a relaxed IoU ceiling.
        "generator": "buildings2d",
        "substyles": ("house", "kiosk", "pavilion", "shop", "inn"),
        "default_min_variants": 2,
        "style_tokens": {"bld1"},
        "tileset": True,
        "materials": ("plaster", "rooftile", "roofslate", "wood", "stone", "canvas"),
        "descriptor": {"blocking": "facade_base",
                       "texture_motifs": "plaster field, roof courses, "
                                         "cornice line, window bays",
                       "anchor": "facade base",
                       # buildings are facade-dominant and facades are
                       # AO-lit BY DESIGN (eave shade up top, light catching
                       # the low wall) — the up-left centroid check misreads
                       # that as bottom-light. The key light lives on the
                       # ROOF, which the painter biases left by construction.
                       "lighting": "ambient",
                       "perspective": "top_down_front",
                       "shadow": "none"},
        "sizes": {"large": (192, 160), "medium": (96, 128),
                  "small": (64, 96)},
        "distinctness": {"iou_max": 0.97, "interior_min": 0.18},
    },
    "ride": {
        # the fair batch: apprentice-built engineering exhibits. The ferris
        # wheel is the game's largest sprite — a LANDMARK, navigated by.
        # Rotation is impossible in band space (gears/drums/wheels cannot
        # turn — documented engine limit): rides are STATIC by declaration.
        "generator": "genlab",
        "substyles": ("ferris", "carousel"),
        "default_min_variants": 1,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("bronze", "canvas", "verdigris", "stone"),
        "descriptor": {"blocking": "base",
                       "texture_motifs": "rivet lines, spoke lattice, "
                                         "canvas stripes",
                       "anchor": "support legs",
                       "prompt_notes": {
                           "ferris": ("the wheel's plane FACES the viewer "
                                      "(seen nearly side-on) so the full "
                                      "circle and its lattice spokes read; "
                                      "gondolas hang inside the rim",),
                       },
                       "perspective": "high_front",
                       "shadow": "dither_ellipse"},
        "sizes": {"large": (288, 384), "medium": (224, 224),
                  "small": (96, 128)},
    },
    "stall": {
        # the midway system: tents, game booths, the high-striker — striped
        # canvas over timber, scoped together (a midway, not lone props)
        "generator": "genlab",
        "substyles": ("tent", "booth", "highstriker", "bunting", "sign",
                      "marquee", "flagpole"),
        "default_min_variants": 2,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("canvas", "wood", "bronze"),
        "descriptor": {"blocking": "base",
                       "texture_motifs": "canvas stripes, seam lines, "
                                         "timber grain",
                       "anchor": "posts",
                       # a pennant line's bright/dark is ALBEDO (cream vs
                       # red flags at random), not lighting
                       "lighting": {"bunting": "ambient", "highstriker": "ambient"},
                       "perspective": "high_front",
                       "shadow": "dither_ellipse"},
        "sizes": {"large": (192, 192), "medium": (128, 96), "small": (64, 192),
                  "grand": (256, 256), "pole": (64, 160)},
    },
    "portal": {
        # openings in masonry: gateways, sealed gallery mouths, the pit-head
        # shaft mouth (the mine's still-missing focal anchor). Portal-scale
        # forms get a larger canvas than the 64px prop default — an arch that
        # must read as architecture dies at prop resolution (plan S4).
        # prompt_notes key by SUBSTYLE: an arch protects its negative space,
        # a bricked mouth is deliberately sealed, a shaft mouth protects the
        # black drop.
        "generator": "genlab",
        "substyles": ("arch", "bricked", "shaftmouth"),
        "default_min_variants": 1,
        "style_tokens": {"gen1"},
        "tileset": True,
        "materials": ("stone", "wood", "verdigris"),
        "descriptor": {"blocking": "base",
                       "texture_motifs": "mortar joints, block edges, "
                                         "weathering stains",
                       "anchor": "jambs",
                       # the shaft mouth is a GROUND feature lit radially
                       # (bright near rim over a dark pit) — the up-left
                       # key-light check doesn't apply to it
                       "lighting": {"shaftmouth": "ground_plane"},
                       "prompt_notes": {
                           "arch": ("the opening under the arch is walkable "
                                    "NEGATIVE SPACE — keep it clearly open, "
                                    "nothing fills the archway",),
                           "shaftmouth": ("the pit interior is PURE BLACK — a "
                                          "hole, not a floor; the stone ring "
                                          "must read as a low raised curb",),
                       },
                       "perspective": "high_front",
                       "shadow": "dither_ellipse"},
        "sizes": {"large": (160, 160), "medium": (96, 96), "small": (32, 32)},
    },
}


def animation_for(family: str, substyle: str) -> dict | None:
    """The family's animation contract for this substyle.

    None when the substyle opted out via `static_substyles` — per-substyle
    is the granularity of DEAD vs ALIVE (correction plan S5 / finding F6):
    the family says what MAY move, the substyle says whether this subject
    is the kind of thing that does.
    """
    anim = FAMILIES.get(family, {}).get("animation")
    if anim and substyle in anim.get("static_substyles", ()):
        return None
    return anim


def load_catalog(game_dir: Path) -> dict:
    p = game_dir / "content" / "props" / "props.json"
    if not p.exists():
        return {"schema": CATALOG_SCHEMA, "props": {}}
    return json.loads(p.read_text())


def matching_entries(catalog: dict, family: str, identity: str,
                     substyle: str | None) -> list[str]:
    """Catalog entries that FIT the request (style-current or manual)."""
    tokens = FAMILIES.get(family, {}).get("style_tokens",
                                          {trees_px.STYLE_TOKEN})
    out = []
    for name, e in catalog.get("props", {}).items():
        if e.get("family") != family:
            continue
        if e.get("identity_name", catalog.get("identity")) != identity:
            continue
        if substyle and e.get("substyle") != substyle:
            continue
        if e.get("style") in tokens or e.get("provenance") == "manual":
            out.append(name)
    return out


def resolve(game_dir: Path, family: str, identity_name: str,
            substyle: str | None, min_variants: int) -> dict:
    have = matching_entries(load_catalog(game_dir), family, identity_name, substyle)
    return {"family": family, "substyle": substyle, "have": sorted(have),
            "fit": len(have) >= min_variants,
            "gap": max(0, min_variants - len(have))}


def _procedural_generator(family: str):
    """The module behind a procedural family (genlab families never get here).
    Each exposes the same contract: build_set(pal, identity_name, substyle,
    count, start_variant=, iou_max=, interior_min=) + STYLE_TOKEN."""
    name = FAMILIES[family]["generator"]
    if name == "buildings2d":
        from automap import buildings2d
        return buildings2d
    return trees_px


def next_variant_start(live: dict, staging: dict, substyle: str,
                       family: str, count: int = 1) -> int:
    """First free variant index for `count` new `<substyle>_<n>` names.

    Counters are FAMILY-scoped (the shopsign `inn` never advances the
    building `inn` — the town run proved cross-family pollution breaks
    the variant-0-is-the-prefab invariant), but names are globally unique
    across the catalog (bare `<substyle>_<n>` strings are what levels and
    the baker reference), so the start bumps past any foreign-family
    holder of a name in the range.
    """
    def fam_next(cat: dict) -> int:
        best = -1
        for name, e in cat.get("props", {}).items():
            m = re.fullmatch(rf"{substyle}_(\d+)", name)
            if m and e.get("family") == family:
                best = max(best, int(m.group(1)))
        return best + 1

    start = max(fam_next(live), fam_next(staging))
    names = set(live.get("props", {})) | set(staging.get("props", {}))
    while any(f"{substyle}_{start + i}" in names for i in range(max(count, 1))):
        start += 1
    return start


def ensure(game_dir: Path, staging_dir: Path, identity: dict, family: str,
           substyle: str, min_variants: int, log=print) -> dict:
    """Resolve; generate only the gap; stage sprites + catalog metadata.

    Returns the resolution report (post-generation)."""
    if family not in FAMILIES:
        raise ValueError(f"unknown family '{family}' (have {list(FAMILIES)})")
    identity_name = str(identity.get("name", "identity"))
    report = resolve(game_dir, family, identity_name, substyle, min_variants)
    if report["fit"]:
        log(f"[assets] {family}/{substyle}: fit "
            f"({len(report['have'])} >= {min_variants}) — nothing generated")
        return report
    if FAMILIES[family]["generator"] == "genlab":
        log(f"[assets] {family}/{substyle}: gap of {report['gap']} — this "
            "family generates through genlab: run `assets request --family "
            f"{family} --substyle {substyle}`, drop reference PNGs, then "
            "`assets ingest`")
        return report

    pal = pixelart.master_palette(identity)
    staging_dir.mkdir(parents=True, exist_ok=True)
    pixelart.write_palette(staging_dir.parent / "palette", pal)

    catalog_path = staging_dir / "props.json"
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() \
        else {"schema": CATALOG_SCHEMA, "identity": identity_name, "props": {}}
    catalog["schema"] = CATALOG_SCHEMA

    live = load_catalog(game_dir)
    start = next_variant_start(live, catalog, substyle, family,
                               count=report["gap"])
    gen = _procedural_generator(family)
    dist = FAMILIES[family].get("distinctness", {})
    built = gen.build_set(pal, identity_name, substyle, report["gap"],
                          start_variant=start, **dist)
    # automated QC before anything ships — iteration happens here, not by eye
    from automap import asset_qc
    qc = asset_qc.qc_set(
        built, pal,
        asset_qc.resolve_descriptor(FAMILIES[family]["descriptor"], substyle),
        **dist)
    log(asset_qc.format_report(qc))
    if not qc["ok"]:
        log(f"[assets] WARNING: {family}/{substyle} shipped with QC failures "
            "(see report) — tune the generator, then purge + replay")

    anim = animation_for(family, substyle)
    for name, (img, meta) in built.items():
        img.save(staging_dir / f"{name}.png")
        maps = meta.pop("maps", None)
        n_frames = 1
        if anim and maps is not None:
            from automap import animate_px
            material, band, names = maps
            n_frames = animate_px.attach_frames(
                staging_dir, name, material, band, names, pal, anim, img,
                seed_key=f"{identity_name}:{name}:{anim['kind']}", log=log)
        w, h = img.size
        catalog["props"][name] = {
            "file": f"{name}.png", "size": [w, h], "frames": n_frames,
            "anchor_y": meta["anchor_y"], "collision_r": meta["collision_r"],
            "footprint": meta.get("footprint"),
            **({"door": meta["door"]} if meta.get("door") else {}),
            "family": family, "substyle": substyle,
            "identity_name": identity_name,
            "style": gen.STYLE_TOKEN,
            "generator": f"{FAMILIES[family]['generator']}/1",
            "provenance": "generated",
        }
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n")
    log(f"[assets] {family}/{substyle}: generated {len(built)} "
        f"({', '.join(built)}) -> {staging_dir}")
    report = dict(report, generated=sorted(built), fit=True, gap=0)
    return report


# --- prop tileset packing --------------------------------------------------------

def tileset_families() -> list[str]:
    """Families published as paintable tile atlases (in the editor)."""
    return [f for f, spec in FAMILIES.items() if spec.get("tileset")]


def pack_prop_atlas(props_dir: Path, catalog: dict, family: str) -> tuple:
    """Pack ONE family's sprites into a tile-grid atlas for the editor.

    Reads the PUBLISHED (post-hash-guard) PNGs, so hand touch-ups flow into
    the tileset automatically. Shelf-packed on the 32px grid, largest first,
    animation frames in the columns right of each base tile; returns
    (PIL.Image, props-tileset/2.0 meta) or (None, None) if the family is
    empty. Legacy blob entries carry no `family` and are never packed.
    """
    from PIL import Image

    entries = []
    for name, e in sorted(catalog.get("props", {}).items()):
        if e.get("family") != family:
            continue
        p = props_dir / e["file"]
        if not p.exists():
            continue
        img = Image.open(p).convert("RGBA")
        cw = max(1, img.width // 32)
        ch = max(1, img.height // 32)
        # animation frames sit in the columns right of the base tile — the
        # layout Godot's tile animation expects (animation_columns = 0)
        frames = [img]
        for k in range(1, int(e.get("frames", 1))):
            fp = props_dir / f"{name}.f{k}.png"
            if fp.exists():
                frames.append(Image.open(fp).convert("RGBA"))
        entries.append(((cw, ch), name, e, frames))
    if not entries:
        return None, None
    entries.sort(key=lambda t: (-(t[0][0] * t[0][1] * len(t[3])), t[1]))

    atlas_cells_w = 12
    grid: list[list[bool]] = []

    def fits(cx, cy, cw, ch):
        for yy in range(cy, cy + ch):
            while yy >= len(grid):
                grid.append([False] * atlas_cells_w)
            for xx in range(cx, cx + cw):
                if xx >= atlas_cells_w or grid[yy][xx]:
                    return False
        return True

    def place(cw, ch):
        cy = 0
        while True:
            for cx in range(atlas_cells_w - cw + 1):
                if fits(cx, cy, cw, ch):
                    for yy in range(cy, cy + ch):
                        for xx in range(cx, cx + cw):
                            grid[yy][xx] = True
                    return cx, cy
            cy += 1

    meta = {"schema": "props-tileset/2.0", "tile_size": 32,
            "family": family, "tiles": {}}
    placements = []
    for (cw, ch), name, e, frames in entries:
        cx, cy = place(cw * len(frames), ch)
        placements.append((cx, cy, (cw, ch), name, e, frames))
        meta["tiles"][name] = {
            "cell": [cx, cy], "size_cells": [cw, ch],
            "frames": len(frames),
            "anchor_y": int(e.get("anchor_y", frames[0].height - 2)),
            "collision_r": float(e.get("collision_r", 8.0)),
            "footprint": e.get("footprint"),
            "provenance": e.get("provenance", "generated"),
        }
    rows = len(grid)
    atlas = Image.new("RGBA", (atlas_cells_w * 32, rows * 32), (0, 0, 0, 0))
    for cx, cy, (cw, ch), name, e, frames in placements:
        for f, img in enumerate(frames):
            atlas.paste(img, ((cx + f * cw) * 32, cy * 32), img)
    return atlas, meta
