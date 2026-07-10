"""The per-scene world model + fusion engine (worldmodel v1).

features.json grown up, per the locked world-model-scope decision: the same
feature vocabulary as before (trees, buildings, roads, water in the centered
metric frame), plus the hub fields — stable per-feature ids, per-attribute
provenance, LOD tiers — so the document survives regeneration instead of being
overwritten by it. Spec: scene-features@2.0.0 in platform-specs; this module
incubates in Automap until the worldmodel earns its own repo.

Fusion semantics (architecture brief §5, generalizing the proven OSM merge):

- **stable-ID matching per feature class** — an incoming batch from one source
  is matched against the document greedily, one-to-one, nearest representative
  point first, within a per-type distance. Matched features keep their id.
- **per-attribute source priority** — each attribute of a matched feature is
  overwritten only by an equal-or-higher-priority source (same source =
  re-observation = refresh). Priorities are per attribute kind: footprints
  trust survey (OSM) over scan; heights trust scan over tags.
- **provenance per attribute** — every write records which source set the
  attribute. `manual` is the top-priority source everywhere: hand-edit a value
  in the JSON, flip its provenance entry to "manual", and no regeneration will
  touch it again. An attribute with no provenance entry is unowned (legacy
  docs): anything may write it.
- **unmatched features survive** — from both sides. The one exception: a
  re-observation retires features *wholly owned* by the observing source that
  it no longer reports (a rerun of the scan is a full statement of what the
  scan sees; stale scan-only detections would otherwise accumulate forever).
  Any feature another source (including `manual`) has touched survives.

Everything here is pure and file-format-level; detection lives in
automap.features, OSM parsing in automap.osm, and the pipeline wiring in
scripts/05_detect_features.py.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np

SPEC = ("scene-features", "2.1.0")
FRAME = "centered-metric-yup"
MANUAL = "manual"
BIM = "bim"

# Lower index = stronger claim. Unknown sources rank below every listed one.
# `bim` sits just under `manual`: an authored IFC model (a dropped-in plan)
# is truth for a building, outranking any detector — and so survives regen.
DEFAULT_PRIORITY = (MANUAL, BIM, "scan", "lidar", "osm", "overture", "generated", "default")
ATTRIBUTE_PRIORITY = {
    # brief §5: footprint: survey > scan; height: scan/LiDAR > tags; color: scan.
    # a dropped-in IFC footprint is authoritative, so bim leads here too.
    "footprint": (MANUAL, BIM, "osm", "overture", "lidar", "scan", "generated", "default"),
}

# How far apart two observations of the same feature may sit (meters).
MATCH_DIST_M = {"tree": 4.0, "building": 12.0, "road": 25.0, "water": 60.0}

# Feature keys that are bookkeeping, not observed attributes.
_META_KEYS = {"type", "id", "source", "provenance", "lod"}

BUILDING_DEFAULTS = {
    "height": 3.0, "ridge": 5.0, "roof": "gable", "roof_color": (150, 145, 140),
}


def new_document(scene: str | None = None) -> dict:
    doc = {"frame": FRAME, "counters": {}, "features": []}
    if scene:
        doc["scene"] = scene
    return doc


def load(path: str | Path) -> dict:
    """Read a features.json of either vintage; v1 docs are upgraded in memory.

    Upgrading allocates ids for id-less features and leaves their attributes
    unowned (no provenance), so the next fusion pass adopts them cleanly.
    """
    doc = json.loads(Path(path).read_text())
    doc.setdefault("frame", FRAME)
    doc.setdefault("counters", {})
    doc.setdefault("features", [])
    for f in doc["features"]:
        if "id" not in f:
            f["id"] = _new_id(doc, f["type"])
    return doc


def save(doc: dict, path: str | Path) -> None:
    Path(path).write_text(json.dumps(doc, indent=2) + "\n")


def validate(doc: dict) -> bool:
    """Validate against scene-features@2.0.0 if platform-specs is importable.

    Auto-detect / no-op like the SRT sidecar: returns False when the registry
    is not installed, raises jsonschema.ValidationError on a bad document.
    """
    try:
        import platform_specs
    except ImportError:
        return False
    platform_specs.validate(doc, *SPEC)
    return True


def _new_id(doc: dict, ftype: str) -> str:
    counters = doc.setdefault("counters", {})
    n = counters.get(ftype, 0)
    counters[ftype] = n + 1
    return f"{ftype}-{n:04d}"


def _rep_point(f: dict) -> np.ndarray:
    """One (x, z) that stands for the feature when matching observations."""
    t = f["type"]
    if t == "tree":
        return np.array([f["x"], f["z"]], float)
    key = {"building": "footprint", "road": "path", "water": "outline"}[t]
    return np.asarray(f[key], float).mean(axis=0)


def _rank(source: str, attr: str) -> int:
    order = ATTRIBUTE_PRIORITY.get(attr, DEFAULT_PRIORITY)
    try:
        return order.index(source)
    except ValueError:
        return len(order)


def _source_summary(f: dict) -> str:
    owners = sorted(set((f.get("provenance") or {}).values()))
    return "+".join(owners) if owners else f.get("source", "")


def _match(existing: list[dict], batch: list[dict], max_dist: float) -> dict[int, int]:
    """Greedy one-to-one nearest-centroid matching: batch index -> existing index."""
    if not existing or not batch:
        return {}
    e_pts = [_rep_point(f) for f in existing]
    b_pts = [_rep_point(f) for f in batch]
    pairs = sorted(
        (float(np.linalg.norm(b_pts[i] - e_pts[j])), i, j)
        for i in range(len(batch)) for j in range(len(existing)))
    out: dict[int, int] = {}
    taken: set[int] = set()
    for dist, i, j in pairs:
        if dist > max_dist:
            break
        if i in out or j in taken:
            continue
        out[i] = j
        taken.add(j)
    return out


def fuse(
    doc: dict,
    batch: list[dict],
    source: str,
    *,
    observed_types: set[str] | None = None,
    match_dist: dict[str, float] | None = None,
    retire: bool = True,
) -> dict:
    """Reconcile one source's observation batch into the document (returns a copy).

    batch features are plain dicts (automap.features .as_feature() output) —
    no ids, no provenance; only the attributes the source actually observed
    (e.g. an OSM building carries a footprint, and heights only when tagged).

    observed_types names the feature types this batch is a *complete*
    observation of, for the retirement rule; it defaults to the types present
    in the batch. Pass it explicitly when a full re-observation legitimately
    found nothing (a scan rerun with zero buildings should still retire stale
    scan-only buildings).
    """
    doc = copy.deepcopy(doc)
    feats: list[dict] = doc.setdefault("features", [])
    if observed_types is None:
        observed_types = {f["type"] for f in batch}
    dist = dict(MATCH_DIST_M, **(match_dist or {}))

    touched_ids: set[str] = set()   # matched or added by this pass: never retired
    for ftype in sorted({f["type"] for f in batch}):
        existing = [f for f in feats if f["type"] == ftype]
        incoming = [f for f in batch if f["type"] == ftype]
        matches = _match(existing, incoming, dist[ftype])

        for i, inc in enumerate(incoming):
            j = matches.get(i)
            if j is None:
                new = {k: v for k, v in inc.items() if k not in _META_KEYS}
                new = {"type": ftype, "id": _new_id(doc, ftype), **new}
                new["provenance"] = {k: source for k in new if k not in _META_KEYS}
                new["source"] = source
                feats.append(new)
                touched_ids.add(new["id"])
                continue
            cur = existing[j]
            touched_ids.add(cur["id"])
            prov = cur.setdefault("provenance", {})
            for attr, value in inc.items():
                if attr in _META_KEYS:
                    continue
                owner = prov.get(attr)
                if owner is None or owner == source or _rank(source, attr) < _rank(owner, attr):
                    cur[attr] = value
                    prov[attr] = source
            cur["source"] = _source_summary(cur)

    if retire:
        def keeps(f: dict) -> bool:
            if f["type"] not in observed_types or f["id"] in touched_ids:
                return True
            # "default" is fusion bookkeeping, not another source's claim
            owners = set((f.get("provenance") or {}).values()) - {"default"}
            return owners != {source}   # wholly-owned & unreported -> retire
        doc["features"] = [f for f in feats if keeps(f)]
    return doc


def finalize(doc: dict, *, building_defaults: dict | None = None) -> dict:
    """Make the document spec-complete (returns a copy).

    Buildings that arrived footprint-only (OSM backfill without height tags)
    get default walls/roof with provenance "default" — the weakest source, so
    any later real observation overwrites them. Building LOD tiers are derived
    (2 = roof-shaped, 1 = prism), and every feature's `source` roll-up is
    refreshed from its provenance.
    """
    doc = copy.deepcopy(doc)
    defaults = dict(BUILDING_DEFAULTS, **(building_defaults or {}))
    for f in doc.get("features", []):
        if f["type"] == "building":
            prov = f.setdefault("provenance", {})
            for attr, value in defaults.items():
                if attr not in f:
                    f[attr] = list(value) if isinstance(value, tuple) else value
                    prov[attr] = "default"
            f["ridge"] = max(f["ridge"], f["height"] + 0.1)
            f["lod"] = 2 if f.get("roof") == "gable" else 1
        summary = _source_summary(f)
        if summary:
            f["source"] = summary
    return doc
