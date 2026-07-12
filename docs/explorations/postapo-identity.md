# Post-apocalyptic identity — styling capabilities, slice 1 (plateau D)

**Status: built, 2026-07-12.** The first game-driven visual identity: the
intake pipeline untouched (same LiDAR, same OSM, same fusion), and the
rendering of the Montréal scene now clearly begins to read as its
post-apocalyptic self — bleached brick under amber dust haze, broken
rooflines, rubble lots, weeds reclaiming the streets. Scene: `plateau`,
identity: `identities/postapo.json`.

## What the identity system had to grow

Flat palette swaps can't say "abandoned". Three new capability axes, all
defaulting to off (v1 identities re-render byte-identically — regression-tested):

1. **Decay** (`instance_buildings`): a per-building deterministic roll
   (separate RNG stream from the roof-palette draw, so existing scenes keep
   their colors) sorts buildings into weathered (grime-jittered walls, sooted
   trim) / damaged (`top_offsets` jagged parapets, `skip_roof` open shells) /
   collapsed (`rubble_parts`: debris mound + charred remnant wall stubs,
   scaled to what stood there).
2. **Overgrowth** (`scatter_overgrowth` transformer + `road_wear`): weed
   clumps stationed along roads (density per 100 m, patchy by design,
   3,000-clump cap), roads bleaching toward grey per-road.
3. **Atmosphere** (`identity.environment` → **env.json**): stage 6 emits the
   block beside the styled glb, stage 7 publishes it as
   `godot/scenes/<name>/env.json`, and `map_loader` applies sky, low amber
   sun, dust fog, ambient and a post-tonemap saturation trim at load. This
   also closes the MTL eval's gap #4 (palettes washing out) for every
   identity — the look of a place now ships as data with the scene.

**Identities graduated to files**: `--identity <path>.json`, validated
against `visual-identity@2.0.0` (platform-specs), loaded by
`identity_from_dict` (unknown keys ignored — schemas may run ahead).
`identities/postapo.json` is the first file identity; a game repo can now own
its look without touching pipeline code.

## The height fix that styling forced

The first renders exposed that the MTL eval's #1 gap blocks this slice: at
the 3 m OSM default, decay is illegible — everything reads as sheds in a
dust storm. So the `lidar` height provider landed here:
`geodata.building_heights_from_dems` rasterizes every OSM footprint onto the
DSM−DTM grid in one pass and takes per-footprint percentiles (p50 wall, p90
ridge → gable detection for free). Stage 5 fuses it as source `"lidar"` —
already ranked above `osm` for height, below `scan`/`bim`/`manual`, so the
priority table needed zero changes. Plateau: **1,451/1,533 buildings now
measured** (mean 10.5 m, the 72 m tower included); 82 keep the default.
Fused into the existing document — stable ids and Marguerite survive.

## Iteration notes (kept honest)

- First atmosphere pass: fog_density 0.0035 was a sandstorm whiteout at
  aerial range; 0.0009 keeps depth without eating the scene.
- Wall/terrain colors sat too close (ruins read as dunes) — walls darkened,
  weeds darkened to read against dead grass.
- 24 s styling for 2,573 features + 3,000 clumps; glb 15 MB.

## Follow-ups

- **Weed colliders**: `_add_trimesh_collision` gives every blob a trimesh
  collider (17.6 k colliders, up from 8.3 k) — a no-collision naming
  convention for decoration meshes is the cheap fix.
- Rubble is under-shown at street level — bigger remnant shells and debris
  spill past the footprint would sell close-ups.
- Ground decay: cracked-lot patches, ash drifts (style_terrain zones — pairs
  with the landcover gap #3).
- Style masks / resolution regime (visual-identity v3 material): the
  pixel-art mask from the platform brief.
