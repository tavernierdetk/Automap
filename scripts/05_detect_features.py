#!/usr/bin/env python
"""Stage 5 (semantic layer) - detect features from ODM's orthophoto + DEM.

The feature pipeline, parallel to geometry: reads the georeferenced orthophoto
(what things look like) and the DSM/DTM (how tall they are), detects trees, and
writes a world-placed features.json in the same metric frame as the terrain glb.

    python scripts/05_detect_features.py \
        --dsm work/<name>/odm/odm_dem/dsm.tif \
        --dtm work/<name>/odm/odm_dem/dtm.tif \
        --ortho work/<name>/odm/odm_orthophoto/odm_orthophoto.tif \
        --output work/<name>/features.json

Requires terrain-mode ODM outputs (run stage 2 with --terrain). See
docs/explorations/feature-substitution.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
import typer
from rasterio.enums import Resampling

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automap.config import load_config  # noqa: E402
from automap.features import detect_trees  # noqa: E402

app = typer.Typer(add_completion=False)


def _read_aligned(dsm_p, dtm_p, ortho_p):
    """Read DSM/DTM/ortho onto the DSM grid. Returns chm, rgb, valid, pixel_size."""
    with rasterio.open(dsm_p) as dsm_ds:
        H, W = dsm_ds.height, dsm_ds.width
        px = abs(dsm_ds.transform.a)
        dsm = dsm_ds.read(1).astype(np.float64)
        dsm_valid = dsm_ds.read_masks(1) > 0
        dsm_nod = dsm_ds.nodata
    with rasterio.open(dtm_p) as dtm_ds:
        dtm = dtm_ds.read(1, out_shape=(H, W), resampling=Resampling.bilinear).astype(np.float64)
        dtm_valid = dtm_ds.read_masks(1, out_shape=(H, W), resampling=Resampling.nearest) > 0
        dtm_nod = dtm_ds.nodata
    with rasterio.open(ortho_p) as o_ds:
        rgb = o_ds.read([1, 2, 3], out_shape=(3, H, W), resampling=Resampling.bilinear)
    rgb = np.transpose(rgb, (1, 2, 0))

    valid = dsm_valid & dtm_valid
    if dsm_nod is not None:
        valid &= dsm != dsm_nod
    if dtm_nod is not None:
        valid &= dtm != dtm_nod
    chm = np.where(valid, dsm - dtm, np.nan)
    return chm, rgb, valid, px


@app.command()
def main(
    dsm: Path = typer.Option(..., "--dsm", help="Surface DEM (with trees)"),
    dtm: Path = typer.Option(..., "--dtm", help="Bare-ground DEM"),
    ortho: Path = typer.Option(..., "--ortho", help="Orthophoto"),
    output: Path = typer.Option(..., "--output", help="features.json"),
    config: Path = typer.Option(Path(__file__).resolve().parent.parent / "config.toml", "--config"),
):
    for p in (dsm, dtm, ortho):
        if not p.exists():
            raise typer.BadParameter(f"missing input: {p} (run stage 2 with --terrain)")
    cfg = load_config(config).features
    log = lambda m: typer.echo(f"[stage 5] {m}")

    chm, rgb, valid, px = _read_aligned(dsm, dtm, ortho)
    log(f"grid {chm.shape[1]}x{chm.shape[0]}  cell={px:.2f}m  canopy_max={np.nanmax(chm):.1f}m")

    trees = detect_trees(
        chm, rgb, pixel_size=px, valid=valid,
        min_height=cfg.min_height, exg_threshold=cfg.exg_threshold,
        min_spacing_m=cfg.min_spacing_m,
    )
    log(f"detected {len(trees)} trees")

    output.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "frame": "centered-metric-yup",
        "features": [t.as_feature() for t in trees],
    }
    output.write_text(json.dumps(doc, indent=2) + "\n")
    log(f"wrote {output}")


if __name__ == "__main__":
    app()
