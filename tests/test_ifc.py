"""IFC adapter tests (automap.ifc). Skip cleanly when ifcopenshell is absent.

Everything is self-generated: the detailed-model test builds a small
multi-wall IFC with ifcopenshell itself, so the geometry-reduction seam is
exercised without depending on any external (proprietary) .ifc file.
"""
import numpy as np
import pytest

ifc = pytest.importorskip("automap.ifc", reason="needs ifcopenshell")
if not ifc.available():
    pytest.skip("ifcopenshell not installed", allow_module_level=True)

from automap import worldmodel  # noqa: E402


def _bld(cx, cz, w=10.0, d=6.0, **kw):
    corners = [[cx - w / 2, cz - d / 2], [cx + w / 2, cz - d / 2],
               [cx + w / 2, cz + d / 2], [cx - w / 2, cz + d / 2]]
    f = {"type": "building", "id": "building-0000", "footprint": corners,
         "height": 3.0, "ridge": 5.0, "roof": "gable", "roof_color": [120, 90, 70],
         "source": "osm+scan",
         "provenance": {"footprint": "osm", "height": "scan", "ridge": "scan",
                        "roof": "scan", "roof_color": "scan"}}
    f.update(kw)
    return f


def test_building_lod_tiers():
    assert ifc.building_lod(_bld(0, 0)) == 2                       # footprint+height+roof+ridge
    assert ifc.building_lod(_bld(0, 0, roof="flat")) == 2
    f = _bld(0, 0)
    del f["ridge"]; del f["roof"]
    assert ifc.building_lod(f) == 1                               # footprint+height only
    del f["height"]
    assert ifc.building_lod(f) == 0                               # footprint only
    with pytest.raises(ValueError):
        ifc.building_lod({"type": "building", "footprint": [[0, 0]]})


@pytest.mark.parametrize("roof,ridge", [("gable", 5.0), ("flat", 3.0)])
def test_roundtrip_preserves_geometry(tmp_path, roof, ridge):
    b = _bld(2.0, -3.0, roof=roof, ridge=ridge)
    f, lod = ifc.to_ifc(b, scene="t")
    assert lod == 2
    p = tmp_path / "b.ifc"
    f.write(str(p))
    back = ifc.from_ifc(p)
    assert back["id"] == "building-0000"
    assert back["height"] == 3.0 and back["ridge"] == ridge and back["roof"] == roof
    drift = np.abs(np.sort(np.array(b["footprint"]), 0)
                   - np.sort(np.array(back["footprint"]), 0)).max()
    assert drift < 1e-6


def test_georeference_round_trips(tmp_path):
    anchor = {"crs": "EPSG:32620", "eastings": 588153.2, "northings": 5232215.5}
    f, _ = ifc.to_ifc(_bld(0, 0), scene="t", anchor=anchor)
    p = tmp_path / "b.ifc"
    f.write(str(p))
    got = ifc.read_anchor(p)
    assert got["crs"] == "EPSG:32620"
    assert abs(got["eastings"] - 588153.2) < 1e-3
    assert abs(got["northings"] - 5232215.5) < 1e-3


def test_provenance_pset_carries_sources(tmp_path):
    import ifcopenshell
    import ifcopenshell.util.element as ue
    f, _ = ifc.to_ifc(_bld(0, 0), scene="t")
    p = tmp_path / "b.ifc"
    f.write(str(p))
    g = ifcopenshell.open(str(p))
    ps = ue.get_psets(g.by_type("IfcBuilding")[0])[ifc.PSET_NAME]
    assert ps["src_footprint"] == "osm" and ps["src_height"] == "scan"
    assert ps["lod"] == 2


def test_lod0_footprint_only(tmp_path):
    f = _bld(0, 0)
    del f["height"]; del f["ridge"]; del f["roof"]
    file, lod = ifc.to_ifc(f, scene="t")
    assert lod == 0
    p = tmp_path / "b.ifc"
    file.write(str(p))
    back = ifc.from_ifc(p)
    assert "height" not in back and len(back["footprint"]) == 4


def test_export_scene_skips_unexportable(tmp_path):
    doc = {"features": [_bld(0, 0), {"type": "building", "id": "bad", "footprint": [[0, 0]]},
                        {"type": "tree", "id": "tree-0", "x": 0, "z": 0}]}
    logs = []
    written = ifc.export_scene(doc, tmp_path, scene="t", on_log=logs.append)
    assert len(written) == 1 and written[0].name == "building-0000.ifc"
    assert any("skip bad" in m for m in logs)


def _detailed_model(tmp_path):
    """A minimal walls+storeys building (no single envelope) — stands in for
    an external plan→IFC model to exercise the geometry-reduction seam."""
    import ifcopenshell
    import ifcopenshell.api as api
    f = ifcopenshell.file(schema="IFC4")
    api.run("root.create_entity", f, ifc_class="IfcProject", name="p")
    api.run("unit.assign_unit", f, length={"is_metric": True, "raw": "METERS"})
    ctx = api.run("context.add_context", f, context_type="Model")
    body = api.run("context.add_context", f, context_type="Model",
                   context_identifier="Body", target_view="MODEL_VIEW", parent=ctx)
    site = api.run("root.create_entity", f, ifc_class="IfcSite", name="s")
    bld = api.run("root.create_entity", f, ifc_class="IfcBuilding", name="Detailed")
    api.run("aggregate.assign_object", f, products=[site],
            relating_object=f.by_type("IfcProject")[0])
    api.run("aggregate.assign_object", f, products=[bld], relating_object=site)
    storey = api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="RDC")
    api.run("aggregate.assign_object", f, products=[storey], relating_object=bld)

    # four walls around a 12 x 8 rectangle, each a thin extruded box to 3 m
    def wall(x0, y0, x1, y1):
        w = api.run("root.create_entity", f, ifc_class="IfcWall")
        dx, dy = x1 - x0, y1 - y0
        length = (dx * dx + dy * dy) ** 0.5
        pts = [(0.0, 0.0), (float(length), 0.0), (float(length), 0.2), (0.0, 0.2)]
        poly = f.createIfcPolyline([f.createIfcCartesianPoint(p) for p in pts]
                                   + [f.createIfcCartesianPoint(pts[0])])
        prof = f.createIfcArbitraryClosedProfileDef("AREA", None, poly)
        placement = f.createIfcAxis2Placement3D(
            f.createIfcCartesianPoint((float(x0), float(y0), 0.0)),
            f.createIfcDirection((0.0, 0.0, 1.0)),
            f.createIfcDirection((float(dx / length), float(dy / length), 0.0)))
        solid = f.createIfcExtrudedAreaSolid(
            prof, placement, f.createIfcDirection((0.0, 0.0, 1.0)), 3.0)
        rep = f.createIfcShapeRepresentation(body, "Body", "SweptSolid", [solid])
        api.run("geometry.assign_representation", f, product=w, representation=rep)
        api.run("spatial.assign_container", f, products=[w], relating_structure=storey)

    wall(0, 0, 12, 0); wall(12, 0, 12, 8); wall(12, 8, 0, 8); wall(0, 8, 0, 0)
    p = tmp_path / "detailed.ifc"
    f.write(str(p))
    return p


def test_reduce_detailed_model_seam(tmp_path):
    """A walls/storeys model (no building envelope) reduces to footprint +
    height, records storeys, and fuses as a 'bim' source — the CEC-SHA seam."""
    p = _detailed_model(tmp_path)
    feat = ifc.from_ifc(p)
    assert feat["id"] == "Detailed"
    fp = np.array(feat["footprint"])
    ext_x = fp[:, 0].max() - fp[:, 0].min()
    ext_z = fp[:, 1].max() - fp[:, 1].min()
    assert {round(ext_x), round(ext_z)} == {12, 8}       # rectangle recovered
    assert abs(feat["height"] - 3.0) < 0.1
    assert feat["storeys"] == ["RDC"]

    d = worldmodel.finalize(worldmodel.fuse(worldmodel.new_document("d"), [feat], "bim"))
    b = d["features"][0]
    assert "bim" in b["source"] and b["provenance"]["footprint"] == "bim"
    assert b["provenance"]["roof_color"] == "default"    # IFC carries no game color
    assert worldmodel.validate(d)
