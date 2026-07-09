"""OSM overlay for the semantic layer (slice 3 of semantic-layer-v2).

The scan is georeferenced (geo.txt -> UTM), so we can pull OpenStreetMap
building footprints, roads, coastline and water for the scene bbox. This
module only fetches and parses; reconciliation with the scan detections is
the fusion engine's job (automap.worldmodel) — OSM is one observation source
among several, feeding per-attribute merges (footprint: OSM over scan;
heights: scan over tags; unmatched footprints backfill edge-of-scene recall).

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


def building_batch(osm_blds: list[dict], level_m: float = 3.0) -> list[dict]:
    """OSM buildings -> world-model observation dicts for the fusion engine.

    Each carries only what OSM actually knows: the footprint always
    (rectified to a min-area rectangle so the proxy builder gets 4 corners),
    heights + roof form only when tagged. The fusion engine settles conflicts
    per attribute (footprint: OSM over scan; heights: scan over tags) and
    finalize() fills defaults on backfilled buildings nobody scanned.
    """
    out = []
    for ob in osm_blds:
        pts = ob["poly"][:-1] if np.allclose(ob["poly"][0], ob["poly"][-1]) else ob["poly"]
        rect = cv2.boxPoints(cv2.minAreaRect(pts.astype(np.float32)))
        feat: dict = {
            "type": "building",
            "footprint": [[round(float(x), 3), round(float(z), 3)] for x, z in rect],
        }
        th = tag_heights(ob["tags"], level_m)
        if th is not None:
            wall, ridge = th
            feat.update(height=round(wall, 2), ridge=round(ridge, 2),
                        roof="gable" if ridge - wall >= 1.0 else "flat")
        out.append(feat)
    return out
