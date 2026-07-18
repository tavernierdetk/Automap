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
from automap import economy as economy_mod  # noqa: E402
from automap import items as items_mod  # noqa: E402
from automap import ui_gate as ui_mod  # noqa: E402

app = typer.Typer(add_completion=False)
items_app = typer.Typer(add_completion=False)
skills_app = typer.Typer(add_completion=False)
economy_app = typer.Typer(add_completion=False)
ui_app = typer.Typer(add_completion=False)
for name, sub in (("items", items_app), ("skills", skills_app),
                  ("economy", economy_app), ("ui", ui_app)):
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


@skills_app.command("check")
def skills_check(game: str = typer.Option("entropy")) -> None:
    _report(items_mod.check_skills(_game_dir(game)))


@economy_app.command("check")
def economy_check(game: str = typer.Option("entropy")) -> None:
    _report(economy_mod.check_economy(_game_dir(game)))


@ui_app.command("check")
def ui_check(game: str = typer.Option("entropy")) -> None:
    _report(ui_mod.check_ui(_game_dir(game)))


if __name__ == "__main__":
    app()
