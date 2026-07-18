#!/usr/bin/env python
"""Stage 13 (scene director) - the SceneCreationDirector's tool suite.

The mechanical half of the director (the LLM half is the /create-scene skill:
it reads the catalog, decides reuse-vs-generate, fills a level@2 document,
and drives these subcommands; see docs/explorations/scene-creation-director.md):

    catalog   what the game already has: backgrounds (size + palette
              signature), creatures (animations), tile atlases (classes +
              mechanics flags), levels (ids + exits). Reuse before generate.
    atlas     generate a tile atlas from a visual identity (+ optional
              mechanics overrides) into the game's staging tree.
    bake      publish (stage 12) then bake tilemap levels to editor-editable
              scenes via the game project's headless baker.

Everything stays deterministic and validated: levels go through the brief
gate (a `<id>.brief.md` must exist upstream — intent before pixels), level@*,
the publisher's teleport-graph gate, and the baker's tile-class checks.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

app = typer.Typer(add_completion=False)

GODOT = "/Applications/Godot.app/Contents/MacOS/Godot"
ROOT = Path(__file__).resolve().parent.parent


def _level_path(levels_dir: Path, lid: str, suffix: str) -> Path:
    """Scene file lookup across layouts, most organized first:
    levels/<region>/<id>/<id>.<suffix> (regional filing), then
    levels/<id>/<id>.<suffix>, then flat levels/<id>.<suffix>."""
    hits = sorted(levels_dir.glob(f"*/{lid}/{lid}.{suffix}"))
    if hits:
        return hits[0]
    foldered = levels_dir / lid / f"{lid}.{suffix}"
    return foldered if foldered.exists() else levels_dir / f"{lid}.{suffix}"


def _check_briefs(levels_dir: Path, level_ids: list[str]) -> list[str]:
    """The brief gate: a scene is generated FROM a brief, never before one.

    A level being baked must have `<id>.brief.md` beside its JSON (the
    upstream statement of intent — place, zones, register, motion,
    acceptance reads) and an `intent` field summarizing it. Retro-authored
    briefs are what this gate exists to prevent (mine_hall finding F8;
    docs/explorations/scene-generation-correction-plan.md, S1).
    """
    errors: list[str] = []
    for lid in level_ids:
        brief = _level_path(levels_dir, lid, "brief.md")
        if not brief.exists() or not brief.read_text().strip():
            shown = brief.relative_to(ROOT) if brief.is_relative_to(ROOT) else brief
            errors.append(f"{lid}: no brief at {shown} — "
                          "write the brief BEFORE the grid (S1 gate)")
        level = _level_path(levels_dir, lid, "json")
        if level.exists():
            doc = json.loads(level.read_text())
            if not str(doc.get("intent", "")).strip():
                errors.append(f"{lid}: level JSON has no `intent` — it must "
                              "summarize the brief")
    return errors


def _palette_signature(img_path: Path, buckets: int = 4) -> list[list[int]]:
    """Dominant colors (coarse histogram peaks) — enough for mood-matching."""
    from PIL import Image
    import numpy as np
    img = Image.open(img_path).convert("RGB").resize((64, 64))
    arr = np.asarray(img).reshape(-1, 3)
    q = (arr // 64).astype(int)  # 4 levels/channel -> 64 buckets
    keys = q[:, 0] * 16 + q[:, 1] * 4 + q[:, 2]
    counts = np.bincount(keys, minlength=64)
    top = counts.argsort()[::-1][:buckets]
    out = []
    for k in top:
        if counts[k] == 0:
            continue
        mask = keys == k
        out.append([int(c) for c in arr[mask].mean(axis=0)])
    return out


@app.command()
def catalog(
    game: str = typer.Option("entropy", "--game"),
    game_dir: Path = typer.Option(Path.home() / "Cowork" / "entropy-remade", "--game-dir"),
):
    """Inventory the game's usable assets + the current level graph."""
    content = game_dir / "content"
    cat: dict = {"game": game, "backgrounds": [], "creatures": [],
                 "tilesets": [], "props": {}, "levels": []}
    bg_dir = content / "backgrounds"
    if bg_dir.exists():
        from PIL import Image
        for f in sorted(bg_dir.glob("*.png")):
            cat["backgrounds"].append({
                "file": f.name, "size": list(Image.open(f).size),
                "palette": _palette_signature(f)})
    cr_dir = content / "creatures"
    if cr_dir.exists():
        for d in sorted(p for p in cr_dir.iterdir() if p.is_dir()):
            m = d / "manifest.json"
            if m.exists():
                doc = json.loads(m.read_text())
                cat["creatures"].append(
                    {"slug": doc["slug"], "animations": sorted(doc["animations"])})
    pr = content / "props" / "props.json"
    if pr.exists():
        doc = json.loads(pr.read_text())
        cat["props"] = {k: {"size": v["size"], "collision_r": v["collision_r"]}
                        for k, v in doc.get("props", {}).items()}
    tl_dir = content / "tilesets"
    if tl_dir.exists():
        for f in sorted(tl_dir.glob("*.tiles.json")):
            doc = json.loads(f.read_text())
            cat["tilesets"].append({
                "atlas": f.name.replace(".tiles.json", ""),
                "identity": doc.get("identity"), "tile_size": doc.get("tile_size"),
                "classes": {c: {k: v for k, v in spec.items() if k != "row"}
                            for c, spec in doc.get("classes", {}).items()}})
    lv_dir = ROOT / "games" / game / "levels"
    for f in sorted(list(lv_dir.glob("*.json")) + list(lv_dir.glob("*/*.json"))
                    + list(lv_dir.glob("*/*/*.json"))):
        doc = json.loads(f.read_text())
        cat["levels"].append({
            "id": doc["id"], "kind": doc.get("kind", "backdrop"),
            "spawns": [s["tag"] for s in doc.get("spawns", [])],
            "exits": [{"to": t["target_level"], "tag": t.get("target_spawn_tag", "")}
                      for t in doc.get("teleports", [])],
            "npc_slots": [s["tag"] for s in doc.get("npc_slots", [])]})
    out = ROOT / "work" / "game" / game / "asset_catalog.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cat, indent=2) + "\n")
    typer.echo(json.dumps(cat, indent=2))
    typer.echo(f"[stage 13] catalog -> {out}")


@app.command()
def atlas(
    identity: Path = typer.Option(None, "--identity", help="visual-identity JSON file"),
    spec: Path = typer.Option(None, "--spec",
                              help="atlas spec JSON (games/<game>/atlases/*.spec.json): "
                                   "the scene's terrain vocabulary — classes, colors, "
                                   "transition pairs. Default = the surface five."),
    game: str = typer.Option("entropy", "--game"),
    name: str = typer.Option(None, "--name", help="Atlas base name (default spec name "
                                                  "or <identity>_terrain)"),
    mechanics: str = typer.Option(None, "--mechanics",
                                  help='JSON overrides, e.g. {"water":{"walkable":true}}'),
):
    """Generate a tile atlas (identity colors + optional vocabulary spec)."""
    from automap.tiles2d import write_atlas
    spec_doc = json.loads(spec.read_text()) if spec else None
    if identity is None:
        if not (spec_doc and spec_doc.get("identity")):
            raise typer.BadParameter("--identity required (or an `identity` in the spec)")
        identity = ROOT / spec_doc["identity"]
    ident = json.loads(identity.read_text())
    base = name or (spec_doc or {}).get("name") or f"{ident.get('name', 'identity')}_terrain"
    over = json.loads(mechanics) if mechanics else None
    meta = write_atlas(ROOT / "work" / "game" / game / "tilesets" / base,
                       ident, mechanics=over, spec=spec_doc)
    typer.echo(f"[stage 13] atlas '{base}' ({len(meta['classes'])} classes, "
               f"{len(meta['transitions'])} transition pairs) "
               f"-> work/game/{game}/tilesets/ (publish with stage 12 / `bake`)")


@app.command()
def library(
    game: str = typer.Option("entropy", "--game"),
    game_dir: Path = typer.Option(Path.home() / "Cowork" / "entropy-remade", "--game-dir"),
):
    """Build THE ASSET LIBRARY — the reference the director consults before
    calling the Asset Creator: games/<game>/library.md (committed; every
    family, variant, figure-relative size, doctrine notes, atlas
    vocabularies, filed scenes) + per-family contact sheets under
    work/game/<game>/library/ for eyeballing."""
    from PIL import Image
    from automap.asset_creator import FAMILIES, load_catalog
    FIGURE = 96.0  # the scale contract's reference height
    cat = load_catalog(game_dir)
    props_dir = game_dir / "content" / "props"
    sheets_dir = ROOT / "work" / "game" / game / "library"
    sheets_dir.mkdir(parents=True, exist_ok=True)

    fams: dict[str, list] = {}
    for name, e in sorted(cat.get("props", {}).items()):
        fams.setdefault(e.get("family", "?"), []).append((name, e))

    lines = [f"# Asset library — {game}", "",
             "The SceneCreationDirector's reference: what EXISTS before the",
             "Asset Creator is asked for anything new (`13 library` rebuilds",
             "this file + the contact sheets in `work/game/%s/library/`)." % game,
             "Sizes are given in FIGURES (the 96px character — the scale",
             "contract): a door is ≥1 figure, a house ≈3.", "",
             "## Families"]
    for fam in sorted(fams):
        spec = FAMILIES.get(fam, {})
        d = spec.get("descriptor", {})
        notes = []
        if spec.get("generator"):
            notes.append(f"generator `{spec['generator']}`")
        if spec.get("animation"):
            a = spec["animation"]
            stat = a.get("static_substyles")
            notes.append(f"animates `{a['kind']}`"
                         + (f" (static: {', '.join(stat)})" if stat else ""))
        if isinstance(d.get("lighting"), str):
            notes.append(f"lighting `{d['lighting']}`")
        fp = "rect" if d.get("blocking") == "facade_base" else d.get("blocking", "base")
        notes.append(f"blocks `{fp}`")
        lines += [f"", f"### {fam} — {'; '.join(notes)}", "",
                  "| variant | px | figures (w×h) | frames | style |",
                  "|---|---|---|---|---|"]
        thumbs = []
        for name, e in fams[fam]:
            w, h = e["size"]
            lines.append(f"| {name} | {w}×{h} | {w / FIGURE:.1f}×{h / FIGURE:.1f} "
                         f"| {e.get('frames', 1)} | {e.get('style', '?')} |")
            p = props_dir / e["file"]
            if p.exists():
                thumbs.append(Image.open(p).convert("RGBA"))
        if thumbs:
            W = sum(t.width for t in thumbs) + 6 * len(thumbs)
            H = max(t.height for t in thumbs)
            sheet = Image.new("RGBA", (W, H), (38, 38, 42, 255))
            x = 0
            for t in thumbs:
                sheet.paste(t, (x, H - t.height), t)
                x += t.width + 6
            sheet.save(sheets_dir / f"{fam}.png")

    lines += ["", "## Terrain vocabularies (atlas specs)", ""]
    for f in sorted((ROOT / "games" / game / "atlases").glob("*.spec.json")):
        doc = json.loads(f.read_text())
        classes = ", ".join(c["name"] for c in doc.get("classes", []))
        lines.append(f"- **{doc.get('name', f.stem)}** (`atlases/{f.name}`): {classes}")

    lines += ["", "## Scenes (regional filing: levels/<region>/<id>/)", ""]
    lv_dir = ROOT / "games" / game / "levels"
    for f in sorted(list(lv_dir.glob("*/*/*.json")) + list(lv_dir.glob("*/*.json"))):
        doc = json.loads(f.read_text())
        region = f.parent.parent.name if f.parent.parent != lv_dir else "(unfiled)"
        lines.append(f"- `{region}` / **{doc['id']}** — {doc.get('kind', 'backdrop')}, "
                     f"{len(doc.get('npc_slots', []))} sockets")

    out = ROOT / "games" / game / "library.md"
    out.write_text("\n".join(lines) + "\n")
    typer.echo(f"[stage 13] library -> {out} (+ {len(fams)} contact sheets)")


@app.command()
def concept(
    level_id: str = typer.Argument(..., help="Level id (its brief must exist)"),
    game: str = typer.Option("entropy", "--game"),
    identity: Path = typer.Option(Path("identities/vaporis.json"), "--identity"),
    count: int = typer.Option(2, "--count"),
):
    """Generate wide concept views of a scene from its brief (reference
    only — study composition/density, write notes into the brief, never
    trace). Brief-downstream by construction."""
    from automap import genlab
    brief = _level_path(ROOT / "games" / game / "levels", level_id, "brief.md")
    if not brief.exists() or not brief.read_text().strip():
        typer.echo(f"[stage 13] BRIEF GATE: no brief at {brief.relative_to(ROOT)}"
                   " — a concept is generated FROM intent, write the brief first")
        raise typer.Exit(code=1)
    if not identity.is_absolute():
        identity = ROOT / identity
    ident = json.loads(identity.read_text())
    genlab.generate_scene_concept(
        brief, ident, ROOT / "work" / "game" / game / "concepts" / level_id,
        count=count, log=typer.echo)


@app.command()
def props(
    identity: Path = typer.Option(..., "--identity", help="visual-identity JSON file"),
    game: str = typer.Option("entropy", "--game"),
):
    """Generate the prop-sprite set (trees/rocks/stumps) from a visual identity."""
    from automap.props2d import write_props
    ident = json.loads(identity.read_text())
    cat = write_props(ROOT / "work" / "game" / game / "props", ident)
    typer.echo(f"[stage 13] {len(cat['props'])} prop sprites -> work/game/{game}/props/")


@app.command()
def bake(
    level_ids: list[str] = typer.Argument(..., help="Tilemap level ids to bake"),
    game: str = typer.Option("entropy", "--game"),
    game_dir: Path = typer.Option(Path.home() / "Cowork" / "entropy-remade", "--game-dir"),
    publish: bool = typer.Option(True, "--publish/--no-publish",
                                 help="Run stage 12 first (default)"),
):
    """Publish, then bake tilemap levels into editor-editable scenes."""
    brief_errors = _check_briefs(ROOT / "games" / game / "levels", level_ids)
    if brief_errors:
        for e in brief_errors:
            typer.echo(f"[stage 13] BRIEF GATE: {e}")
        raise typer.Exit(code=1)
    if publish:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "12_publish_game.py"),
                            "--game", game, "--game-dir", str(game_dir)])
        if r.returncode != 0:
            raise typer.Exit(code=r.returncode)
        # publish wipes content dirs including Godot's .import metadata — the
        # baker loads textures through the import cache, so refresh it first
        subprocess.run([GODOT, "--headless", "--path", str(game_dir), "--import"],
                       capture_output=True, text=True)
        typer.echo("[stage 13] reimported game resources")
    r = subprocess.run([GODOT, "--headless", "--path", str(game_dir),
                        "res://tools/bake_scene.tscn", "--", *level_ids],
                       capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if "[bake]" in line:
            typer.echo(line)
    if r.returncode != 0:
        typer.echo(r.stderr[-800:])
        raise typer.Exit(code=1)
    typer.echo(f"[stage 13] baked {len(level_ids)} scene(s) -> content/scenes/")


@app.command()
def assets(
    action: str = typer.Argument(
        ..., help="'ensure', 'status', 'qc', 'replay', 'request', "
                  "'generate', 'preview' or 'ingest'"),
    family: str = typer.Option("tree", "--family"),
    identity: Path = typer.Option(Path("identities/entropy.json"), "--identity"),
    substyle: str = typer.Option("deciduous", "--substyle"),
    min_variants: int = typer.Option(None, "--min-variants"),
    size_class: str = typer.Option("large", "--size-class",
                                   help="genlab request canvas (large/medium/small)"),
    req_id: str = typer.Option(None, "--req", help="ingest one request by id"),
    game: str = typer.Option("entropy", "--game"),
    game_dir: Path = typer.Option(Path.home() / "Cowork" / "entropy-remade", "--game-dir"),
):
    """Asset Creator: reuse what fits, generate only the gap (pixel-art)."""
    from automap import asset_creator
    if not identity.is_absolute():
        identity = ROOT / identity
    ident = json.loads(identity.read_text())
    spec = asset_creator.FAMILIES.get(family, {})
    n = min_variants or spec.get("default_min_variants", 4)
    genlab_dir = ROOT / "work" / "game" / game / "genlab"
    staging = ROOT / "work" / "game" / game / "props"
    if action == "request":
        from automap import genlab
        req_dir = genlab.create_request(
            genlab_dir, ident, str(identity), family, substyle, size_class,
            n, spec.get("descriptor", {}),
            spec.get("materials", ("foliage", "foliage_dark", "wood")))
        typer.echo(f"[genlab] request {req_dir.name} created")
        typer.echo(f"[genlab] prompt:   {req_dir / 'prompt.md'}")
        typer.echo(f"[genlab] drop PNGs into: {req_dir / 'incoming'}")
        typer.echo("[genlab] then run: assets ingest --req " + req_dir.name)
        return
    if action == "generate":
        # API mode of the ImageGen box: fill incoming/ from the configured
        # provider (key: IMAGEGEN_API_KEY or ~/.automap/imagegen.json),
        # then judge with 'assets preview' before anything is staged
        from automap import genlab
        req_dirs = [genlab_dir / req_id] if req_id else \
            sorted(d for d in genlab_dir.glob("*") if (d / "request.json").exists()
                   and not any((d / "incoming").glob("*.png"))) \
            if genlab_dir.exists() else []
        if not req_dirs:
            typer.echo("[genlab] nothing to generate — every request already "
                       "has references (or none exist; run 'assets request')")
            raise typer.Exit(code=1)
        for rd in req_dirs:
            genlab.generate_via_api(rd, log=typer.echo)
        return
    if action == "preview":
        # human-in-the-loop dry run: recreate + QC, stage NOTHING — judge
        # the review sheet, cull references, then 'ingest' what earned it
        from automap import genlab
        req_dirs = [genlab_dir / req_id] if req_id else \
            sorted(d for d in genlab_dir.glob("*") if (d / "request.json").exists()
                   and any((d / "incoming").glob("*.png"))) \
            if genlab_dir.exists() else []
        if not req_dirs:
            typer.echo("[genlab] nothing to preview — drop reference PNGs "
                       "into a request's incoming/ first")
            raise typer.Exit(code=1)
        for rd in req_dirs:
            genlab.preview(rd, ident, log=typer.echo)
        return
    if action == "ingest":
        from automap import genlab
        req_dirs = [genlab_dir / req_id] if req_id else \
            sorted(d for d in genlab_dir.glob("*") if (d / "request.json").exists()) \
            if genlab_dir.exists() else []
        if not req_dirs:
            typer.echo("[genlab] no requests found — run 'assets request' first")
            raise typer.Exit(code=1)
        recipes_path = ROOT / "games" / game / "asset_requests.json"
        recipes = json.loads(recipes_path.read_text()) if recipes_path.exists() \
            else {"requests": []}
        for rd in req_dirs:
            out = genlab.ingest(rd, game_dir, staging, ident, log=typer.echo)
            if out["staged"]:
                req_doc = json.loads((rd / "request.json").read_text())
                rec = {"generator": "genlab", "family": req_doc["family"],
                       "identity": str(identity), "req": rd.name}
                if rec not in recipes["requests"]:
                    recipes["requests"].append(rec)
        recipes_path.write_text(json.dumps(recipes, indent=2) + "\n")
        return
    if action == "replay":
        recipes_path = ROOT / "games" / game / "asset_requests.json"
        if recipes_path.exists():
            from automap import genlab
            for req in json.loads(recipes_path.read_text()).get("requests", []):
                ipath = Path(req["identity"])
                if not ipath.is_absolute():
                    ipath = ROOT / ipath
                rident = json.loads(ipath.read_text())
                if req.get("generator") == "genlab":
                    rd = genlab_dir / req["req"]
                    if rd.exists() and any((rd / "incoming").glob("*.png")):
                        genlab.ingest(rd, game_dir, staging, rident, log=typer.echo)
                    else:
                        # reference images are gitignored intermediates: the
                        # published sprite is the durable artifact
                        typer.echo(f"[genlab] replay: {req['req']} has no "
                                   "reference images — skipped (published "
                                   "sprites remain the artifact)")
                    continue
                asset_creator.ensure(
                    game_dir, staging, rident,
                    req["family"], req["substyle"], req["min_variants"],
                    log=typer.echo)
        return
    if action == "qc":
        from automap import asset_qc, pixelart
        from PIL import Image as PILImage
        import numpy as _np
        pal = pixelart.master_palette(ident)
        props_dir = game_dir / "content" / "props"
        catalog = asset_creator.load_catalog(game_dir)
        images_meta = {}
        for name, e in sorted(catalog.get("props", {}).items()):
            if e.get("family") != family:
                continue
            p = props_dir / e["file"]
            if p.exists():
                images_meta[name] = (PILImage.open(p).convert("RGBA"), e)
        if not images_meta:
            typer.echo(f"[assets] qc: no {family} assets published")
            return
        report = asset_qc.qc_set(images_meta, pal, spec.get("descriptor", {}))
        typer.echo(asset_qc.format_report(report))
        raise typer.Exit(code=0 if report["ok"] else 1)
    if action == "status":
        for sub in spec.get("substyles", (substyle,)):
            r = asset_creator.resolve(game_dir, family, ident.get("name", "identity"), sub, n)
            typer.echo(f"[assets] {family}/{sub}: {'FIT' if r['fit'] else 'GAP ' + str(r['gap'])}"
                       f" (have {len(r['have'])}/{n})")
        return
    report = asset_creator.ensure(
        game_dir, ROOT / "work" / "game" / game / "props", ident,
        family, substyle, n, log=typer.echo)
    # record the recipe so PRODUCE=1 CI regenerates from text
    recipes_path = ROOT / "games" / game / "asset_requests.json"
    recipes = json.loads(recipes_path.read_text()) if recipes_path.exists() else {"requests": []}
    req = {"family": family, "identity": str(identity), "substyle": substyle,
           "min_variants": n}
    if req not in recipes["requests"]:
        recipes["requests"].append(req)
        recipes_path.write_text(json.dumps(recipes, indent=2) + "\n")
        typer.echo(f"[assets] recipe recorded -> {recipes_path.name}")


@app.command()
def transcribe(
    sources: list[Path] = typer.Argument(..., help="Original .tscn scene files"),
    game: str = typer.Option("entropy", "--game"),
    scan_root: Path = typer.Option(
        Path.home() / "Cowork" / "entropy-integrated" / "Scenes", "--scan-root",
        help="Directory scanned to map scene uids -> level ids"),
    out: Path = typer.Option(None, "--out", help="Default games/<game>/levels/"),
):
    """SceneCreator reverse projection: authored .tscn -> level@2 documents."""
    from automap.scene_transcriber import build_uid_map, transcribe as run
    out_dir = out or ROOT / "games" / game / "levels"
    uid_map = build_uid_map(scan_root)
    for src_path in sources:
        doc, skipped = run(src_path, uid_map,
                           dialogues_dir=ROOT / "games" / game / "dialogues")
        try:
            import platform_specs
            platform_specs.validate(doc, "level", "2.1.0")
        except ImportError:
            typer.echo("[stage 13] WARNING: unvalidated (platform-specs missing)")
        except Exception as e:
            typer.echo(f"[stage 13] WARNING: {doc['id']} is a DRAFT — schema says: "
                       f"{str(e).splitlines()[0]} (director attention needed)")
        target = out_dir / doc["id"] / f"{doc['id']}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(doc, indent=2) + "\n")
        typer.echo(f"[stage 13] transcribed {src_path.name} -> {target.name}"
                   + (f"  (skipped: {'; '.join(skipped)})" if skipped else ""))


if __name__ == "__main__":
    app()
