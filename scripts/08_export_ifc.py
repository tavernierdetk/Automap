#!/usr/bin/env python
"""Stage 8 (IFC projection) - the world model's buildings -> georeferenced IFC.

The dual emission (brief §1b): a building leaves the world model as styled
game geometry (stage 6) AND as a standalone .ifc here - both projections of
one record. One file per building under work/<scene>/ifc/, georeferenced by
IfcMapConversion against the scene raster.

    python scripts/08_export_ifc.py --scene lagrave

Reads work/<scene>/features.json + a raster for the georeference anchor
(geodata/dtm.tif, else odm DSM). Needs the ifc extra: pip install -e '.[ifc]'.

The reverse direction (a plan->IFC model, e.g. an external CubiCasa pipeline,
back into the world model) is automap.ifc.from_ifc — fuse its output with
source "bim". No importer script yet; add one when a real inbound source is
wired.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automap import ifc, worldmodel  # noqa: E402

app = typer.Typer(add_completion=False)


def _anchor_raster(scene_dir: Path) -> Optional[Path]:
    for rel in ("geodata/dtm.tif", "odm/odm_dem/dsm.tif", "geodata/dsm.tif"):
        p = scene_dir / rel
        if p.exists():
            return p
    return None


@app.command()
def main(
    scene: str = typer.Option(..., "--scene", help="Scene name (work/<scene>/)"),
    root: Path = typer.Option(Path(__file__).resolve().parent.parent, "--root"),
    georeference: bool = typer.Option(
        True, "--georeference/--no-georeference",
        help="Anchor via IfcMapConversion from the scene raster's CRS"),
):
    if not ifc.available():
        raise typer.BadParameter("ifcopenshell missing - install with: pip install -e '.[ifc]'")
    log = lambda m: typer.echo(f"[stage 8] {m}")
    scene_dir = root / "work" / scene
    features = scene_dir / "features.json"
    if not features.exists():
        raise typer.BadParameter(f"no features.json for {scene!r} (run stage 5)")

    doc = worldmodel.load(features)
    anchor = None
    if georeference:
        raster = _anchor_raster(scene_dir)
        if raster is None:
            log("no scene raster found - exporting without georeference")
        else:
            anchor = ifc.scene_anchor(raster)
            log(f"georeference: {anchor['crs']} @ E={anchor['eastings']:.1f} "
                f"N={anchor['northings']:.1f} (from {raster.name})")

    written = ifc.export_scene(doc, scene_dir / "ifc", scene=scene,
                               anchor=anchor, on_log=log)
    n_bld = sum(1 for f in doc["features"] if f["type"] == "building")
    log(f"exported {len(written)}/{n_bld} buildings to {scene_dir / 'ifc'}")


if __name__ == "__main__":
    app()
