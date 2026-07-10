"""IFC projection of the world model (ifc-adapter v1, incubating here).

IFC is a first-class *projection*, not the backbone (brief §4): the world
model keeps its own vocabulary, and buildings leave it twice — as styled
game geometry via stage 6, and as standalone georeferenced .ifc files here
(one per building, the diagram's `ifcart`). The reverse direction reads an
.ifc back into a world-model observation batch for the fusion engine
(source "bim", high priority: BIM models are authored, not detected).

**The IFC-complete tier decision** (deferred by the 2026-07-08 session,
decided here): the mandatory world-model attributes per LOD tier are

- LOD0 (footprint):    `footprint` (>= 3 ordered corners)
- LOD1 (prism):        + `height` (wall height above ground, m)
- LOD2 (roof-shaped):  + `ridge`, `roof` ("flat" | "gable")
- LOD3+ (openings, interiors): out of scope for v1 — arrives with real
  interior sources (plans/text), not before.

to_ifc emits the deepest tier the record supports and never invents
attributes: a footprint-only building exports as LOD0, not as a guessed
prism. Colors/styling stay in the game projection — IFC gets geometry,
identity and provenance (an Automap_Provenance pset carries the fusion
engine's per-attribute sources, so a BIM consumer can see *why* each number
is what it is).

Georeferencing: IfcMapConversion against the scene raster's CRS (UTM by
construction — automap.geodata reprojects, ODM emits UTM), anchored at the
raster center, i.e. the origin of the centered metric scene frame. IFC axes
are X=east Y=north Z=up; the scene frame is x=east z=south, so y_ifc = -z.

This module deliberately depends only on world-model dicts + numpy +
ifcopenshell, so extracting it into the constellation's `ifc-adapter` repo
is repo-splitting, not rewriting (end-state E rule).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

try:
    import ifcopenshell
    import ifcopenshell.api as _api
    import ifcopenshell.util.element as _element
except ImportError:  # auto-detect / no-op, like laspy in stage 5
    ifcopenshell = None

PSET_NAME = "Automap_Provenance"
SOURCE_BIM = "bim"


def available() -> bool:
    return ifcopenshell is not None


def _require():
    if ifcopenshell is None:
        raise RuntimeError("ifcopenshell is not installed (pip install -e '.[ifc]')")


def scene_anchor(raster_path: str | Path) -> dict:
    """Georeference anchor of a scene: its raster's center + CRS.

    The centered metric frame's origin is the raster center by construction
    (automap.terrain / features), so MapConversion Eastings/Northings are
    exactly that point.
    """
    import rasterio
    with rasterio.open(raster_path) as ds:
        if ds.crs is None:
            raise ValueError(f"{raster_path} has no CRS; cannot georeference IFC")
        T = ds.transform
        return {
            "crs": str(ds.crs),
            "eastings": T.c + T.a * (ds.width - 1) / 2.0,
            "northings": T.f + T.e * (ds.height - 1) / 2.0,
        }


def building_lod(feature: dict) -> int:
    """Deepest exportable tier per the mandatory-attribute decision above."""
    if "footprint" not in feature or len(feature["footprint"]) < 3:
        raise ValueError(f"{feature.get('id', '?')}: no footprint, not IFC-exportable")
    if "height" not in feature:
        return 0
    if feature.get("roof") in ("flat", "gable") and "ridge" in feature:
        return 2
    return 1


def _gable_solids(f, body, footprint: np.ndarray, height: float, ridge: float):
    """Wall prism to `height` + triangular roof prism to `ridge`.

    The footprint is a (rotated) rectangle from detection/OSM rectification;
    the ridge runs along its long axis. Roof profile is drawn in the wall's
    cross-section plane and extruded along the long edge.
    """
    e0 = footprint[1] - footprint[0]
    e1 = footprint[2] - footprint[1]
    long_i = 0 if np.linalg.norm(e0) >= np.linalg.norm(e1) else 1
    origin = footprint[0]
    u = (e0 if long_i == 0 else e1).astype(float)          # ridge direction
    v = (e1 if long_i == 0 else -e0).astype(float)          # across the roof
    lu, lv = np.linalg.norm(u), np.linalg.norm(v)
    u /= lu
    v /= lv
    if long_i == 1:
        origin = footprint[1]

    # roof profile in the (v, z) plane: eaves at both ends, apex mid-span
    profile_pts = [(0.0, height), (lv, height), (lv / 2.0, ridge)]
    poly = f.createIfcPolyline(
        [f.createIfcCartesianPoint((float(a), float(b))) for a, b in profile_pts]
        + [f.createIfcCartesianPoint((0.0, float(height)))])
    profile = f.createIfcArbitraryClosedProfileDef("AREA", None, poly)
    # position the profile plane: origin at the eave corner, extrude along u
    placement = f.createIfcAxis2Placement3D(
        f.createIfcCartesianPoint((float(origin[0]), float(origin[1]), 0.0)),
        f.createIfcDirection((float(u[0]), float(u[1]), 0.0)),      # profile normal
        f.createIfcDirection((float(v[0]), float(v[1]), 0.0)))      # profile x-axis
    roof = f.createIfcExtrudedAreaSolid(
        profile, placement, f.createIfcDirection((0.0, 0.0, 1.0)), float(lu))
    return roof


def to_ifc(feature: dict, *, scene: str = "scene", anchor: dict | None = None):
    """One world-model building -> a self-contained ifcopenshell file.

    Emits the deepest LOD the record's attributes support (never invents),
    IfcMapConversion georeferencing when an anchor is given, and the
    provenance pset. Returns (file, lod).
    """
    _require()
    lod = building_lod(feature)
    fp = np.asarray([(float(x), -float(z)) for x, z in feature["footprint"]])

    f = ifcopenshell.file(schema="IFC4")
    _api.run("root.create_entity", f, ifc_class="IfcProject", name=scene)
    _api.run("unit.assign_unit", f)
    model3d = _api.run("context.add_context", f, context_type="Model")
    body = _api.run("context.add_context", f, context_type="Model",
                    context_identifier="Body", target_view="MODEL_VIEW", parent=model3d)
    if anchor is not None:
        _api.run("georeference.add_georeferencing", f)
        _api.run("georeference.edit_georeferencing", f,
                 coordinate_operation={"Eastings": float(anchor["eastings"]),
                                       "Northings": float(anchor["northings"]),
                                       "OrthogonalHeight": 0.0},
                 projected_crs={"Name": anchor["crs"]})

    site = _api.run("root.create_entity", f, ifc_class="IfcSite", name=scene)
    bld = _api.run("root.create_entity", f, ifc_class="IfcBuilding",
                   name=feature.get("id", "building"))
    project = f.by_type("IfcProject")[0]
    _api.run("aggregate.assign_object", f, products=[site], relating_object=project)
    _api.run("aggregate.assign_object", f, products=[bld], relating_object=site)

    ring = [f.createIfcCartesianPoint((float(x), float(y))) for x, y in fp]
    closed = f.createIfcPolyline(ring + [ring[0]])
    items, rep_type = [], "SweptSolid"
    if lod == 0:
        items = [closed]
        rep_type = "Curve2D"
    else:
        gable = lod == 2 and feature["roof"] == "gable"
        # flat LOD2 walls rise to the ridge; gable walls stop at eave height
        wall_top = float(feature["height"] if gable
                         else feature.get("ridge", feature["height"]))
        profile = f.createIfcArbitraryClosedProfileDef("AREA", None, closed)
        identity = f.createIfcAxis2Placement3D(
            f.createIfcCartesianPoint((0.0, 0.0, 0.0)), None, None)
        items = [f.createIfcExtrudedAreaSolid(
            profile, identity, f.createIfcDirection((0.0, 0.0, 1.0)), wall_top)]
        if gable:
            items.append(_gable_solids(f, body, fp, float(feature["height"]),
                                       float(feature["ridge"])))
    shape = f.createIfcShapeRepresentation(
        body, "Body" if lod else "FootPrint", rep_type, items)
    _api.run("geometry.assign_representation", f, product=bld, representation=shape)

    props = {"lod": lod, "source": feature.get("source", "")}
    for attr, src in (feature.get("provenance") or {}).items():
        props[f"src_{attr}"] = src
    _api.run("pset.edit_pset", f,
             pset=_api.run("pset.add_pset", f, product=bld, name=PSET_NAME),
             properties=props)
    return f, lod


def export_scene(doc: dict, out_dir: str | Path, *, scene: str = "scene",
                 anchor: dict | None = None, on_log=lambda _m: None) -> list[Path]:
    """The dual emission: every exportable building -> out_dir/<id>.ifc."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for feat in doc.get("features", []):
        if feat.get("type") != "building":
            continue
        try:
            f, lod = to_ifc(feat, scene=scene, anchor=anchor)
        except ValueError as err:
            on_log(f"skip {feat.get('id', '?')}: {err}")
            continue
        p = out_dir / f"{feat['id']}.ifc"
        f.write(str(p))
        written.append(p)
        on_log(f"wrote {p.name} (LOD{lod})")
    return written


_PHYSICAL = ("IfcWall", "IfcWallStandardCase", "IfcSlab", "IfcColumn", "IfcRoof",
             "IfcCurtainWall", "IfcPlate")


def _reduce_detailed(g, feat: dict) -> dict | None:
    """Coarsen a detailed plan→IFC model (walls/storeys/openings) to a
    world-model building feature: footprint = min-area rectangle of all
    physical elements' world-space geometry, height = their z-extent.

    This is the CEC-SHA seam: a plan→IFC module emits a full building; the
    world model wants a footprint + height, so we reduce. Returns None if
    the geometry kernel can't mesh anything (caller falls back).
    """
    import cv2
    import ifcopenshell.geom as geom

    settings = geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    xy, zs = [], []
    for el in g:
        if not el.is_a() in _PHYSICAL:
            continue
        try:
            shape = geom.create_shape(settings, el)
        except (RuntimeError, Exception):  # noqa: BLE001 - unmeshableelement, skip
            continue
        v = np.asarray(shape.geometry.verts, float).reshape(-1, 3)
        xy.append(v[:, :2])
        zs.append(v[:, 2])
    if not xy:
        return None
    pts = np.vstack(xy).astype(np.float32)
    z = np.concatenate(zs)
    (cx, cy), (w, h), ang = cv2.minAreaRect(pts)
    corners = cv2.boxPoints(((cx, cy), (w, h), ang))
    # IFC XY (x=east, y=north) -> scene frame (x=east, z=south = -y)
    feat["footprint"] = [[round(float(x), 3), round(float(-y), 3)] for x, y in corners]
    feat["height"] = round(float(z.max() - z.min()), 3)
    feat["ridge"] = feat["height"]
    feat["roof"] = "flat"           # detailed models rarely expose a clean ridge
    storeys = [s.Name for s in g.by_type("IfcBuildingStorey")]
    if storeys:
        feat["storeys"] = storeys   # interior evidence (LOD3+); metadata for now
    return feat


def from_ifc(path: str | Path) -> dict:
    """Read one building .ifc back into a world-model observation dict.

    Two shapes are handled: our own export (a single envelope extrusion over
    the footprint profile, exact round-trip) and a detailed plan→IFC model
    (walls/storeys/openings — CEC-SHA), reduced to footprint + height by
    _reduce_detailed. Feed the result to worldmodel.fuse(..., source="bim").
    """
    _require()
    g = ifcopenshell.open(str(path))
    bld = g.by_type("IfcBuilding")[0]
    feat: dict = {"type": "building"}
    if bld.Name:
        feat["id"] = bld.Name

    # our export gives the IfcBuilding its own body representation; a detailed
    # model puts geometry on walls/slabs and leaves the building abstract
    building_has_body = bool(bld.Representation)
    if not building_has_body:
        reduced = _reduce_detailed(g, feat)
        if reduced is not None:
            return reduced

    def ring_pts(poly):
        pts = np.array([p.Coordinates for p in poly.Points], float)
        return pts[:-1] if np.allclose(pts[0], pts[-1]) else pts

    # a solid extruded in a rotated frame (Axis != world Z) is the gable
    # roof; the vertical extrusion over the footprint profile is the walls
    wall = roof = None
    for s in g.by_type("IfcExtrudedAreaSolid"):
        axis = (tuple(s.Position.Axis.DirectionRatios)
                if s.Position is not None and s.Position.Axis is not None
                else (0.0, 0.0, 1.0))
        if axis == (0.0, 0.0, 1.0):
            wall = s
        else:
            roof = s

    if wall is not None:
        ring = ring_pts(wall.SweptArea.OuterCurve)
        feat["height"] = round(float(wall.Depth), 3)
        if roof is not None:
            apex = max(p.Coordinates[1] for p in roof.SweptArea.OuterCurve.Points)
            feat["ridge"] = round(float(apex), 3)
            feat["roof"] = "gable"
        else:
            feat["ridge"] = feat["height"]
            feat["roof"] = "flat"
    else:  # LOD0: footprint-only curve representation
        ring = ring_pts(g.by_type("IfcPolyline")[0])
    feat["footprint"] = [[round(float(x), 3), round(float(-y), 3)] for x, y in ring]
    return feat


def ifc_to_glb(path: str | Path, out_glb: str | Path, *, placement=None) -> dict:
    """Tessellate a building .ifc into a scene-frame .glb (base at y=0).

    Meshes every physical element with the geometry kernel (world coords),
    remaps IFC axes (x=east, y=north, z=up) to the scene frame (x=east,
    y=up, z=south), applies the horizontal `placement` (a placement.Placement
    yaw+translation) if given, and drops the base to y=0 so the presentation
    stage seats it on the terrain. Returns {"path", "footprint_xz",
    "size": [w, h, d]} — footprint_xz is the placed footprint hull for the
    world-model record.
    """
    _require()
    import trimesh
    import ifcopenshell.geom as geom

    settings = geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    g = ifcopenshell.open(str(path))
    meshes = []
    for el in g:
        if el.is_a() not in _PHYSICAL:
            continue
        try:
            shape = geom.create_shape(settings, el)
        except (RuntimeError, Exception):  # noqa: BLE001
            continue
        v = np.asarray(shape.geometry.verts, float).reshape(-1, 3)
        faces = np.asarray(shape.geometry.faces, int).reshape(-1, 3)
        if len(v) and len(faces):
            meshes.append(trimesh.Trimesh(vertices=v, faces=faces, process=False))
    if not meshes:
        raise ValueError(f"{path}: no meshable geometry")
    mesh = trimesh.util.concatenate(meshes)

    # IFC (x=east, y=north, z=up) -> scene (x=east, y=up, z=south)
    v = mesh.vertices
    mesh.vertices = np.column_stack([v[:, 0], v[:, 2], -v[:, 1]])

    if placement is not None:
        xz = placement.apply_xz(mesh.vertices[:, [0, 2]])
        mesh.vertices = np.column_stack([xz[:, 0], mesh.vertices[:, 1], xz[:, 1]])
    mesh.vertices[:, 1] -= mesh.vertices[:, 1].min()   # base to y=0

    out_glb = Path(out_glb)
    out_glb.parent.mkdir(parents=True, exist_ok=True)
    trimesh.Scene(mesh).export(out_glb)
    lo, hi = mesh.vertices.min(axis=0), mesh.vertices.max(axis=0)
    hull_xz = mesh.vertices[:, [0, 2]]
    return {
        "path": out_glb,
        "footprint_xz": [[round(float(lo[0]), 3), round(float(lo[2]), 3)],
                         [round(float(hi[0]), 3), round(float(lo[2]), 3)],
                         [round(float(hi[0]), 3), round(float(hi[2]), 3)],
                         [round(float(lo[0]), 3), round(float(hi[2]), 3)]],
        "size": [round(float(hi[i] - lo[i]), 2) for i in range(3)],
    }


def read_anchor(path: str | Path) -> dict | None:
    """The IfcMapConversion of a file, if georeferenced."""
    _require()
    g = ifcopenshell.open(str(path))
    mcs = g.by_type("IfcMapConversion")
    if not mcs:
        return None
    crs = g.by_type("IfcProjectedCRS")
    return {"eastings": float(mcs[0].Eastings), "northings": float(mcs[0].Northings),
            "crs": crs[0].Name if crs else None}
