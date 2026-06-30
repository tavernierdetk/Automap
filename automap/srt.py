"""DJI .SRT GPS sidecar parsing -> ODM geo.txt. Auto-detect / best-effort / no-op.

The DJI Mini 3 AirDrop case usually has NO sidecar, so this is never required. When
a sidecar IS present, we parse per-subtitle GPS, interpolate a position for each
kept frame's timestamp, and emit an ODM geo.txt so reconstruction is georeferenced.

Handles two DJI variants:
  * bracketed:  [latitude: 47.1] [longitude: -63.2] [rel_alt: 30 abs_alt: 50]
  * legacy:     GPS(-63.2,47.1,30)   -> (longitude, latitude, altitude)
"""
from __future__ import annotations

import re
from pathlib import Path

_TIME_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->")
_LAT_RE = re.compile(r"latitude\s*:?\s*([-\d.]+)", re.I)
_LON_RE = re.compile(r"longitude\s*:?\s*([-\d.]+)", re.I)
_ABS_RE = re.compile(r"abs_alt\s*:?\s*([-\d.]+)", re.I)
_REL_RE = re.compile(r"rel_alt\s*:?\s*([-\d.]+)", re.I)
_GPS_RE = re.compile(r"GPS\s*\(?\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)", re.I)


def parse_dji_srt(path: str | Path) -> list[dict]:
    """Return [{time, lat, lon, alt}, ...] sorted by time (s). Empty if unparseable."""
    text = Path(path).read_text(errors="ignore")
    entries: list[dict] = []
    for block in re.split(r"\n\s*\n", text):
        tm = _TIME_RE.search(block)
        if not tm:
            continue
        h, m, s, ms = map(int, tm.groups())
        t = h * 3600 + m * 60 + s + ms / 1000.0

        lat = lon = alt = None
        mlat, mlon = _LAT_RE.search(block), _LON_RE.search(block)
        if mlat and mlon:
            lat, lon = float(mlat.group(1)), float(mlon.group(1))
            malt = _ABS_RE.search(block) or _REL_RE.search(block)
            alt = float(malt.group(1)) if malt else 0.0
        else:
            mg = _GPS_RE.search(block)
            if mg:
                lon, lat, alt = float(mg.group(1)), float(mg.group(2)), float(mg.group(3))

        if lat is not None and lon is not None:
            entries.append({"time": t, "lat": lat, "lon": lon, "alt": alt or 0.0})

    entries.sort(key=lambda e: e["time"])
    return entries


def interpolate(entries: list[dict], t: float) -> dict | None:
    """Linear GPS interpolation at time t; clamps to the ends. None if no entries."""
    if not entries:
        return None
    if t <= entries[0]["time"]:
        return entries[0]
    if t >= entries[-1]["time"]:
        return entries[-1]
    for i in range(1, len(entries)):
        a, b = entries[i - 1], entries[i]
        if a["time"] <= t <= b["time"]:
            span = (b["time"] - a["time"]) or 1.0
            f = (t - a["time"]) / span
            return {
                "lat": a["lat"] + f * (b["lat"] - a["lat"]),
                "lon": a["lon"] + f * (b["lon"] - a["lon"]),
                "alt": a["alt"] + f * (b["alt"] - a["alt"]),
            }
    return entries[-1]


def write_geo_txt(frames: list[dict], entries: list[dict], out_path: str | Path) -> int:
    """Write an ODM geo.txt for the given frames. Returns # georeferenced frames.

    No file is written (returns 0) when there are no SRT entries, so callers can
    treat georeferencing as a pure no-op when the sidecar is absent/empty.
    """
    if not entries:
        return 0
    # ODM geo.txt: first line is the CRS, then "image_name geo_x geo_y geo_z".
    # For EPSG:4326, geo_x = longitude, geo_y = latitude.
    lines = ["EPSG:4326"]
    n = 0
    for fr in frames:
        g = interpolate(entries, fr["time"])
        if g is None:
            continue
        lines.append(f"{fr['name']} {g['lon']:.8f} {g['lat']:.8f} {g['alt']:.3f}")
        n += 1
    Path(out_path).write_text("\n".join(lines) + "\n")
    return n
