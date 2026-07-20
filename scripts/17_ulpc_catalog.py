#!/usr/bin/env python
"""Build the curated ULPC layer catalog the in-game character creator ships.

Copies a curated subset of ULPC layer sheets (walk + hurt) + emits catalog.json
into work/game/<game>/ulpc/; stage-12 publish moves it to res://content/ulpc/.

    .venv/bin/python scripts/17_ulpc_catalog.py [--game entropy]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automap import ulpc_catalog  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PIXELASSET_DEFAULT = Path.home() / "Cowork" / "PixelAssetCreator"

app = typer.Typer(add_completion=False)


@app.command()
def build(game: str = typer.Option("entropy"),
          pixelasset: Path = typer.Option(None)) -> None:
    root = pixelasset or Path(os.environ.get("PIXELASSET_ROOT", PIXELASSET_DEFAULT))
    vendor = root / "packages" / "sprite-catalog" / "vendor" / "ulpc-src"
    if not vendor.exists():
        typer.echo(f"no ULPC vendor source at {vendor}")
        raise typer.Exit(2)
    out = ROOT / "work" / "game" / game / "ulpc"
    cat = ulpc_catalog.build_catalog(vendor, out, log=typer.echo)
    typer.echo(f"[ulpc-catalog] axes: {', '.join(cat['layers'])}")


if __name__ == "__main__":
    app()
