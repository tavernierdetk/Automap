#!/usr/bin/env python
"""Systems Director CLI — the rulers' door (items, skills, economy, ui).

Commands:
  items check|library --game <g>     stat-budget gate / the item library
  skills check --game <g>            skill formula caps
  economy check --game <g>           the economy sim gate
  ui check --game <g>                the readability gate

The rulers live in games/<g>/systems.md; the gate constants mirror it
(automap/items.py, economy.py, ui_gate.py). The publisher runs the same
gates fatally; this door runs them solo. Charters: docs/studio-org.md
ledger rows 20, 22–25, 30.
"""
from __future__ import annotations

import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automap import classes as classes_mod  # noqa: E402
from automap import economy as economy_mod  # noqa: E402
from automap import items as items_mod  # noqa: E402
from automap import ui_gate as ui_mod  # noqa: E402

app = typer.Typer(add_completion=False)
items_app = typer.Typer(add_completion=False)
skills_app = typer.Typer(add_completion=False)
classes_app = typer.Typer(add_completion=False)
economy_app = typer.Typer(add_completion=False)
ui_app = typer.Typer(add_completion=False)
for name, sub in (("items", items_app), ("skills", skills_app),
                  ("classes", classes_app), ("economy", economy_app),
                  ("ui", ui_app)):
    app.add_typer(sub, name=name)

ROOT = Path(__file__).resolve().parent.parent


def _game_dir(game: str) -> Path:
    d = ROOT / "games" / game
    if not d.exists():
        typer.echo(f"no such game: {d}")
        raise typer.Exit(2)
    return d


def _report(findings) -> None:
    for f in findings:
        typer.echo(f"  {f.severity.upper():5s} [{f.beat}] {f.message}")
    errs = [f for f in findings if f.severity == "error"]
    if errs:
        typer.echo(f"BLOCKED — {len(errs)} errors")
        raise typer.Exit(1)
    typer.echo("gate passed")


@items_app.command("check")
def items_check(game: str = typer.Option("entropy")) -> None:
    _report(items_mod.check_items(_game_dir(game)))


@items_app.command("library")
def items_library(game: str = typer.Option("entropy")) -> None:
    gdir = _game_dir(game)
    out = gdir / "items" / "library.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(items_mod.library_md(gdir))
    typer.echo(f"library: {out.relative_to(ROOT)} "
               f"({len(items_mod.load_items(gdir))} items, "
               f"{len(items_mod.load_skills(gdir))} skills)")


# kind -> icon substyle (the icon family names candidates <substyle>_<n>)
_ICON_SUBSTYLE = {"weapon": "weapon", "armor": "armor", "consumable": "consumable",
                  "accessory": "accessory", "key": "key"}


def _icon_subject(iid: str, item: dict, authored: dict) -> tuple[str, str]:
    """(substyle, subject) for an item — the authored subject wins; else a
    kind template. Wearables MUST say 'no person' or GMIC draws a character."""
    spec = authored.get(iid, {})
    substyle = spec.get("substyle") or _ICON_SUBSTYLE.get(item.get("kind", ""),
                                                          "accessory")
    subject = spec.get("subject")
    if not subject:                      # template fallback for un-authored items
        name = item.get("name", iid)
        kind = item.get("kind", "")
        flat = ", laid flat, no person" if kind == "armor" else ""
        subject = f"a {name}, a single {kind or 'object'} item{flat}"
    return substyle, subject


@items_app.command("icons")
def items_icons(
    action: str = typer.Argument("generate", help="generate | assign | status"),
    game: str = typer.Option("entropy"),
    item: str = typer.Option("", help="restrict to these item ids (comma-sep)"),
    count: int = typer.Option(2, help="generate: candidates per item"),
    pick: str = typer.Option("", help="assign: JSON map {item_id: prop_name}"),
    identity: str = typer.Option("identities/entropy.json"),
) -> None:
    """Mint item icons through the GMIC icon pipeline, one request per item.

    generate → box renders `count` candidates per item, repixelized into the
    vivid icon palette; writes a contact sheet + candidates map.
    assign --pick '{"id":"prop"}' → sets item.icon (prunes unpicked candidates).
    """
    import json
    from PIL import Image, ImageDraw
    from automap import genlab, asset_creator

    gdir = _game_dir(game)
    ident_path = ROOT / identity
    ident = json.loads(ident_path.read_text())
    items = items_mod.load_items(gdir)
    only = {s.strip() for s in item.split(",") if s.strip()}
    if only:
        items = {k: v for k, v in items.items() if k in only}
    authored = json.loads((gdir / "items" / "icon_subjects.json").read_text()
                          ).get("subjects", {}) \
        if (gdir / "items" / "icon_subjects.json").exists() else {}
    genlab_dir = ROOT / "work" / "game" / game / "genlab"
    staging = ROOT / "work" / "game" / game / "props"
    map_path = ROOT / "work" / "game" / game / "icon_candidates.json"
    spec = asset_creator.FAMILIES["icon"]

    if action == "generate":
        cand: dict = json.loads(map_path.read_text()) if map_path.exists() else {}
        for iid, doc in sorted(items.items()):
            substyle, subject = _icon_subject(iid, doc, authored)
            rd = genlab.create_request(genlab_dir, ident, identity, "icon",
                                       substyle, "large", count,
                                       spec["descriptor"], spec["materials"],
                                       subject=subject)
            typer.echo(f"[icons] {iid}: {rd.name} — “{subject[:56]}…”")
            genlab.generate_via_api(rd, log=lambda *a: None)
            out = genlab.ingest(rd, gdir, staging, ident, log=typer.echo)
            cand[iid] = out["staged"]
            map_path.write_text(json.dumps(cand, indent=2) + "\n")  # per-item
        _icon_contact_sheet(staging, cand, map_path.with_suffix(".png"))
        typer.echo(f"[icons] candidates -> {map_path}")
        typer.echo(f"[icons] contact sheet -> {map_path.with_suffix('.png')}")
        return

    if action == "assign":
        if not pick:
            typer.echo("assign needs --pick '{\"item_id\": \"prop_name\"}'")
            raise typer.Exit(2)
        chosen = json.loads(pick)
        catalog = asset_creator.load_catalog(gdir)  # published props (names valid)
        staged = json.loads((staging / "props.json").read_text())["props"] \
            if (staging / "props.json").exists() else {}
        for iid, prop in chosen.items():
            if prop not in staged and prop not in catalog.get("props", {}):
                typer.echo(f"  ! {iid}: '{prop}' is not a staged icon prop")
                raise typer.Exit(1)
            p = gdir / "items" / f"{iid}.json"
            doc = json.loads(p.read_text())
            doc["icon"] = prop
            p.write_text(json.dumps(doc, indent=2) + "\n")
            typer.echo(f"  {iid}.icon = {prop}")
        # prune icon-family candidates nobody picked — keep content/props clean
        kept = set(chosen.values())
        removed = 0
        for name, e in list(staged.items()):
            if e.get("family") == "icon" and name not in kept:
                staged.pop(name)
                (staging / e["file"]).unlink(missing_ok=True)
                removed += 1
        cat = json.loads((staging / "props.json").read_text())
        cat["props"] = staged
        (staging / "props.json").write_text(json.dumps(cat, indent=2) + "\n")
        typer.echo(f"[icons] assigned {len(chosen)}, pruned {removed} unpicked")
        return

    if action == "status":
        for iid, doc in sorted(items.items()):
            typer.echo(f"  {iid:22s} icon={doc.get('icon') or '—'}")
        return
    typer.echo(f"unknown action '{action}' (generate|assign|status)")
    raise typer.Exit(2)


def _icon_contact_sheet(staging: Path, cand: dict, out: Path) -> None:
    from PIL import Image, ImageDraw
    rows = [(iid, names) for iid, names in sorted(cand.items()) if names]
    if not rows:
        return
    cell, pad, labw = 96, 10, 150
    maxn = max(len(n) for _, n in rows)
    W = labw + maxn * (cell + pad) + pad
    H = pad + len(rows) * (cell + pad)
    sheet = Image.new("RGBA", (W, H), (44, 44, 50, 255))
    dr = ImageDraw.Draw(sheet)
    for r, (iid, names) in enumerate(rows):
        y = pad + r * (cell + pad)
        dr.text((6, y + cell // 2 - 4), iid, fill=(230, 230, 220, 255))
        for c, name in enumerate(names):
            fp = staging / f"{name}.png"
            if not fp.exists():
                continue
            im = Image.open(fp).convert("RGBA").resize((cell, cell), Image.NEAREST)
            x = labw + c * (cell + pad)
            sheet.alpha_composite(im, (x, y))
            dr.text((x, y), name, fill=(180, 200, 160, 255))
    sheet.convert("RGB").save(out)


@skills_app.command("check")
def skills_check(game: str = typer.Option("entropy")) -> None:
    _report(items_mod.check_skills(_game_dir(game)))


@classes_app.command("check")
def classes_check(game: str = typer.Option("entropy")) -> None:
    _report(classes_mod.check_classes(_game_dir(game)))


@economy_app.command("check")
def economy_check(game: str = typer.Option("entropy")) -> None:
    _report(economy_mod.check_economy(_game_dir(game)))


@ui_app.command("check")
def ui_check(game: str = typer.Option("entropy")) -> None:
    _report(ui_mod.check_ui(_game_dir(game)))


if __name__ == "__main__":
    app()
