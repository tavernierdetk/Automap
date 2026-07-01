# Exploration — Terrain-first branch (DEM → Godot terrain)

**Status:** **BUILT (Option A).** De-risk probe done, then implemented:
`02_run_odm.sh --terrain` produces the DEM/orthophoto, `scripts/03b_dem_to_terrain.py`
turns the DTM + orthophoto into a textured grid-mesh `.glb`, and `ingest.py --terrain`
orchestrates it (manifest `kind: terrain`). Terrain3D (Option B) remains a future
upgrade. This doc records what the elevation products look like and the design.

**Idea:** instead of decimating the lumpy textured scan mesh (mesh-first), build a
clean **heightmap terrain** from ODM's elevation model, textured with the
orthophoto. Cleaner, regular topology, LOD-friendly, performant — and the natural
substrate for [feature substitution](feature-substitution.md) (trees as assets on
bare ground).

---

## What we verified (probe on the samples reconstruction)

Resumed ODM on the existing `work/odm` with `--dsm --dtm --orthophoto` (it skipped
the heavy stages and only rasterized — ~1 min). Inspected via the ODM image's
bundled GDAL. Results:

| Product | File | Result |
|---|---|---|
| **DSM** (surface, incl. trees) | `odm_dem/dsm.tif` | 1681×1394 px, 0.12 m/px, relief **16.6 m** |
| **DTM** (bare ground) | `odm_dem/dtm.tif` | same grid, relief **9.1 m** |
| **Orthophoto** | `odm_orthophoto/odm_orthophoto.tif` | 0.12 m/px, RGBA, crisp |

Footprint ≈ 200 × 166 m — consistent with the mesh-first model (scale checks out).
The run was properly georeferenced from the photos' real GPS EXIF (UTM 17N).

**Two findings that matter:**
1. **The DTM strips vegetation.** Bare-ground relief (9.1 m) is ~8 m lower than the
   surface (16.6 m) exactly where trees are. So the DTM gives us clean ground for
   free — trees become asset instances on top, not blobs baked into the terrain.
2. **The orthophoto is detection-grade.** At 12 cm/px every tree crown is distinct,
   so it's both the ground texture *and* a strong input for 2D tree detection
   (DeepForest). Terrain-first and the tree work share this artifact.

(Heightmap + ortho previews were generated to `work/odm/odm_dem/dsm_preview.png`
and `.../ortho_preview.png` — gitignored; regenerate from the tifs as needed.)

---

## What building the branch involves

### Generation side (ours)
1. **Run ODM far enough.** Today we stop at `mvs_texturing`. Terrain-first needs
   the DEM + orthophoto, i.e. run with `--dsm --dtm --orthophoto` and
   `end_with = odm_orthophoto`. → a "terrain mode" toggle in `config.toml` /
   `02_run_odm.sh`.
2. **New stage `03b_dem_to_terrain`.** Convert `dtm.tif` (+ `dsm.tif` option) to a
   heightmap and build a terrain asset:
   - GeoTIFF → normalized heightmap (PNG/EXR). GDAL does this; we have no local
     GDAL, so either use the ODM container (as the probe did) or add `rasterio`
     to the venv.
   - Build a **displaced grid mesh** in Blender (subdivided plane + displace by the
     heightmap), apply the **orthophoto** as the ground texture, export `<name>.glb`.
   - **Reuses the exact stage-3 → glb → engine contract.** No new playback
     dependency, no change to the hand-off.

### Playback side (theirs) — two options
- **Option A — heightmap-as-glb (recommended first):** the terrain ships as an
  ordinary `.glb` (a clean displaced grid). The engine already loads glbs by name —
  **zero new dependency, nothing to coordinate.**
- **Option B — Godot Terrain3D (later upgrade):** a GDExtension plugin (clipmap LOD,
  paintable, built-in collision). Best quality/perf for large terrain, but a native
  per-platform dependency to install into `godot/addons/`, and it touches the
  playback engine's architecture. Worth it later for big/streamed maps; overkill now.

---

## The caveat that decides scope: 2.5D

A heightmap stores one height per (x, z) — so terrain-first **cannot represent
overhangs, caves, or vertical cliff faces.** For a mostly-flat park, that's fine.
But the eventual real target is **Îles-de-la-Madeleine — coastal cliffs**, which is
exactly where 2.5D loses the most. So:

- Terrain-first is a **parallel branch, not a replacement** (as the spec intends).
- Mesh-first stays the path when verticality matters (cliffs, overhangs).
- Likely end state: pick per-scene, or composite (terrain ground + mesh-first
  cliff chunks). Worth deciding before the Madeleine footage lands.

---

## Recommendation

Build terrain-first as **Option A** (heightmap → grid-mesh `.glb`), gated behind a
config toggle, leaving mesh-first intact. Cheapest path to a clean, performant,
asset-ready ground; defers Terrain3D and the playback-contract change until there's
a reason. It also unlocks the tree work, since it produces bare ground + a
detection-grade orthophoto in one shot.

**Open questions:**
1. `rasterio` in the venv vs. shelling GeoTIFF conversion to the ODM container?
2. Per-scene mesh-first vs terrain-first selection — config flag, or auto-heuristic?
3. When (if) do we want Terrain3D, given the cliffs target?

---

Related: [pipeline primer](../primer.md) · [feature substitution](feature-substitution.md) · [named ingestion](named-ingestion.md)
