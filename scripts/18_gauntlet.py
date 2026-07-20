#!/usr/bin/env python
"""Combat Trial generator door — emit the gauntlet from games/<game>/gauntlet.json.

    .venv/bin/python scripts/18_gauntlet.py [--game entropy]
then publish (no bake — backdrop levels):
    .venv/bin/python scripts/12_publish_game.py --game entropy
"""
from __future__ import annotations

import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automap import gauntlet  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
app = typer.Typer(add_completion=False)


@app.command()
def build(game: str = typer.Option("entropy")) -> None:
    d = ROOT / "games" / game
    if not d.exists():
        typer.echo(f"no such game: {d}")
        raise typer.Exit(2)
    gauntlet.generate(d, log=typer.echo)


if __name__ == "__main__":
    app()
