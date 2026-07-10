#!/usr/bin/env python
"""Stage 9 (building substitution) - drop an IFC plan in to replace a building.

Takes any scene's world model (drone or geodata) and an external IFC building
model, and swaps a generated proxy building for the authored model:

    python scripts/09_replace_building.py --scene lagrave \\
        --ifc plans/manoir.ifc --id building-0007

Steps: read the plan (ifc.from_ifc) -> compute placement onto the target
building (georeference if the IFC carries an IfcMapConversion, else footprint-
fit) -> tessellate the plan into work/<scene>/assets/<id>.glb in the scene
frame -> write a `representation` override onto the building via the fusion
engine (source "bim", so it outranks detectors and survives every re-run).

Re-run stage 6 afterwards to see it; a later stage-5 detection pass will not
clobber it (that's the whole point of the world model's provenance).
The plan's own materials are kept; pass --restyle at stage 6 to repaint.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automap import ifc, placement as placement_mod, worldmodel  # noqa: E402

app = typer.Typer(add_completion=False)


def _anchor_raster(scene_dir: Path) -> Optional[Path]:
    for rel in ("geodata/dtm.tif", "odm/odm_dem/dsm.tif", "geodata/dsm.tif"):
        if (scene_dir / rel).exists():
            return scene_dir / rel
    return None


@app.command()
def main(
    scene: str = typer.Option(..., "--scene", help="Scene name (work/<scene>/)"),
    ifc_path: Path = typer.Option(..., "--ifc", help="External building .ifc"),
    building_id: str = typer.Option(..., "--id", help="Target building id in features.json"),
    georeference: bool = typer.Option(
        True, "--georeference/--footprint-fit",
        help="Use the IFC's IfcMapConversion if present (default); --footprint-fit forces "
             "centroid+axis alignment to the target footprint"),
    extra_yaw: float = typer.Option(0.0, "--rotate", help="Extra yaw (deg) nudge"),
    root: Path = typer.Option(Path(__file__).resolve().parent.parent, "--root"),
):
    if not ifc.available():
        raise typer.BadParameter("ifcopenshell missing - install with: pip install -e '.[ifc]'")
    if not ifc_path.exists():
        raise typer.BadParameter(f"IFC not found: {ifc_path}")
    log = lambda m: typer.echo(f"[stage 9] {m}")

    scene_dir = root / "work" / scene
    features_p = scene_dir / "features.json"
    if not features_p.exists():
        raise typer.BadParameter(f"no features.json for {scene!r} (run stage 5)")
    doc = worldmodel.load(features_p)
    target = next((f for f in doc["features"]
                   if f.get("type") == "building" and f.get("id") == building_id), None)
    if target is None:
        ids = [f["id"] for f in doc["features"] if f.get("type") == "building"][:8]
        raise typer.BadParameter(f"no building {building_id!r}; e.g. {ids}")

    plan = ifc.from_ifc(ifc_path)
    src_anchor = ifc.read_anchor(ifc_path) if georeference else None

    # placement: georeference when available, else fit the plan's footprint
    # onto the target's; then apply any manual yaw nudge.
    if src_anchor is not None:
        raster = _anchor_raster(scene_dir)
        if raster is None:
            raise typer.BadParameter("IFC is georeferenced but scene has no raster anchor; "
                                     "re-run with --footprint-fit")
        place = placement_mod.from_georeference(
            src_anchor, ifc.scene_anchor(raster), target["footprint"])
        log(f"placement: georeference {src_anchor['crs']} -> scene "
            f"(dx={place.translate_xz[0]:.1f}, dz={place.translate_xz[1]:.1f} m)")
    else:
        place = placement_mod.fit_footprint(plan["footprint"], target["footprint"])
        log(f"placement: footprint-fit (yaw={place.yaw_deg:.1f}°, "
            f"centroid {tuple(round(v, 1) for v in place.ground_xz)})")
    if extra_yaw:
        place = placement_mod.Placement(place.yaw_deg + extra_yaw,
                                        place.translate_xz, place.ground_xz)

    asset_rel = f"assets/{building_id}.glb"
    info = ifc.ifc_to_glb(ifc_path, scene_dir / asset_rel, placement=place)
    log(f"tessellated -> {asset_rel} (size {info['size'][0]}x{info['size'][2]} m "
        f"footprint, {info['size'][1]} m tall)")

    # targeting is explicit (by id), so set the override on the chosen
    # building directly and mark the touched attributes source "bim" — which
    # outranks every detector, so a later stage-5 re-run cannot clobber it.
    try:
        source_ifc = str(ifc_path.resolve().relative_to(root.resolve()))
    except ValueError:
        source_ifc = str(ifc_path)
    prov = target.setdefault("provenance", {})
    target["footprint"] = info["footprint_xz"]; prov["footprint"] = worldmodel.BIM
    if "height" in plan:
        target["height"] = plan["height"]; prov["height"] = worldmodel.BIM
    target["representation"] = {
        "kind": "asset", "asset": asset_rel, "source_ifc": source_ifc,
        "ground_xz": [round(float(place.ground_xz[0]), 3),
                      round(float(place.ground_xz[1]), 3)],
    }
    prov["representation"] = worldmodel.BIM
    doc = worldmodel.finalize(doc)
    if worldmodel.validate(doc):
        log(f"worldmodel: valid against scene-features@{worldmodel.SPEC[1]}")
    worldmodel.save(doc, features_p)

    log(f"replaced {building_id} with {ifc_path.name}; re-run stage 6 to render:")
    log(f"    python scripts/06_style_scene.py --source work/{scene}/mesh/_base_{scene}.glb "
        f"--features {features_p} --identity <id> --output work/{scene}/mesh/sf_{scene}.glb")


if __name__ == "__main__":
    app()
