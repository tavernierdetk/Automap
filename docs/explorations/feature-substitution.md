# Exploration — Feature substitution (trees → assets)

**Status:** Exploration / brainstorm. Nothing built. This is the "what's involved"
map so we can decide *if*, *when*, and *which slice* to build.

**Goal:** instead of leaving trees (and later buildings, cars, benches) as raw
scan geometry, *detect* them and represent them with clean instanced 3D assets.

---

## Why trees, and why this is more than polish

Photogrammetry is **worst at exactly the things we'd most like to replace.**
Foliage has no stable features to match across frames, so trees reconstruct as
lumpy, smeary blobs — the ugliest part of every scan. Replacing them with clean
assets attacks the single biggest visual weakness, not a cosmetic edge. Trees are
the right first target because:

- highest visual payoff (they're the worst-reconstructed thing),
- well-studied problem (forestry/remote-sensing have done canopy detection for years),
- generic assets are fine — we don't need *the* tree, just *a* believable tree.

The same **detect → classify → instance** pattern generalizes later to buildings,
vehicles, street furniture.

---

## Three sub-problems (very different difficulty)

### 1. Detect — where are the trees?
Two families, best combined:

- **2D, from imagery.** Run a detector on the frames or a top-down orthophoto.
  - **DeepForest** — a pretrained model for tree-crown bounding boxes in aerial
    **RGB** (key: the DJI Mini 3 is RGB-only, so multispectral/NDVI methods are out).
    Output: crown box → center + radius.
  - Heavier general alternatives: SAM / Detectron2 segmentation with a tree class.
- **3D, from geometry.**
  - **Canopy Height Model (CHM)** = surface elevation − bare-ground elevation;
    local maxima = tree tops, peak value = tree height. Classic forestry method.
    Needs a DSM + DTM (ODM products we don't currently generate — see below).
  - **Directly on the dense point cloud we already produce**
    (`work/<name>/odm/opensfm/undistorted/openmvs/scene_dense.ply`): segment
    vegetation by color (excess-green index from RGB), then cluster (DBSCAN) into
    individual trees; height/radius per cluster.
- **Combine:** color says "vegetation," height says "tall," clustering says "how
  many distinct trees." The intersection is far more robust than any one signal.

### 2. Place — instance the assets
Given `(x, z, height, radius)` per tree: spawn models scaled to height, jittered
in yaw/scale for variety, from a small asset library. In Godot this is a
`MultiMeshInstance3D` — thousands of instances at near-zero cost. **This part is
easy and high-payoff.**

### 3. Reconcile — the scan blobs are still there
The hard part, and it forks the whole project's direction:

- **Mesh-first (current path):** the lumpy tree geometry is baked into the terrain
  mesh. Planting a clean asset means cutting it out *and* reconstructing the ground
  underneath (interpolate from surrounding terrain). Fiddly.
- **Terrain-first branch (already designed-for):** DTM → heightmap → Godot
  Terrain3D gives **bare ground by construction** — trees never entered the
  terrain, so you just drop assets on top.

> **Key insight:** feature-substitution and the terrain-first branch are natural
> partners. Wanting clean trees is a strong reason to finally stand up
> terrain-first, rather than fight the mesh.

---

## The architecture that keeps it clean: a semantic layer

Introduce a new stage (≈ **stage 3.5**) that emits a plain, engine-agnostic
`features.json` *beside* the geometry:

```json
[ { "type": "tree", "x": 12.4, "z": -8.1, "height": 9.2, "radius": 2.1 }, … ]
```

Detection writes it; the playback engine reads `glb` **+** `features.json` and
instances assets. This respects the project's decoupling principle: detection can
improve independently of rendering, and the same features file drives any engine.
It lives inside each scene's folder (see the named-ingestion exploration).

---

## Difficulty ladder (so we can choose an ambition level)

| Level | Approach | Effort | Look |
|---|---|---|---|
| **Easy — "scatter"** | segment vegetation *regions* (not individual trees), scatter assets across them | low | good enough for a game |
| **Medium — per-tree** | DeepForest or CHM local-maxima → one asset per tree, scaled to real height | moderate | convincing |
| **Hard** | clean blob removal + ground reconstruction (mesh-first), or species classification | high | precise |

The "scatter" level is a surprisingly cheap first win, especially on terrain-first.

---

## What we'd need that we don't make today

We stop ODM at `mvs_texturing`, so we currently have **no DSM/DTM/orthophoto**.
To pursue trees we'd either:
- let ODM run further (it produces DEM + orthophoto after texturing — a config
  change, not new code), **or**
- build detection on the **dense point cloud we already have**.

Tools in play: DeepForest (RGB crowns), Open3D / PDAL (point clouds), scikit-image
(CHM maxima), Godot `MultiMeshInstance3D` (rendering many instances).

---

## Open questions / decisions before building

1. Mesh-first reconcile, or commit to **terrain-first** as the substrate for features?
2. Detection signal: 2D (DeepForest) vs 3D (point-cloud cluster) vs combined?
3. Ambition level from the ladder for a first slice?
4. Does the playback engine consume `features.json`, and who owns that contract?

**Suggested first slice (when we build):** terrain-first ground + "scatter"-level
vegetation regions → tree MultiMesh. Cheapest path to a visibly better world, and
it forces the `features.json` contract early.

---

Related: [pipeline primer](../primer.md) · [named ingestion exploration](named-ingestion.md)
