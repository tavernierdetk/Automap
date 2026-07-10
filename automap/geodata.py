"""Public elevation for a named scene (ingest-geodata v1, end-state B).

Provider: NRCan HRDEM via the datacube STAC API — a bbox search picks the
best item (newest project-level `hrdem-lidar` acquisition, falling back to
the seamless 1 m mosaic), and the DTM/DSM are read as **windowed COG reads
over HTTPS** (seconds for a village-sized bbox; the mosaics never download
whole). Rasters are reprojected to the bbox's UTM zone so downstream code
sees the exact same shape of artifact the drone path produces, then cached
under work/<scene>/geodata/ — re-runs are offline, like osm.json.

Network happens only in stac_search() and fetch_dem(); everything else is
pure. HRDEM is Canada Open Government Licence (attribution, no share-alike).
"""
from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds

STAC_SEARCH = "https://datacube.services.geo.ca/stac/api/search"
USER_AGENT = "automap/0.1 (personal drone-scan pipeline)"


def utm_epsg(lon: float, lat: float) -> str:
    """EPSG code of the WGS84 UTM zone containing (lon, lat)."""
    zone = int(math.floor((lon + 180.0) / 6.0)) + 1
    return f"EPSG:{(32600 if lat >= 0 else 32700) + zone}"


def stac_search(bbox_wgs84, collection: str, limit: int = 20) -> list[dict]:
    """STAC items of one collection intersecting bbox (west,south,east,north)."""
    url = (f"{STAC_SEARCH}?collections={collection}"
           f"&bbox={','.join(f'{v:.6f}' for v in bbox_wgs84)}&limit={limit}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp).get("features", [])


def candidates(lidar_items: list[dict], mosaic_items: list[dict]) -> list[dict]:
    """Preference order: newest project LiDAR first, then the seamless mosaic.

    Order is a *preference*, not a verdict: STAC footprints over-claim (a
    Nova Scotia 2020 survey "intersects" the Magdalen Islands bbox), so the
    caller must confirm real pixels with has_coverage() before fetching.
    """
    lid = [i for i in lidar_items
           if "dtm" in i.get("assets", {}) and "dsm" in i.get("assets", {})]
    lid.sort(key=lambda i: i.get("properties", {}).get("datetime") or i["id"],
             reverse=True)
    return lid + [i for i in mosaic_items if "dtm" in i.get("assets", {})]


def has_coverage(href: str, bbox_wgs84, *, min_valid: float = 0.3) -> bool:
    """Cheap COG probe: does href hold real data over the bbox center?"""
    w, s, e, n = bbox_wgs84
    cx, cy, dx, dy = (w + e) / 2, (s + n) / 2, (e - w) / 10, (n - s) / 10
    with rasterio.open(href) as src:
        win = from_bounds(*transform_bounds("EPSG:4326", src.crs,
                                            cx - dx, cy - dy, cx + dx, cy + dy),
                          src.transform)
        arr = src.read(1, window=win, out_shape=(32, 32), boundless=True,
                       fill_value=src.nodata if src.nodata is not None else -32767.0)
        nodata = src.nodata if src.nodata is not None else -32767.0
    return float((arr != nodata).mean()) >= min_valid


def fetch_dem(
    href: str,
    bbox_wgs84,
    out_path: str | Path,
    *,
    dst_crs: str | None = None,
    resolution: float = 1.0,
) -> Path:
    """Windowed COG read of bbox from href, reprojected to dst_crs (default:
    the bbox's UTM zone), written as a GeoTIFF. Returns out_path."""
    w, s, e, n = bbox_wgs84
    if dst_crs is None:
        dst_crs = utm_epsg((w + e) / 2.0, (s + n) / 2.0)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # destination grid = exactly the requested bbox, axis-aligned in UTM
    dw, ds_, de, dn = transform_bounds("EPSG:4326", dst_crs, w, s, e, n)
    width = max(int(round((de - dw) / resolution)), 2)
    height = max(int(round((dn - ds_) / resolution)), 2)
    dst_transform = rasterio.transform.from_origin(dw, dn, resolution, resolution)

    with rasterio.open(href) as src:
        # source window padded so the (rotated) reprojection covers the
        # destination corners
        sw, ss, se_, sn = transform_bounds(dst_crs, src.crs, dw, ds_, de, dn)
        pad = 0.05 * max(se_ - sw, sn - ss) + 2 * resolution
        win = from_bounds(sw - pad, ss - pad, se_ + pad, sn + pad, src.transform)
        data = src.read(1, window=win, boundless=True,
                        fill_value=src.nodata if src.nodata is not None else -32767.0)
        win_transform = src.window_transform(win)
        nodata = src.nodata if src.nodata is not None else -32767.0
        dst = np.full((height, width), nodata, dtype=np.float32)
        reproject(
            source=data, destination=dst,
            src_transform=win_transform, src_crs=src.crs,
            dst_transform=dst_transform, dst_crs=dst_crs,
            src_nodata=nodata, dst_nodata=nodata,
            resampling=Resampling.bilinear)
        profile = {
            "driver": "GTiff", "count": 1, "dtype": "float32",
            "width": width, "height": height, "crs": dst_crs,
            "transform": dst_transform, "nodata": nodata,
            "compress": "deflate", "tiled": True,
        }
    with rasterio.open(out_path, "w", **profile) as out:
        out.write(dst, 1)
    return out_path


def fetch_scene_geodata(
    bbox_wgs84,
    dest_dir: str | Path,
    *,
    on_log=lambda _m: None,
) -> dict:
    """DTM + DSM for a bbox into dest_dir/{dtm,dsm}.tif (cached if present).

    Returns {"dtm": Path, "dsm": Path|None, "item": id, "collection": name}.
    """
    dest = Path(dest_dir)
    dtm_p, dsm_p, meta_p = dest / "dtm.tif", dest / "dsm.tif", dest / "source.json"
    if dtm_p.exists() and meta_p.exists():
        meta = json.loads(meta_p.read_text())
        on_log(f"geodata: using cached {dest} ({meta.get('item')})")
        return {"dtm": dtm_p, "dsm": dsm_p if dsm_p.exists() else None, **meta}

    item = None
    for cand in candidates(stac_search(bbox_wgs84, "hrdem-lidar"),
                           stac_search(bbox_wgs84, "hrdem-mosaic-1m")):
        if has_coverage(cand["assets"]["dtm"]["href"], bbox_wgs84):
            item = cand
            break
        on_log(f"geodata: {cand['id']} claims the bbox but has no pixels there - skipped")
    if item is None:
        raise RuntimeError(f"no HRDEM coverage for bbox {bbox_wgs84}")
    assets, meta = item["assets"], {"item": item["id"], "collection": item["collection"]}
    on_log(f"geodata: {item['id']} ({meta['collection']})")

    fetch_dem(assets["dtm"]["href"], bbox_wgs84, dtm_p)
    on_log(f"geodata: wrote {dtm_p.name}")
    dsm = None
    if "dsm" in assets:
        dsm = fetch_dem(assets["dsm"]["href"], bbox_wgs84, dsm_p)
        on_log(f"geodata: wrote {dsm_p.name}")
    dest.mkdir(parents=True, exist_ok=True)
    meta_p.write_text(json.dumps(meta, indent=2) + "\n")
    return {"dtm": dtm_p, "dsm": dsm, **meta}
