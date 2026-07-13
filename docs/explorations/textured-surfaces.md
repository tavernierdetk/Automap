# Textured surfaces + passable roads — styling capabilities, slice 2

**Status: built, 2026-07-12.** Two playtest marks addressed: roads no longer
block the walking character, and buildings/roads/roofs stopped being
single-color — stage 6 now bakes **procedural textures** into the glb,
selected and tiled by the identity.

## Part A — roads are decoration, not obstacles

Diagnosis: road ribbons floated 0.35 m above terrain (`ROAD_LIFT`, tuned for
bumpy ODM melt), every mesh got a double-sided trimesh collider, and Godot's
`move_and_slide()` has no step-up — so each ribbon edge was an impassable
35 cm wall.

Fix — the **`deco_` convention**: roads, weeds, and water export with
`deco_*` names (`scene.add_geometry(geom_name=…)`; names survive glb →
Godot); `map_loader._add_trimesh_collision` skips them. The terrain below
carries the player — a road is walked *through*, never jumped onto.
`ROAD_LIFT` dropped to 0.12 m (z-fighting margin only). Plateau colliders:
**17,579 → 7,515**. Integration-tested: deco meshes carry zero colliders and
a ray dropped through a road lands on the terrain (`[lagrave populate]`).

## Part B — procedural textures (`automap/facades.py`)

The texture path was already proven in-repo (stage 3b bakes the orthophoto
via PIL → `baseColorTexture` + UVs; Godot renders glb materials verbatim), so
the whole feature is pipeline-side. The economics that shaped it: ~1,500
buildings must share a **handful** of images.

- **Wall = one tileable storey tile** (256², brick/siding/concrete): u spans
  one window bay (`window_tile_m`), v one storey (`storey_m`). Wall UVs
  repeat it, so the measured LiDAR heights produce the right number of
  window rows from a single image — storey-awareness for free. Window
  states (dark/lit/boarded/broken) draw per-variant from identity weights;
  postapo boards them up.
- **Roof/road tiles are near-neutral** and tinted per instance through
  `baseColorFactor` (glTF multiplies factor × texture): one tin/membrane/
  shingle image serves the whole roof palette; one asphalt image (cracks,
  dashed centerline, gutter grime) serves every road including per-road wear.
- **Geometry**: walls became unwelded quads with UVs (winding set per wall
  against the footprint centroid); roofs get planar XZ UVs; `road_ribbon`
  grew lengthwise UVs (attached before vertex cleanup so trimesh masks them).
  Textured buildings keep the door trim box but drop the window box — the
  texture carries the windows.
- **Contract**: `visual-identity@2.1.0` (additive) — optional `textures`
  block. `identities/postapo.json` and the built-in `plateau` identity use
  it; `madelinot`/no-block identities render the flat path unchanged
  (regression-tested: no UVs anywhere when the block is absent).

## Found along the way

A "flat untextured wall" in the renders turned out to be a **35 m paper-thin
charred remnant slab**: `rubble_parts` capped debris piles at 3 m but scaled
remnant wall stubs with `wall_h` unbounded — the collapsed 72 m tower left a
skyscraper-sized wafer. Stubs now cap at 9 m.

## The AI tier (next, not now)

`facades.py` sits behind the same `baseColorTexture` slot an image model
would fill. When genserver grows a diffusion worker, a `"generated"`
facade_style routes the tile request there (PixelAssetCreator's
image-adapter facade + palette quantizer, per the reuse ledger) and nothing
downstream changes — same UVs, same materials, same glb.

## Follow-ups

- Sunlit faces still flatten under filmic tonemap at high sun energy —
  normal/roughness variation (or a texture-space AO band under eaves) would
  keep pattern in full light.
- Gable roof planar-XZ UVs stretch on steep slopes (acceptable at current
  pitches).
- Terrain texturing (ground tiles) deliberately out of scope — pairs with
  the landcover-zones gap.
- Facade texel density is uniform; tall towers could take a 512 tile.
