"""OSM overlay for the semantic layer (slice 3 of semantic-layer-v2).

The scan is georeferenced (geo.txt -> UTM), so we can pull OpenStreetMap
building footprints for the scene bbox and join them with the scan-detected
buildings:

- a detected building that matches an OSM footprint keeps its scanned heights
  / roof / color but adopts the surveyed OSM footprint (scan footprints run
  fat from photogrammetry melt) -> source "scan+osm";
- an OSM footprint nobody detected is backfilled with default or tag-derived
  heights -> source "osm" (fixes edge-of-scene recall where the cloud is thin);
- a detection without OSM counterpart is kept as-is -> source "scan" (OSM
  coverage is incomplete too).

Network happens only in fetch_osm(); everything else is pure so it stays
testable offline. The stage-5 script caches the Overpass response next to
features.json, making re-runs reproducible without a connection.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

import cv2
import numpy as np

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)


def overpass_query(bbox_wgs84: tuple[float, float, float, float]) -> str:
    """Overpass QL for the scene bbox (west, south, east, north).

    Buildings feed the merge; highways become road features, coastline
    anchors the sea level; standing water rides along for later.
    """
    w, s, e, n = bbox_wgs84
    bb = f"({s},{w},{n},{e})"
    return (
        "[out:json][timeout:60];("
        f'way["building"]{bb};'
        f'way["highway"]{bb};'
        f'way["natural"="coastline"]{bb};'
        f'way["natural"="water"]{bb};'
        ");out geom tags;"
    )


def fetch_osm(bbox_wgs84, timeout: float = 90.0) -> dict:
    """Fetch the scene's OSM extract. Raises on network/HTTP failure."""
    data = urllib.parse.urlencode({"data": overpass_query(bbox_wgs84)}).encode()
    last_err: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        req = urllib.request.Request(
            endpoint, data=data, headers={"User-Agent": "automap/0.1 (personal drone-scan pipeline)"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except Exception as err:  # noqa: BLE001 - any endpoint failure -> try next
            last_err = err
    raise RuntimeError(f"all Overpass endpoints failed: {last_err}")


def buildings_from_osm(osm: dict, lonlat_to_xz) -> list[dict]:
    """OSM building ways -> [{'poly': (N,2) metric array, 'tags': {...}}].

    lonlat_to_xz maps (lons, lats) arrays to the centered metric frame.
    """
    out = []
    for el in osm.get("elements", []):
        if el.get("type") != "way" or "building" not in el.get("tags", {}):
            continue
        geom = el.get("geometry") or []
        if len(geom) < 4:  # closed way = at least a triangle + repeat node
            continue
        lons = np.array([g["lon"] for g in geom], float)
        lats = np.array([g["lat"] for g in geom], float)
        x, z = lonlat_to_xz(lons, lats)
        out.append({"poly": np.column_stack([x, z]), "tags": el.get("tags", {})})
    return out


ROAD_WIDTHS_M = {
    "motorway": 12.0, "trunk": 10.0, "primary": 8.0, "secondary": 7.0,
    "tertiary": 6.5, "residential": 6.0, "unclassified": 5.0, "service": 4.0,
    "track": 3.0, "footway": 1.8, "path": 1.5, "cycleway": 2.0, "steps": 1.5,
}


def road_width(tags: dict, default: float = 5.0) -> float:
    """Road width in meters: explicit width tag, else by highway class."""
    try:
        if "width" in tags:
            return float(str(tags["width"]).split()[0].replace("m", ""))
    except ValueError:
        pass
    return ROAD_WIDTHS_M.get(tags.get("highway", ""), default)


def roads_from_osm(osm: dict, lonlat_to_xz) -> list[dict]:
    """OSM highway ways -> [{'path': (N,2) metric array, 'tags': {...}}]."""
    out = []
    for el in osm.get("elements", []):
        if el.get("type") != "way" or "highway" not in el.get("tags", {}):
            continue
        geom = el.get("geometry") or []
        if len(geom) < 2:
            continue
        x, z = lonlat_to_xz(np.array([g["lon"] for g in geom], float),
                            np.array([g["lat"] for g in geom], float))
        out.append({"path": np.column_stack([x, z]), "tags": el.get("tags", {})})
    return out


def coastline_from_osm(osm: dict, lonlat_to_xz) -> list[np.ndarray]:
    """OSM coastline ways -> list of (N,2) metric polylines."""
    out = []
    for el in osm.get("elements", []):
        if el.get("type") != "way" or el.get("tags", {}).get("natural") != "coastline":
            continue
        geom = el.get("geometry") or []
        if len(geom) < 2:
            continue
        x, z = lonlat_to_xz(np.array([g["lon"] for g in geom], float),
                            np.array([g["lat"] for g in geom], float))
        out.append(np.column_stack([x, z]))
    return out


def tag_heights(tags: dict, level_m: float = 3.0) -> tuple[float, float] | None:
    """(wall, ridge) from OSM tags, or None if untagged."""
    try:
        if "height" in tags:
            ridge = float(str(tags["height"]).split()[0].replace("m", ""))
            return max(ridge * 0.6, 2.0), ridge
        if "building:levels" in tags:
            wall = float(tags["building:levels"]) * level_m
            return max(wall, 2.0), max(wall, 2.0) + 1.5
    except ValueError:
        pass
    return None


def merge_osm_buildings(
    detected: list,
    osm_blds: list[dict],
    *,
    default_wall: float = 3.0,
    default_ridge: float = 5.0,
    default_color: tuple = (150, 145, 140),
    level_m: float = 3.0,
    match_dist_m: float = 12.0,
) -> list:
    """Join scan detections with OSM footprints (see module docstring).

    detected is a list of automap.features.Building; returns a new list.
    Matching is greedy nearest-centroid, one-to-one, within match_dist_m.
    """
    from automap.features import Building

    osm_rects = []
    for ob in osm_blds:
        pts = ob["poly"][:-1] if np.allclose(ob["poly"][0], ob["poly"][-1]) else ob["poly"]
        rect = cv2.boxPoints(cv2.minAreaRect(pts.astype(np.float32)))
        osm_rects.append({
            "corners": [(float(x), float(z)) for x, z in rect],
            "centroid": pts.mean(axis=0),
            "tags": ob["tags"],
        })

    det_centroids = [np.asarray(b.footprint).mean(axis=0) for b in detected]
    pairs = sorted(
        ((float(np.linalg.norm(det_centroids[i] - r["centroid"])), i, j)
         for i in range(len(detected)) for j, r in enumerate(osm_rects)),
        key=lambda t: t[0])
    det_match: dict[int, int] = {}
    osm_taken: set[int] = set()
    for dist, i, j in pairs:
        if dist > match_dist_m:
            break
        if i in det_match or j in osm_taken:
            continue
        det_match[i] = j
        osm_taken.add(j)

    merged: list = []
    for i, b in enumerate(detected):
        j = det_match.get(i)
        if j is None:
            merged.append(b)
        else:
            merged.append(Building(
                footprint=osm_rects[j]["corners"], height=b.height, ridge=b.ridge,
                roof=b.roof, roof_color=b.roof_color, source="scan+osm"))
    for j, r in enumerate(osm_rects):
        if j in osm_taken:
            continue
        th = tag_heights(r["tags"], level_m)
        wall, ridge = th if th else (default_wall, default_ridge)
        merged.append(Building(
            footprint=r["corners"], height=wall, ridge=ridge,
            roof="gable" if ridge - wall >= 1.0 else "flat",
            roof_color=default_color, source="osm"))
    return merged
