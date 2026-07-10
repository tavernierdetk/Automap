#!/usr/bin/env python
"""Stage 2b (geodata intake) - public elevation instead of a drone scan.

The end-state-B alternative to stage 2: no footage, no ODM. Fetches the best
open LiDAR DTM/DSM covering a bbox (NRCan HRDEM, COG windowed reads - see
docs/explorations/end-state-b.md) into work/<scene>/geodata/, reprojected to
the bbox's UTM zone so stages 3b/5 consume it exactly like ODM's DEMs.

    python scripts/02b_fetch_geodata.py --scene lagrave \
        --center 47.2375,-61.8353 --size 1200

    python scripts/02b_fetch_geodata.py --scene lagrave \
        --bbox -61.843,47.232,-61.827,47.243

Cached: re-runs with an existing work/<scene>/geodata/ are offline no-ops.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Optional

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automap.geodata import fetch_scene_geodata  # noqa: E402

app = typer.Typer(add_completion=False)


@app.command()
def main(
    scene: str = typer.Option(..., "--scene", help="Scene name (work/<scene>/)"),
    center: Optional[str] = typer.Option(
        None, "--center", help="lat,lon of the scene center (with --size)"),
    size: float = typer.Option(1200.0, "--size", help="Scene edge length (m), with --center"),
    bbox: Optional[str] = typer.Option(
        None, "--bbox", help="west,south,east,north (WGS84); overrides --center"),
    root: Path = typer.Option(Path(__file__).resolve().parent.parent, "--root"),
):
    log = lambda m: typer.echo(f"[stage 2b] {m}")
    if bbox:
        w, s, e, n = (float(v) for v in bbox.split(","))
    elif center:
        lat, lon = (float(v) for v in center.split(","))
        dlat = (size / 2.0) / 111_320.0
        dlon = dlat / math.cos(math.radians(lat))
        w, s, e, n = lon - dlon, lat - dlat, lon + dlon, lat + dlat
    else:
        raise typer.BadParameter("pass --bbox or --center")

    log(f"scene '{scene}' bbox ({w:.5f}, {s:.5f}, {e:.5f}, {n:.5f})")
    out = fetch_scene_geodata((w, s, e, n), root / "work" / scene / "geodata", on_log=log)
    log(f"source: {out['item']} [{out['collection']}] (HRDEM, Canada OGL)")
    log(f"next: scripts/03b_dem_to_terrain.py --dtm {out['dtm']} "
        f"--output work/{scene}/mesh/_base_{scene}.glb")


if __name__ == "__main__":
    app()
