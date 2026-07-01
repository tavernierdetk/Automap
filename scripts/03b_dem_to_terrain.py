#!/usr/bin/env python
"""Stage 3b (terrain-first) - turn an ODM DEM + orthophoto into a terrain .glb.

The terrain-first alternative to stage 3: instead of decimating the lumpy scan
mesh, build a clean regular grid displaced by the DTM (bare ground) and textured
with the orthophoto. Produces the same Y-up .glb hand-off as stage 3.

    python scripts/03b_dem_to_terrain.py \
        --dtm work/<name>/odm/odm_dem/dtm.tif \
        --ortho work/<name>/odm/odm_orthophoto/odm_orthophoto.tif \
        --output work/<name>/mesh/<name>.glb [--grid 256] [--use-dsm dsm.tif]

2.5D by design (one height per x,z): great for open ground, cannot represent
cliffs/overhangs - that's the mesh-first path's job. See
docs/explorations/terrain-first.md.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import rasterio
import trimesh
import typer
from PIL import Image
from rasterio.enums import Resampling

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automap.config import load_config  # noqa: E402
from automap.terrain import build_grid_mesh  # noqa: E402

app = typer.Typer(add_completion=False)


def _read_heightmap(path: Path, grid: int):
    """Downsample a DEM GeoTIFF to ~grid cells on the long edge. Returns (h, mask, px)."""
    with rasterio.open(path) as ds:
        scale = max(ds.height, ds.width) / grid
        new_h = max(round(ds.height / scale), 2)
        new_w = max(round(ds.width / scale), 2)
        h = ds.read(1, out_shape=(new_h, new_w), resampling=Resampling.bilinear).astype(np.float64)
        mask = ds.read_masks(1, out_shape=(new_h, new_w), resampling=Resampling.nearest) > 0
        px = abs(ds.transform.a) * scale
        if ds.nodata is not None:
            mask &= h != ds.nodata
        mask &= np.isfinite(h)
    return h, mask, px


def _read_texture(path: Path, max_px: int = 2048) -> Image.Image:
    with rasterio.open(path) as ds:
        scale = max(max(ds.height, ds.width) / max_px, 1.0)
        th, tw = round(ds.height / scale), round(ds.width / scale)
        rgb = ds.read([1, 2, 3], out_shape=(3, th, tw), resampling=Resampling.bilinear)
    return Image.fromarray(np.transpose(rgb, (1, 2, 0)).astype(np.uint8), "RGB")


@app.command()
def main(
    dtm: Path = typer.Option(..., "--dtm", help="Bare-ground DEM GeoTIFF"),
    ortho: Path = typer.Option(..., "--ortho", help="Orthophoto GeoTIFF (ground texture)"),
    output: Path = typer.Option(..., "--output", help="Output .glb"),
    use_dsm: Optional[Path] = typer.Option(None, "--use-dsm", help="Use this DSM instead of the DTM (keeps trees as bumps)"),
    grid: Optional[int] = typer.Option(None, "--grid", help="Grid cells on the long edge"),
    config: Path = typer.Option(Path(__file__).resolve().parent.parent / "config.toml", "--config"),
):
    cfg = load_config(config).terrain
    grid = grid or cfg.grid_resolution
    dem = use_dsm or dtm
    if not dem.exists():
        raise typer.BadParameter(f"DEM not found: {dem}")
    if not ortho.exists():
        raise typer.BadParameter(f"orthophoto not found: {ortho}")

    log = lambda m: typer.echo(f"[stage 3b] {m}")
    log(f"reading {'DSM' if use_dsm else 'DTM'} {dem.name} -> grid ~{grid}")
    h, mask, px = _read_heightmap(dem, grid)
    log(f"grid {h.shape[1]}x{h.shape[0]}  cell={px:.2f}m  valid={int(mask.sum())}/{mask.size}")

    verts, faces, uvs = build_grid_mesh(
        h, pixel_size=px, valid_mask=mask, z_exaggeration=cfg.z_exaggeration,
    )
    size = verts.max(axis=0) - verts.min(axis=0)
    log(f"mesh: {len(verts)} verts, {len(faces)} faces, extent X={size[0]:.0f} Y={size[1]:.0f} Z={size[2]:.0f} m")

    tex = _read_texture(ortho)
    material = trimesh.visual.material.PBRMaterial(
        baseColorTexture=tex, metallicFactor=0.0, roughnessFactor=1.0
    )
    mesh = trimesh.Trimesh(
        vertices=verts, faces=faces,
        visual=trimesh.visual.TextureVisuals(uv=uvs, material=material),
        process=False,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(output)
    log(f"wrote {output} ({output.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    app()
