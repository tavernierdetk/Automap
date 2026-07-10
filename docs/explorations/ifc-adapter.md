# Exploration — IFC adapter (to_ifc / from_ifc)

**Status: v1 BUILT (2026-07-10).** `automap/ifc.py` projects world-model
buildings to georeferenced IFC4 and reads plan→IFC models back in. Proven:
all 126 lagrave buildings → georeferenced `.ifc` (LOD2), and a real detailed
walls/storeys model reduces to a footprint+height building and fuses as a
`bim` source. IfcOpenShell 0.8.5 runs natively on the M4 (arm64, py3.13) —
the dependency risk that gated this is retired.

## The decisions this work was told to make

**IFC is a projection, not the backbone** (brief §4) — confirmed in code:
the world model keeps its own vocabulary; `ifc.py` depends only on
world-model dicts + numpy + ifcopenshell, so extraction into the
constellation's `ifc-adapter` repo is repo-splitting, not rewriting.

**The IFC-complete building schema — mandatory attributes per LOD tier**
(deferred by the 2026-07-08 session, decided here):

| LOD | Meaning | Mandatory world-model attributes |
|----|---------|----------------------------------|
| 0 | footprint | `footprint` (≥3 ordered corners) |
| 1 | prism | + `height` |
| 2 | roof-shaped | + `ridge`, `roof` (`flat`\|`gable`) |
| 3+ | openings, interiors | out of v1 — arrives with real interior sources |

`to_ifc` emits the deepest tier the record supports and **never invents**
attributes (a footprint-only building exports as LOD0, not a guessed prism).
Colors/styling stay in the game projection; IFC gets geometry, georeference,
and an `Automap_Provenance` pset carrying the fusion engine's per-attribute
sources.

Georeference: `IfcMapConversion` against the scene raster's CRS (UTM by
construction), anchored at the raster center = the centered metric frame's
origin. Axis map: IFC (x=east, y=north, z=up) ← scene (x=east, z=south),
so y_ifc = −z.

## The CEC-SHA seam (why no code was reused)

`~/Claude/CEC-SHA` is a mature plan→IFC ingestion pipeline (CubiCasa
floor-plan → domain snapshot → IFC read/write adapters) — exactly the
`ingest-plan` module the platform wants. **But it is proprietary Baseline
code** (`license = Proprietary`, remote `github.com/Baseline-quebec/…`), and
Automap's first rule is "no Baseline anything." So nothing was copied.

Instead we use the boundary the architecture already prescribes (end-state
E): a plan→IFC module is a **standalone BIM component that speaks IFC at its
edge**, so it interoperates through `.ifc` files, not shared code.
`from_ifc` is that inbound seam — it reads a detailed walls/storeys/openings
model (verified against a real CEC-SHA `model.ifc`: IFC4X3, 1 building, 3
storeys, 101 walls) and **reduces** it to a world-model building:

- footprint = min-area rectangle of all physical elements' world-space
  geometry (via the IfcOpenShell geometry kernel), reprojected to the scene
  frame;
- height = geometry z-extent;
- storey names recorded as interior evidence (LOD3+ metadata; not yet
  geometry);
- fused with source `bim` (authored, so high priority); `roof_color` falls
  to `default` because IFC carries no game color — correct provenance.

Nothing from CEC-SHA enters the repo: no code, no `.ifc` fixtures. The
detailed-model test self-generates a walls+storeys IFC with ifcopenshell.

## Follow-ups

- **Inbound georeference**: place a `from_ifc` building into the right scene
  frame using the source's `IfcMapConversion` (read_anchor exists; wiring an
  importer script waits for a real inbound need).
- **LOD3/4**: `IfcSpace` interiors → per-room world-model features, when an
  interior source (plans/text) is actually wired.
- **Roads/site**: IFC4x3 built-infrastructure classes for the road network
  and `IfcSite` terrain, if the BIM consumers want more than buildings.
