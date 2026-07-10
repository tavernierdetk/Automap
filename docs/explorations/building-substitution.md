# Exploration — Building substitution (drop an IFC plan onto a building)

**Status: BUILT (2026-07-10).** Any scene (drone or geodata) can have a
generated proxy building replaced by an authored IFC model, in place,
surviving every future re-run. This is the `feature-substitution` pattern
(trees → assets) applied to buildings with an *authored* asset, and the
end-state-C/E payoff of the IFC adapter.

Proven on `lagrave`: a self-authored 2-storey L-shaped house
(`manoir.ifc`, local coords) dropped onto `building-0072` via footprint-fit —
placed at the target centroid, rotated −37° to match the detected footprint,
draped onto the terrain (base at the 2.5 m ground height), rendered as the
detailed mesh instead of a box. A subsequent stage-5 detection re-run left it
untouched (footprint provenance stayed `bim`).

## The command

    python scripts/09_replace_building.py --scene <name> --ifc <plan.ifc> --id building-0007
        [--footprint-fit] [--rotate <deg>]

Targeting is **explicit by id** (deterministic; the ids are in
features.json). Then stage 6 renders it; `--restyle` at stage 6 repaints the
plan in the scene identity, otherwise its authored materials are kept.

## How it works (pieces, all reused downstream)

1. **`ifc.from_ifc`** reads the plan and reduces it to a footprint (used to
   fit) — the same reader built for the CEC-SHA seam.
2. **`placement.py`** solves a rigid transform onto the target:
   *georeference* (the plan's `IfcMapConversion` vs the scene's UTM anchor)
   when present, else *footprint-fit* (align the plan's footprint centroid +
   long axis to the target's). Vertical seating is deferred to a terrain
   drape at render time (keyed by `ground_xz`).
3. **`ifc.ifc_to_glb`** tessellates the plan (geometry kernel), remaps IFC
   axes (z-up → scene y-up), bakes the horizontal placement, and seats the
   base at y=0 → `work/<scene>/assets/<id>.glb`.
4. **The world model** records a `representation` override on the building
   (`scene-features@2.1.0`, additive) with provenance `bim`.
5. **The fusion engine** ranks `bim` just under `manual`, so the override
   **outranks every detector and survives regeneration** — the whole reason
   worldmodel v1 was built first.
6. **Stage 6** (`instance_buildings`) instances the placed glb, draped onto
   the terrain, instead of a proxy box.

## Why this closes the loop

The plan can come from anywhere that speaks IFC — including the external
(proprietary) CEC-SHA plan→IFC pipeline — because only `.ifc` files cross
the boundary (see [ifc-adapter.md](ifc-adapter.md)). Detect a building from a
drone scan or public LiDAR+OSM, then drop the real surveyed/authored model in
its place, and it holds through every regeneration. That is the
"multi-source world that survives hand-authoring" claim, demonstrated.

## Follow-ups

- **True-north rotation** in the georeference path (assumed ~0 today).
- **Auto-match** targeting for georeferenced plans (match by footprint
  proximity, reusing the fusion matcher) — deferred; explicit id is the v1.
- **Interiors**: the plan's `IfcSpace`/storeys are recorded as evidence but
  not yet turned into walkable interior geometry (LOD3/4).
- **Scale sanity check**: warn when a footprint-fit plan's size diverges
  wildly from the target footprint (likely a units or wrong-target error).
