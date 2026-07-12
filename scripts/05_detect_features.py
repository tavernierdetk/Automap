#!/usr/bin/env python
"""Stage 5 (semantic layer) - detect features from ODM's orthophoto + DEM.

The feature pipeline, parallel to geometry: reads the georeferenced orthophoto
(what things look like), the DSM/DTM (how tall things are) and the classified
point cloud (what the reconstruction actually saw), detects trees and
buildings, and writes a world-placed features.json in the same metric frame
as the terrain glb.

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
from typing import Optional

import numpy as np
import rasterio
import typer
from rasterio.enums import Resampling

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automap import worldmodel  # noqa: E402
from automap.config import load_config  # noqa: E402
from automap.features import Road, Water, detect_buildings, detect_trees, slope_degrees  # noqa: E402
from automap.osm import (  # noqa: E402
    building_batch,
    buildings_from_osm,
    coastline_from_osm,
    fetch_osm,
    road_width,
    roads_from_osm,
)

app = typer.Typer(add_completion=False)


def _read_aligned(dsm_p, dtm_p, ortho_p):
    """Read DSM/DTM/ortho onto the DSM grid. Returns chm, rgb, valid, slope, pixel_size.

    ortho_p may be None (geodata scenes have no imagery): rgb comes back None
    and only the DEM masks define validity.
    """
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
    rgb, ortho_valid = None, True
    if ortho_p is not None:
        with rasterio.open(ortho_p) as o_ds:
            rgb = o_ds.read([1, 2, 3], out_shape=(3, H, W), resampling=Resampling.bilinear)
            # the ortho's own no-data (alpha) marks failed-reconstruction holes the
            # DEMs interpolate over; those melt zones must count as invalid
            ortho_valid = o_ds.read_masks(1, out_shape=(H, W), resampling=Resampling.nearest) > 0
        rgb = np.transpose(rgb, (1, 2, 0))

    valid = dsm_valid & dtm_valid & ortho_valid
    if dsm_nod is not None:
        valid &= dsm != dsm_nod
    if dtm_nod is not None:
        valid &= dtm != dtm_nod
    chm = np.where(valid, dsm - dtm, np.nan)
    slope = slope_degrees(np.where(valid, dtm, np.nanmedian(dtm[valid])), px)
    return chm, rgb, valid, slope, dtm, px


def _read_support_xy(laz_p: Path, dsm_p: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """(veg_xy, bld_xy, bld_z) in the centered metric frame, or None.

    Auto-detect / no-op like the SRT sidecar: the gates quietly disengage when
    the point cloud or the laspy dependency is unavailable. When the cloud
    carries ASPRS classification (ODM's DTM step classifies it), vegetation
    points (3/4/5) support trees and building points (6) veto them and seed
    building detection; an unclassified cloud supports trees with every point
    and yields no building evidence.
    """
    if not laz_p.exists():
        return None
    try:
        import laspy
    except ImportError:
        return None
    las = laspy.read(laz_p)
    with rasterio.open(dsm_p) as ds:
        T, H, W, px = ds.transform, ds.height, ds.width, abs(ds.transform.a)
    col = (np.asarray(las.x) - T.c) / T.a
    row = (np.asarray(las.y) - T.f) / T.e
    xy = np.column_stack(((col - (W - 1) / 2.0) * px, (row - (H - 1) / 2.0) * px))
    cls = np.asarray(las.classification)
    is_veg = np.isin(cls, (3, 4, 5))
    if not is_veg.any():
        return xy, xy[:0], np.zeros(0), xy[:0]
    is_bld = cls == 6
    return xy[is_veg], xy[is_bld], np.asarray(las.z)[is_bld], xy[cls == 2]


def _load_osm(cache: Path, dsm_p: Path, log) -> dict | None:
    """The scene's OSM extract: from cache, else fetched+cached, else None.

    Same auto-detect / no-op philosophy as the SRT sidecar and the point
    cloud: no network (or no georeferencing) just means no overlay.
    """
    if cache.exists():
        log(f"osm: using cached {cache.name}")
        return json.loads(cache.read_text())
    from rasterio.warp import transform_bounds
    with rasterio.open(dsm_p) as ds:
        if ds.crs is None:
            log("osm: DSM has no CRS (not georeferenced) - overlay off")
            return None
        bbox = transform_bounds(ds.crs, "EPSG:4326", *ds.bounds)
    try:
        osm = fetch_osm(bbox)
    except Exception as err:  # noqa: BLE001 - offline is a supported mode
        log(f"osm: fetch failed ({err}) - overlay off")
        return None
    cache.write_text(json.dumps(osm))
    log(f"osm: fetched + cached {cache.name}")
    return osm


def _lonlat_to_xz(dsm_p: Path):
    """(lons, lats) -> centered metric (x, z) arrays, via the DSM's CRS."""
    from rasterio.warp import transform as warp_transform
    with rasterio.open(dsm_p) as ds:
        T, H, W, crs = ds.transform, ds.height, ds.width, ds.crs
    px = abs(T.a)

    def go(lons, lats):
        xs, ys = warp_transform("EPSG:4326", crs, list(lons), list(lats))
        col = (np.asarray(xs) - T.c) / T.a
        row = (np.asarray(ys) - T.f) / T.e
        return (col - (W - 1) / 2.0) * px, (row - (H - 1) / 2.0) * px

    return go


@app.command()
def main(
    dsm: Path = typer.Option(..., "--dsm", help="Surface DEM (with trees)"),
    dtm: Path = typer.Option(..., "--dtm", help="Bare-ground DEM"),
    ortho: Optional[Path] = typer.Option(
        None, "--ortho",
        help="Orthophoto; omit for geodata scenes (scan detection off, "
             "OSM features flow through the fusion engine alone)"),
    pointcloud: Path = typer.Option(
        None, "--pointcloud",
        help="Georeferenced .laz (support gate); default: alongside the DEMs"),
    osm: bool = typer.Option(
        True, "--osm/--no-osm",
        help="Join OSM building footprints (fetched once, then cached)"),
    output: Path = typer.Option(..., "--output", help="features.json"),
    config: Path = typer.Option(Path(__file__).resolve().parent.parent / "config.toml", "--config"),
):
    for p in (dsm, dtm) + ((ortho,) if ortho else ()):
        if not p.exists():
            raise typer.BadParameter(f"missing input: {p} (run stage 2 with --terrain)")
    cfg = load_config(config).features
    log = lambda m: typer.echo(f"[stage 5] {m}")

    chm, rgb, valid, slope, dtm_arr, px = _read_aligned(dsm, dtm, ortho)
    log(f"grid {chm.shape[1]}x{chm.shape[0]}  cell={px:.2f}m  canopy_max={np.nanmax(chm):.1f}m")

    if pointcloud is None:
        pointcloud = dsm.parent.parent / "odm_georeferencing" / "odm_georeferenced_model.laz"
    pts = _read_support_xy(pointcloud, dsm) if rgb is not None else None
    if pts is not None:
        support_xy, veto_xy, bld_z, ground_xy = pts
        H, W = dtm_arr.shape
        rr = np.clip(np.round(veto_xy[:, 1] / px + (H - 1) / 2.0).astype(int), 0, H - 1)
        cc = np.clip(np.round(veto_xy[:, 0] / px + (W - 1) / 2.0).astype(int), 0, W - 1)
        bld_xyh = np.column_stack([veto_xy, bld_z - dtm_arr[rr, cc]])
        log(f"support cloud: {len(support_xy)} veg, {len(veto_xy)} building, "
            f"{len(ground_xy)} ground pts")
    else:
        support_xy, veto_xy, bld_xyh, ground_xy = None, None, None, None
        log("support cloud: none (gates off)")

    if rgb is None:
        log("no ortho: scan detection off (geodata mode) - OSM features only")
        trees, buildings = [], []
    else:
        trees = detect_trees(
            chm, rgb, pixel_size=px, valid=valid, slope=slope,
            min_height=cfg.min_height, max_height=cfg.max_height,
            exg_threshold=cfg.exg_threshold, gob_threshold=cfg.gob_threshold,
            max_slope_deg=cfg.max_slope_deg, edge_margin_m=cfg.edge_margin_m,
            min_spacing_m=cfg.min_spacing_m,
            prominence_min=cfg.prominence_min, prominence_radius_m=cfg.prominence_radius_m,
            min_area_m2=cfg.min_area_m2, max_radius_m=cfg.max_radius_m,
            support_xy=support_xy, veto_xy=veto_xy,
            min_support_density=cfg.min_support_density,
        )
        log(f"detected {len(trees)} trees")

        buildings = detect_buildings(
            bld_xyh, support_xy, ground_xy, rgb=rgb, slope=slope, pixel_size=px,
            min_points=cfg.bld_min_points,
            min_height=cfg.bld_min_height, max_height=cfg.bld_max_height,
            min_area_m2=cfg.bld_min_area_m2, max_area_m2=cfg.bld_max_area_m2,
            min_fill=cfg.bld_min_fill, min_side_m=cfg.bld_min_side_m,
            max_blueness=cfg.bld_max_blueness, gable_delta=cfg.gable_delta,
        )
        log(f"detected {len(buildings)} buildings")

    osm_batch: list[dict] = []
    if osm:
        osm_doc = _load_osm(output.parent / "osm.json", dsm, log)
        if osm_doc is not None:
            to_xz = _lonlat_to_xz(dsm)
            osm_blds = buildings_from_osm(osm_doc, to_xz)
            roads = [Road(path=[tuple(p) for p in r["path"]],
                          width=road_width(r["tags"]),
                          kind=r["tags"].get("highway", "road"))
                     for r in roads_from_osm(osm_doc, to_xz)]
            coast = coastline_from_osm(osm_doc, to_xz)
            osm_batch = (building_batch(osm_blds, level_m=cfg.osm_level_m)
                         + [r.as_feature() for r in roads])
            if coast:
                osm_batch.append(Water(
                    kind="sea", outline=[tuple(p) for c in coast for p in c]).as_feature())
            log(f"osm: {len(osm_blds)} footprints, {len(roads)} roads, "
                f"{'sea (from ' + str(len(coast)) + ' coastline ways)' if coast else 'no water'}")

    # fusion: the scan pass and the OSM pass are two observation sources
    # reconciled into the per-scene world model. Re-runs match against the
    # existing document, so stable ids and manual edits survive regeneration.
    if output.exists():
        doc = worldmodel.load(output)
        log(f"worldmodel: fusing into existing {output.name} "
            f"({len(doc['features'])} features)")
    else:
        doc = worldmodel.new_document(scene=output.parent.name)
    doc = worldmodel.fuse(
        doc, [t.as_feature() for t in trees] + [b.as_feature() for b in buildings],
        "scan", observed_types={"tree", "building"})
    if osm_batch:
        doc = worldmodel.fuse(
            doc, osm_batch, "osm",
            observed_types={"building", "road", "water"},
            match_dist={"building": cfg.osm_match_dist_m})

        # LiDAR heights: the DSM knows what OSM tags don't. Same footprints,
        # source "lidar" — per-attribute priority keeps OSM's footprint and
        # scan's height where present, and lidar outranks tag defaults.
        osm_fps = [f["footprint"] for f in osm_batch if f.get("type") == "building"]
        if osm_fps:
            from automap.geodata import building_heights_from_dems
            hs = building_heights_from_dems(dtm, dsm, osm_fps)
            lidar_batch = []
            for fp, h in zip(osm_fps, hs):
                if h is None:
                    continue
                feat = {"type": "building", "footprint": fp, **h}
                feat["roof"] = "gable" if h["ridge"] - h["height"] >= 1.5 else "flat"
                lidar_batch.append(feat)
            if lidar_batch:
                doc = worldmodel.fuse(
                    doc, lidar_batch, "lidar", observed_types={"building"},
                    match_dist={"building": cfg.osm_match_dist_m})
            log(f"lidar heights: {len(lidar_batch)}/{len(osm_fps)} footprints measured "
                f"from DSM-DTM")
    doc = worldmodel.finalize(doc, building_defaults={
        "height": cfg.osm_default_wall, "ridge": cfg.osm_default_ridge})

    blds = [f for f in doc["features"] if f["type"] == "building"]
    srcs = [f.get("source", "") for f in blds]
    log(f"buildings: {srcs.count('osm+scan')} matched, "
        f"{sum(1 for s in srcs if s in ('osm', 'default+osm'))} osm-backfilled, "
        f"{srcs.count('scan')} scan-only ({len(blds)} total)")

    output.parent.mkdir(parents=True, exist_ok=True)
    if worldmodel.validate(doc):
        log(f"worldmodel: valid against scene-features@{worldmodel.SPEC[1]}")
    worldmodel.save(doc, output)
    log(f"wrote {output} ({len(doc['features'])} features)")


if __name__ == "__main__":
    app()
