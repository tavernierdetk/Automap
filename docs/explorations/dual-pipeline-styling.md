# Dual pipeline + presentation layer

**Status:** **BUILT (first increment).** The second (semantic) pipeline and the
presentation abstraction now run end-to-end on the samples: orthophoto → detected
trees → styled glb (terrain + stand-in trees). Placeholder visual identity; real
art style is config, added later.

## The shape

Two **parallel, non-destructive** representation tracks of the same place, plus a
styling layer that turns them into the game's look:

```
                 Track 1 (geometry, faithful)
  MP4 ─stage1─▶ frames ─stage2─▶ ODM ─▶ mesh glb (03) / terrain glb (03b)
                                   │
                                   ├── DSM/DTM + orthophoto (terrain mode)
                                   ▼
                 Track 2 (semantic)          Presentation
   orthophoto+DEM ─stage5─▶ features.json ─▶ stage6: VisualIdentity + transformers ─▶ styled glb
```

Three layers, cleanly separated:

1. **Sources** — the faithful glbs (mesh-first, terrain-first). Canonical, never
   edited by styling.
2. **Semantic layer** — `features.json`: world-placed detections
   (`{type, x, z, height, radius}`), engine-agnostic, additive.
3. **Presentation** — a **VisualIdentity** (data: asset/colour choices + an ordered
   transformer list) + composable **Transformers** `(scene, ground, features,
   identity) → scene`. Emits a NEW styled glb; sources are untouched.

Why this matches the goal:
- **Parallel & non-destructive** — style freely, always compare against faithful.
- **Both sources feed it** — terrain + instanced trees is the natural stylized combo.
- **Visual identity is data, not code** — new look = new identity entry, same transformers.

## What's built (stages 5-6)

- **`automap/features.py` + `scripts/05_detect_features.py`** — tree detection on
  the orthophoto + DEM. A pixel is canopy when TALL (CHM = DSM−DTM ≥ `min_height`)
  and GREEN (excess-green ≥ `exg_threshold`); local maxima of canopy height become
  individual trees. World-placed in the terrain's centered metric frame. Classical
  / no-ML; a DeepForest backend can slot in behind the same `Tree` output.
  *Samples: 118 trees, heights 2–14 m.*
- **`automap/presentation.py` + `scripts/06_style_scene.py`** — `VisualIdentity`,
  a transformer registry, and `instance_trees`: replace tree features with a
  procedural stand-in (trunk + canopy, scaled by height), raycast onto the terrain
  surface. *Samples: 116/118 placed (2 outside the footprint), verified upright and
  on-surface in Godot.*
- Config `[features]`; deps `scipy`, `rtree` (+ `rasterio/trimesh/pillow` from 3b).

## Design decisions locked

- **Feature input = orthophoto** (top-down): pixel→world is automatic, height from
  the DTM. "Curated" = choosing which scenes/regions to run.
- **Framework first, style-agnostic**: placeholder identity (green cones) proves
  the plumbing; art direction is dialed in later purely as identity config.
- **Trees first** (worst-reconstructed subject, highest payoff).

## Next / open

- Real **VisualIdentity** entries (palette, asset library, materials, atmosphere)
  once an art direction is chosen — no code change, just data + assets.
- Better individual-tree separation in dense canopy (watershed / DeepForest).
- More transformers: `palette_remap`, `stylize_terrain`, `atmosphere`; more feature
  types (buildings, water/paths → material treatment).
- Wire stages 5-6 into `ingest.py` (e.g. `--features --style <id>`) once the results
  are dialed in — kept standalone for now to iterate.
- Godot-side: instance via `MultiMeshInstance3D` from `features.json` instead of a
  baked styled glb, if the playback engine prefers runtime instancing.

Related: [feature substitution](feature-substitution.md) · [terrain-first](terrain-first.md) · [primer](../primer.md)
