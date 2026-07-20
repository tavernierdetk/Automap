"""Curated ULPC layer catalog for the in-game character creator.

The offline compositor (npc_creator.compose_ulpc) bakes a FIXED build into
flattened frames — right for authored NPCs, wrong for a live player creator
(combinatorial). Instead we ship a CURATED SUBSET of raw ULPC layer sheets
(walk + hurt) into the game so a Godot compositor stacks them at runtime from a
recipe of strings. This module reads the ULPC `sheet_definitions` (for zPos +
per-bodytype paths + color variants), copies the needed sheet PNGs, and emits
`catalog.json` (the picker's option lists + the compositor's path/z map).

Sheet path convention (vendor AND shipped): `<category-path><anim>/<variant>.png`
where category-path = a definition's `layer_1[<bodytype>]` (hair/glasses use a
shared `adult` path across bodytypes). Frame grid is 64px; walk 9×4, hurt 6×1.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

CATALOG_SCHEMA = "ulpc-catalog/1.0"
ANIMS = ("walk", "hurt")            # walk → Walk/Idle/Run (synth); hurt → Faint
FRAME = 64

# --- the curated v1 selection --------------------------------------------------
# bodytypes the creator offers (each rewrites clothing/body paths); hair/glasses
# are body-agnostic (`adult`). Keep male+female for v1; muscular/teen later.
BODYTYPES = ("male", "female")
SKIN = ("light", "amber", "olive", "bronze", "brown", "black")
COLORS = ("black", "blue", "brown", "forest", "charcoal", "red")   # clothing
HAIR_COLORS = ("blonde", "ash", "chestnut", "raven", "brown", "black")

# axis -> (zpos comes from the def) list of definition-file stems to offer
AXES: dict[str, dict] = {
    "hair":    {"defs": ["hair_afro", "hair_bob", "hair_braid", "hair_buzzcut",
                         "hair_bangslong", "hair_bedhead"], "colors": HAIR_COLORS},
    "top":     {"defs": ["torso_clothes_longsleeve", "torso_clothes_tunic",
                         "torso_clothes_robe", "torso_clothes_tshirt",
                         "torso_clothes_vest", "torso_clothes_shortsleeve"],
                "colors": COLORS},
    "bottom":  {"defs": ["legs_pants", "legs_skirts_plain", "legs_shorts",
                         "legs_leggings"], "colors": COLORS},
    "feet":    {"defs": ["feet_shoes_basic"], "colors": COLORS},
    "beard":   {"defs": ["beards_beard", "beards_mustache"], "colors": HAIR_COLORS,
                "bodytypes": ("male",)},   # beards are male-sheeted
    "glasses": {"defs": ["facial_glasses_nerd", "facial_glasses_round",
                         "facial_glasses_shades"], "colors": ("black", "brown")},
    "hat":     {"defs": ["hat_bandana", "hat_cap"], "colors": COLORS},
}


def _def(vendor: Path, stem: str) -> dict | None:
    p = vendor / "sheet_definitions" / f"{stem}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _layer(doc: dict) -> dict:
    for k, v in doc.items():
        if k.startswith("layer_") and isinstance(v, dict):
            return v
    return {}


def _copy_sheets(vendor: Path, out: Path, cat_path: str, colors, log) -> list[str]:
    """Copy <cat_path><anim>/<color>.png for each anim; return colors that exist."""
    got: list[str] = []
    for color in colors:
        ok = False
        for anim in ANIMS:
            src = vendor / "spritesheets" / cat_path / anim / f"{color}.png"
            if src.exists():
                dst = out / "spritesheets" / cat_path / anim / f"{color}.png"
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                ok = ok or anim == "walk"
        if ok:
            got.append(color)
        else:
            log(f"[ulpc-catalog] skip {cat_path} {color} (no walk sheet)")
    return got


def build_catalog(vendor: Path, out: Path, log=print) -> dict:
    """Copy the curated sheets into `out` and return (also writing) catalog.json."""
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    catalog: dict = {"schema": CATALOG_SCHEMA, "frame": FRAME,
                     "bodytypes": list(BODYTYPES), "layers": {}}

    # body (the base layer): one def, per-bodytype paths, SKIN as its colors
    body = _def(vendor, "body")
    bl = _layer(body)
    body_paths, body_skin = {}, set(SKIN)
    for bt in BODYTYPES:
        cat = bl[bt]
        body_paths[bt] = cat
        body_skin &= set(_copy_sheets(vendor, out, cat, SKIN, log))
    catalog["layers"]["body"] = {"zpos": int(bl.get("zPos", 10)),
                                 "paths": body_paths, "colors": sorted(body_skin)}

    # head (a SEPARATE ULPC layer, skin-toned like the body) — per-bodytype def
    head_paths, head_skin = {}, set(SKIN)
    for bt in BODYTYPES:
        hdoc = _def(vendor, f"heads_human_{bt}")
        if hdoc is None:
            continue
        hl = _layer(hdoc)
        cat = hl.get(bt, "")
        head_paths[bt] = cat
        head_skin &= set(_copy_sheets(vendor, out, cat, SKIN, log))
    if head_paths:
        catalog["layers"]["head"] = {"zpos": int(_layer(_def(vendor,
            f"heads_human_{BODYTYPES[0]}")).get("zPos", 100)),
            "paths": head_paths, "colors": sorted(head_skin)}

    # the dressable/cosmetic axes
    for axis, spec in AXES.items():
        bts = spec.get("bodytypes", BODYTYPES)
        options: dict = {}
        zpos = 100
        for stem in spec["defs"]:
            doc = _def(vendor, stem)
            if doc is None:
                log(f"[ulpc-catalog] {axis}: no def {stem} — skipped")
                continue
            lay = _layer(doc)
            zpos = int(lay.get("zPos", zpos))
            oid = stem.split("_", 1)[1] if "_" in stem else stem
            paths, colors = {}, None
            for bt in bts:
                cat = lay.get(bt)
                if not cat:
                    continue
                paths[bt] = cat
                got = _copy_sheets(vendor, out, cat, spec["colors"], log)
                colors = set(got) if colors is None else (colors & set(got))
            if paths and colors:
                options[oid] = {"paths": paths, "colors": sorted(colors)}
        if options:
            catalog["layers"][axis] = {"zpos": zpos, "options": options}

    (out / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n")
    log(f"[ulpc-catalog] {sum(1 for _ in (out / 'spritesheets').rglob('*.png'))} "
        f"sheets, {len(catalog['layers'])} layer axes -> {out}")
    return catalog
