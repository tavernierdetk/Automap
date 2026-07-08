# Exploration — Semantic layer v2 (fix trees, add buildings)

**Status:** Slice 1 (stage-5 hardening) BUILT 2026-07-05. Slice 2 (buildings
v1) and slice 3 (OSM overlay) BUILT 2026-07-06. Slice 3b (roads + sea) BUILT
2026-07-07 — see results below. Slice 4 (ML) still exploration.

**Goal:** make feature recognition trustworthy on real footage (mountain_cross
is grass-heavy with few trees, yet stage 5 reported 2,792 of them), and add a
second feature class — **buildings** — detected and represented well.

---

## What mountain_cross actually shows (evidence)

Diagnostic overlay of `features.json` on the orthophoto (downsampled 10×,
0.5 m cells), 2026-07-05:

- **The scene is a coastal village**: ocean across the upper half, a grassy
  headland with cliffs, a shore road, and a few dozen houses along it.
- **2,792 "trees"**: heights 2 m → 137 m (!), median 4 m. Fixed radius 1.5 m.
- **~half the detections sit on terrain steeper than 25°** (median slope at
  detection: 27°). Cliff faces pass the CHM test because the interpolated DTM
  undershoots there.
- **Hundreds of detections sit on open water.** Moving water reconstructs as
  noise; the DSM there has huge phantom spikes (the CHM heatmap shows 20 m+
  "canopy" blobs over the ocean) and blue-green water passes the ExG ≥ 0.05
  test.
- Grass fields contribute scattered false positives wherever DSM−DTM noise
  exceeds 2 m — grass is *green*, and the only tree-vs-grass discriminator we
  have today is height, which is exactly what's noisy.
- The houses are plainly visible in the ortho and DSM but are either ignored
  or (when a roof reads greenish) counted as trees.

Root causes, in order of damage:

1. **No validity/water/slope masking** — the detector trusts CHM everywhere
   ODM produced pixels, including ocean and mosaic seams.
2. **CHM noise on steep ground** — DTM interpolation fails on cliffs; a slope
   gate (or a cliff-aware CHM cap) is required before believing any height.
3. **ExG alone is not "tree"** — it's "vegetation". Grass passes. Water
   sometimes passes. Tree needs height *and* greenness *and* canopy texture.
4. **Single-class taxonomy** — everything tall+green is a tree; there is no
   "building", "water", or "don't know".

---

## Framing: the contract stays, the detector grows

`features.json` is the interface between detection (stage 5) and
representation (stage 6). That design holds; v2 is about widening the
taxonomy and swapping better detectors in behind it:

```json
{"type": "tree",     "x":…, "z":…, "height":…, "radius":…}
{"type": "building", "footprint": [[x,z]…], "height":…, "roof": "flat|gable",
                     "roof_color": [r,g,b]}
```

Stage 6 already has a transformer registry (`instance_trees`); buildings add
`instance_buildings`. Detection backends are swappable per class.

---

## Options — detection

### A. Harden the classical stack (no new deps, days not weeks)
- **Masks first**: water/no-data mask (blue-dominance index + ODM's
  `odm_georeferenced_model.bounds.geojson` boundary), DTM slope gate
  (reject where slope > ~30°), CHM sanity cap (~40 m).
- **Tree vs grass**: require CHM ≥ 2 m **and** ExG **and** local CHM
  roughness (canopy is bumpy at 0.5 m scale; grass+noise is smooth or
  ridge-like). Blob shape checks (compactness) kill cliff ridges.
- **Real radii**: watershed the CHM around each accepted peak instead of the
  fixed 1.5 m — better instancing, and blob area is itself a sanity filter.
- Expected outcome on mountain_cross: 2,792 → a few dozen, mostly real.

### B. Use the point cloud we already have
`odm_georeferencing/odm_georeferenced_model.laz` (4.7 MB at pc-quality low)
already carries SMRF ground/non-ground classification (DTM generation turned
it on). Pipeline: non-ground points → height-above-ground → DBSCAN clusters →
per-cluster eigenvalue features (planarity ⇒ roof, roughness ⇒ canopy) +
color. This is the classic classical route to **buildings vs trees** and runs
in seconds locally (`laspy` is a trivial pip add). Resolution is coarse at
pc-quality low; fine for house-sized objects.

### C. ML on the orthophoto (swap-in backends)
- **DeepForest** (already anticipated in `automap/features.py` docstring):
  pretrained RGB tree-crown detector, pip install, tiles the ortho, CPU/MPS
  friendly on the M4. Best tree accuracy per unit effort.
- **Buildings**: SAM/SAM2 prompted by nDSM blobs (detection stays classical,
  ML only refines the footprint), or a segmentation model pretrained on
  aerial building datasets (INRIA / SpaceNet via torchgeo). Heavier dep
  stack; keep behind the same features.json contract.
- **Full land-cover segmentation** (grass/road/water/building/tree in one
  pass, e.g. OpenEarthMap-pretrained SegFormer): most complete, most setup;
  also the natural source for a grass/road **splatmap** later.

### D. Join external data — we are georeferenced
`geo.txt` means the scene has real WGS84 coordinates. Pull **OSM building
footprints** (+ roads, landuse, coastline) for the bbox via Overpass and
reproject into the scene frame. Where OSM coverage exists this gives exact,
labeled polygons for free; heights still come from our nDSM. Cheap to build,
great as ground truth / cross-check; weakness: coverage varies, needs
network. The coastline polygon also solves the water mask outright.

---

## Options — building representation (stage 6)

1. **Extruded footprint prism** — polygon + median nDSM height, flat/gabled
   roof heuristic from the DSM ridge; stylized materials from the visual
   identity, optionally ortho-cropped roof texture. Cheap, collision-
   friendly, matches the low-poly styled look. **Recommended v1.**
2. **Mesh carve-out** — clip the sraw photogrammetry mesh inside the
   footprint and keep it. Photoreal but walls are melted in nadir-only
   capture; heavy; noisy.
3. **Procedural kit buildings** — parametric walls/roof/window generator
   matched to footprint dims. Best game look, most work; a later identity
   upgrade that slots into the same transformer.
4. **Hybrid** (prism geometry + ortho roof + stylized walls) — likely the
   sweet spot after v1.

Grass, since footage is grass-heavy: don't instance it — detect the grass
mask (ExG high, CHM ≈ 0) and export it as a **splatmap/regions** for Godot
multimesh grass + ground material. Separate, cheap, big visual win.

---

## Capture-side note

Nadir-only passes give buildings melted walls no algorithm will fix. For
scenes where buildings matter, add a low **oblique orbit** around them (see
docs/capture-guide.md) — reconstruction quality is set at capture time. Water
in frame will always poison the DSM; mask it, don't fight it.

---

## Recommended slices (in order)

1. **Stage-5 hardening (Option A)** — masks, slope gate, CHM cap, roughness
   test, watershed radii. Synthetic-raster unit tests like the existing ones.
   Re-run on mountain_cross; expect a believable tree set.
2. **Buildings v1 (Option B + prism representation)** — nDSM blob → planarity
   test → regularized footprint rectangle → `building` features →
   `instance_buildings` prisms. All classical, all local.
3. **OSM overlay (Option D)** — optional enrichment + validation layer, and
   the free water mask.
4. **ML upgrades (Option C)** — DeepForest for trees, SAM-refined footprints
   for buildings, only where 1–3 plateau.

---

## Slice 1 results (built 2026-07-05)

mountain_cross detections: **2,792 → 97**, all on the headland shrub masses
and a village hedgerow; water/cliff/melt/building false positives gone.
Heights 2-10 m (was 2-137 m). What shipped in `automap/features.py` +
`scripts/05_detect_features.py` (knobs in `config.toml [features]`):

- green-over-blue color veto (water), slope gate (cliffs, from the DTM),
  max-height as *peak* rejection (a >40 m peak is junk — masking tall pixels
  instead leaves a ring of flank maxima, same for the edge margin below),
- edge margin: peaks within 3 m of no-data are distrusted; the ortho's alpha
  now counts as no-data (ODM interpolates the DEMs over failed areas, so only
  the ortho knows where reconstruction actually failed),
- prominence gate: peak must stand ≥2 m above the 10th-percentile CHM within
  12 m — kills broad DSM-DTM offset plateaus on grass,
- crown area from nearest-peak pixel assignment → real radii + min-area gate,
- **support gate (the decisive one)**: the georeferenced .laz is already
  ASPRS-classified by ODM's DTM step (here: 576k ground / 64k low-veg / 84k
  building). A tree needs ≥1 vegetation pt/m² under its crown, and is vetoed
  when building points outnumber vegetation there. Auto-detect / no-op like
  the SRT sidecar (needs `laspy`, now a dependency).

Empirical dead ends worth remembering:
- Per-crown ortho sharpness (variance-of-Laplacian) does NOT separate melt
  from canopy — building-melt is high-contrast, smeared grass is low, real
  shrub is in between. Don't revisit.
- Raw all-points density is too weak: structures triangulate densely, so
  building melt passes; the classification split is what works.
- ODM's classification is noisy at the margins (outlier flight-line streaks
  over water get class 6) but reliable *within the valid ortho area* — gate
  detections first, then trust classes.

Head start for slice 2 (buildings): the 84k class-6 points cluster on the
actual village houses; during tuning, an interim all-points support gate left
83 detections that were exactly "building melt" — nDSM blobs + class-6
support is clearly viable as the building detector.

---

## Slice 2 results (built 2026-07-06)

mountain_cross: **19 buildings** (17 gabled), all on real structures — the
village houses along the shore road, the white barn, farm outbuildings. Zero
on water/cliffs. Detection is **point-first** (`detect_buildings` in
`automap/features.py`), NOT the nDSM-blob plan above — measured on
mountain_cross, half the class-6 points sit at raster-CHM < 2.7 m because the
DEMs smooth small houses away, so a raster detector structurally misses them.
Instead: cluster class-6 points on a 1 m grid → per-cluster gates → footprint
= minAreaRect of the points (they sit on the actual roof, which also trims
the melt skirt). Gates, in order of what they killed:

- min points / min-max area / veg-majority veto (trees),
- shape: rect short side ≥ 2.5 m and fill ≥ 0.35 — kills misclassified
  outlier flight lines over water (thin streaks),
- height: cluster's p75 height-above-DTM ≥ 2 m using the POINTS' own z (not
  the raster CHM — that was the whole lesson), wall = p25, ridge = p95,
  gable if ridge − wall ≥ 1 m,
- slope gate (cliffs) via the DTM slope raster,
- ground-context: ≥ 20 ground-classified points within 15 m (debris over
  open sea has none) — NOTE: weaker than hoped, sea surface sometimes gets
  class-2 points too,
- **blueness veto (the decisive water kill)**: median B − R > 15 ⇒ sea.
  ODM's classifier labels the planar sea surface "building"; geometry can't
  separate it, color does. Caveat: a genuinely blue metal roof would be lost
  (knob: `bld_max_blueness`).

Representation (`instance_buildings` in `automap/presentation.py`, in the
default transformer chain): wall prism sunk 0.5 m into the slope + roof solid
(0.2 m slab, or gable prism with ridge along the long axis), walls in the
identity's `wall_color`, roof tinted with the median ortho color the detector
sampled. Both parts are closed solids (winding fixed via
`trimesh.repair.fix_normals`), seated at the LOWEST ground raycast under the
footprint corners.

Known v1 limits: recall drops at the scene edges (houses with few camera
views have thin point support); footprints are rectangles only; wall heights
floor at 2 m because eaves-height from roof-only points underestimates
low bungalows. OSM footprints (slice 3) are the natural cross-check/backfill.

---

## Slice 3 results (built 2026-07-06)

`automap/osm.py` + wiring in stage 5 (`--osm/--no-osm`, default on). The
scene bbox (DSM bounds → WGS84 via rasterio) goes to Overpass once; the
response is cached at `work/<name>/osm.json` so re-runs are offline. The
query also grabs highways / coastline / water for future slices (roads,
water mask) — only buildings are processed today. Same auto-detect / no-op
philosophy as the SRT sidecar: no network or no CRS just means no overlay.

Merge semantics (pure, tested offline in `tests/test_osm.py`):
- greedy nearest-centroid one-to-one matching within 12 m;
- matched → keep scanned heights/roof/color, adopt the surveyed OSM
  footprint (fixes melt-fat rectangles) → source `"scan+osm"`;
- OSM-only → backfill with `height`/`building:levels` tags when present,
  else config defaults (3 m wall / 5 m gable) → source `"osm"`;
- scan-only → kept (OSM coverage is incomplete: most farm outbuildings here
  are unmapped) → source `"scan"`.

mountain_cross: 83 OSM footprints in bbox → **5 matched, 78 backfilled, 14
scan-only = 97 buildings**; alignment against the ortho is clean (no offset —
DJI geo + OSM agree within a few meters). Stage 6 placed 68; the 29 OSM
footprints outside the reconstructed terrain self-pruned via the ground
raycast. The melt-obscured village center is now fully populated — the
single biggest visual/recall win of the overlay.

Note the low match rate (5/19) is genuine, not a bug: the scan detects real
unmapped structures, OSM knows houses the thin-support scan edges missed.
The two sources are complementary, which is why all three source classes
survive in features.json.

---

## Slice 3b results (roads + sea, built 2026-07-07)

The cached OSM extract now also becomes geometry. New feature types `road`
(polyline + width from OSM class/tags) and `water` (kind "sea", coastline
outline); new transformers `instance_roads` (terrain-draped ribbon, resampled
every 2 m, raycast per vertex, +0.15 lift, asphalt vs dirt color by highway
class) and `instance_water` (full-scene sea plane). mountain_cross: 69 roads
parsed → 42 draped (off-terrain ones self-prune), 1 sea plane.

**The sea needed terrain surgery, not just a plane.** Open water is
textureless, so ODM hallucinates a lumpy sea "surface" that sat 5-10 m ABOVE
the real village — no flat plane can cover that while keeping land dry. New
`terrain.flatten_sea` in stage 3b: water-like cells (blue-dominant ortho OR
point-desert-and-not-green — sun glint reconstructs gray but triangulates
nothing) connected to the raster border are the sea; they're clamped to the
sea level measured from the laz points actually on the water (median; p5 of
masked heights as offline fallback), and valid land PITS below that level
(melt artifacts — nothing real is below the sea) are raised just above it.
Result on mountain_cross: terrain relief 120 m of garbage → 53 m of plausible
coast; sea flat at y=0 is the true minimum; village sits 0.4-8.9 m above it.

`instance_water` anchors the plane to the modal co-planar vertex set the
flattening leaves behind (+0.15), falling back to p10 of coastline raycasts.
Pitfall for the record: only count face-REFERENCED vertices — build_grid_mesh
parks nodata vertices at a bogus y=0, and the first version anchored the sea
49 m underground by counting them.

---

## First real visual identity: "madelinot" (built 2026-07-07)

User picked (via prompt): Madelinot postcard direction + stylized terrain
zones + richer prop kit. Identities remain data (`IDENTITIES` in
`06_style_scene.py`); run stage 6 with `--identity madelinot`.

- **style_terrain** (new transformer, first in the chain): drops the ortho
  texture, colors terrain vertices by zone — seafloor below the sea flat,
  sand strip = low AND within 15 m of actual sea cells (low-lying inland
  melt must stay grass), cliff where a *height-smoothed* copy of the mesh is
  steeper than 38°, grass elsewhere, plus deterministic brightness grain.
  Two hard-won details: slope must be measured on smoothed geometry or the
  entire melt zone reads as cliff (real cliffs are large-amplitude and
  survive smoothing; ±2 m melt bumps don't), and the smoothing is hand-rolled
  height-only averaging because trimesh's `filter_laplacian` rejects meshes
  with unreferenced (nodata) vertices.
- **Varied tree kit**: conifers (h ≥ 3r) = 2-3 stacked cones, deciduous =
  stacked icosphere blobs; per-instance deterministic jitter (size ±15 %,
  hue, yaw) seeded from the feature position so re-styles are identical.
- **Building details**: chimney + door/window trim quads on the long wall;
  detected roof colors get a 1.6× saturation postcard-boost; near-gray roofs
  (incl. all OSM backfills) get painted from a red/green/yellow/blue palette
  — 63 of 68 mountain_cross buildings ended up painted.
- Styled glb shrank 6.0 → 2.5 MB (no ortho texture; vertex colors instead).
- Verified with a homemade painter's-algorithm renderer (cv2 fillPoly,
  no GL) — its one artifact: the single-quad water plane sorts wrong against
  terrain in the preview; Godot's z-buffer is unaffected.
