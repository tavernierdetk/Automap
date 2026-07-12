# MTL acceptance run — geoJSON → Plateau-Mont-Royal, capability evaluation

**Status: run complete, 2026-07-12.** The brief §1b acceptance scenario
pointed at its actual target city for the first time: a user-provided
**GeoJSON polygon** (Square Saint-Louis / Saint-Denis block of the Plateau,
~870×780 m) through the whole B-funnel to a walkable, styled, published
Godot scene. Every stage ran; the output is recognizably that neighbourhood
(Square Saint-Louis's diagonal paths read from the air). Scene: `plateau`.

## What ran, stage by stage

| Stage | Result | Verdict |
|---|---|---|
| **GeoJSON intake** (new) | `--geojson input/plateau.geojson` → bbox; `geodata.geojson_bounds` walks any GeoJSON nesting | ✅ built this run — **bounds only; polygon clip is a gap** |
| **2b LiDAR fetch** | `QC-600023_52_CMM_2023-1m` (hrdem-lidar) — dedicated 2023 CMM acquisition, 1 m, 100 % valid, DTM 22–47 m / DSM to 131.7 m | ✅ Montréal coverage is excellent |
| **3b terrain** | 256×233 grid, 3.4 m cells, 59 k verts | ✅ unchanged from lagrave |
| **5 features** | no ortho → OSM-only through fusion: **1,533 buildings, 1,040 roads**, 0 water; validates scene-features@2.1.0 | ✅ 12× lagrave's density, no strain |
| **6 identity** | new `plateau` identity (data-only entry): brick walls, tin/membrane/copper roof palette, asphalt, park green. 1,468 buildings + 999 roads placed in **7 s** | ✅ identity-as-data proven on new fabric |
| **7 publish + run** | `sf_plateau.tscn`, 8,340 colliders, player spawns on-surface, procedural quest works headless | ✅ playable |

## What the renders show (aerial + street captures)

The identity *applies* — palette variation across roofs, brick walls, road
network legible, the square recognizable. But four things dominate the gap
between "walkable map" and "feels like the Plateau":

1. **Flat city (the #1 fix).** 1,492 of 1,533 buildings wear the 3 m
   default height — OSM height/levels tags are rare here, and we never read
   the DSM we already fetched (mean fabric 8.7 m, p95 22.8 m, max 90 m).
   **Per-footprint DSM−DTM height extraction** (a percentile inside each
   footprint, as a `lidar` fusion source) would fix the whole skyline in one
   provider. Triplexes should be ~10–12 m, not bungalow-high.
2. **No trees at all.** OSM has no tree points here; scan detection is off
   (no ortho). Square Saint-Louis without its canopy is naked. The logged
   **LiDAR-CHM tree detection** (DSM−DTM, no-RGB gates) is no longer a
   nice-to-have — on urban scenes it is the difference-maker.
3. **Everything unbuilt is grass.** No landcover source: sidewalks, parking,
   schoolyards all render park-green. OSM landuse/surface polygons (or
   Overture land) as a `style_terrain` zone input is the missing layer.
4. **Washed-out palette.** Sky-ambient + filmic tonemap desaturate the
   authored colors; the brick reads salmon. Identity *values* are right;
   the render side needs a lighting/material pass (or the visual-identity
   v2 resolution/style-mask work).

Minor: the map-centre player spawn landed on a big flat roof (raycast hit a
building top — fine for a viewer, wrong for gameplay); large institutional
footprints (UQAM-side blocks) dominate street views at 3 m height.

## Verdict

Same funnel, third intake (drone → coordinates → **geoJSON**), zero code
changes below the intake seam — the platform claim keeps paying. Density is
a non-issue. The remaining distance to "feels like Montréal" is **data
enrichment, not architecture**: heights from the DSM, trees from the CHM,
landcover zones, then a lighting pass. All four fit the existing provider /
transformer seams.

## Follow-up queue (ordered)

1. `lidar` height provider: per-footprint DSM−DTM percentile → building
   height/ridge as a fusion source (outranks the 3 m default, yields to
   `manual`/`bim`).
2. LiDAR-CHM tree detection with no-RGB gates (already logged at end-state B).
3. Landcover zones for `style_terrain` (OSM landuse/surface → grass vs
   paved vs plaza).
4. Lighting/tonemap pass so identity palettes survive to the pixel.
5. GeoJSON polygon **clip** (scene = the neighbourhood, not its bbox);
   spawn anchor should reject rooftops.
6. CityGML LOD2 (the diagram's red source) stays the eventual upgrade for
   real roof shapes.
