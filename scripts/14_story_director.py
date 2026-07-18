#!/usr/bin/env python
"""Story Director / Lore Keeper CLI — the doors for the narrative chairs.

Commands:
  lore   --game <g>            summarize the canon registry
  arcs   --game <g>            list arcs and their gate status
  check  <arc> --game <g>      run the canon gate on one arc (exit 1 on errors)

The owned documents live at games/<g>/lore/ (bible.md + canon.json) and
games/<g>/story/<arc>/ (<arc>.arc.md + <arc>.beats.json); charters and
the interaction ledger are in docs/studio-org.md.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automap import story  # noqa: E402

app = typer.Typer(add_completion=False)
ROOT = Path(__file__).resolve().parent.parent


def _game_dir(game: str) -> Path:
    d = ROOT / "games" / game
    if not d.exists():
        typer.echo(f"no such game: {d}")
        raise typer.Exit(2)
    return d


@app.command()
def lore(game: str = typer.Option("entropy")) -> None:
    """Summarize the canon registry — counts per kind/region, then entities."""
    canon = story.load_canon(_game_dir(game))
    by = Counter((e["kind"], e.get("region", "-")) for e in canon.values())
    typer.echo(f"canon: {len(canon)} entities")
    for (kind, region), n in sorted(by.items()):
        typer.echo(f"  {kind:8s} {region:10s} {n}")
    for eid, e in sorted(canon.items()):
        mark = {"canon": " ", "proposed": "?", "retired": "x"}[e["status"]]
        typer.echo(f"  [{mark}] {e['kind']:8s} {eid:24s} {e.get('name', '')}")


@app.command()
def arcs(game: str = typer.Option("entropy")) -> None:
    """List arcs with beat counts and gate status."""
    gdir = _game_dir(game)
    ids = story.list_arcs(gdir)
    if not ids:
        typer.echo("no arcs yet — the Story Director writes the first one")
        return
    for arc_id in ids:
        doc = story.load_arc(gdir, arc_id)
        findings = story.check_arc(gdir, doc)
        errs = story.errors(findings)
        status = "BLOCKED" if errs else "ok"
        typer.echo(f"  {arc_id:24s} beats={len(doc.get('beats', []))} "
                   f"gate={status} ({len(errs)} errors, "
                   f"{len(findings) - len(errs)} warnings)")


@app.command()
def check(arc: str, game: str = typer.Option("entropy")) -> None:
    """The canon gate: names, places, sockets, admission, flag continuity."""
    gdir = _game_dir(game)
    doc = story.load_arc(gdir, arc)
    findings = story.check_arc(gdir, doc)
    for f in findings:
        typer.echo(f"  {f.severity.upper():5s} [{f.beat}] {f.message}")
    errs = story.errors(findings)
    if errs:
        typer.echo(f"BLOCKED — {len(errs)} canon errors "
                   "(the Lore Keeper admits, the gate does not bend)")
        raise typer.Exit(1)
    typer.echo(f"gate passed — {len(findings)} warnings" if findings
               else "gate passed — clean")


if __name__ == "__main__":
    app()
