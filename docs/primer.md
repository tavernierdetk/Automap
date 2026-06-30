# Automap — Pipeline Primer

A readable tour of how a drone clip becomes a walkable 3D world: the stages, the
files each one produces, the different routes you can take through the chain, and
a map of where the quality and features can be enriched.

This is the "what is actually happening and where can we make it better" doc. For
the architectural rationale see [the design spec](2026-06-30-automap-pipeline-design.md);
for the ODM-on-M4 viability result see [ADR 0001](decisions/0001-odm-on-apple-silicon.md).

---

## 1. The big picture

Automap is **photogrammetry**: it reconstructs 3D geometry from many overlapping
2D photos. A drone flies over a place; we slice the video into stills; software
finds the same physical points across many photos, triangulates where the camera
was and where those points are in space, grows that into a dense surface, drapes
the original photos back over it as texture, and we walk on the result.

```
  clip.mp4            frames/*.jpg          work/odm/                 scene.glb           Godot
 (+ .srt GPS)   ──▶   (sharp stills)  ──▶   (textured .obj +    ──▶  (clean Y-up    ──▶  (walkable
                                             point cloud, etc.)       mesh, 1 file)        scene)
   stage 0            stage 1               stage 2                   stage 3             stage 4
   drop zone          ffmpeg+OpenCV         OpenDroneMap (Docker)     Blender headless    Godot 4.x
```

Each stage is **a separate command that reads the previous stage's folder and
writes its own.** You run them one at a time and *look at the result before
moving on* — photogrammetry fails visibly (holes, smears, noise), and the staged
design exists to catch garbage early instead of at the end.

Two principles worth holding onto:
- **Generation (stages 0–3) and playback (stage 4) are decoupled.** Stages 0–3
  produce a `.glb`; stage 4 is just a viewer/engine that loads it.
- **Stage 2 is a swappable box.** It's the risky, heavy step; everything around
  it is designed so it can be replaced (different photogrammetry tool, beefier
  machine) without touching the other stages.

---

## 2. Stage by stage

### Stage 0 — Input (the drop zone)
You drop a clip into `input/clip.mp4`. Optionally a `input/clip.srt` GPS sidecar
rides along (DJI can record one). Nothing runs here. `input/` is gitignored —
footage never enters the repo.

### Stage 1 — Extract frames  · `scripts/01_extract_frames.py`
| | |
|---|---|
| **Reads** | `input/*.mp4` (+ optional `.srt`) |
| **Writes** | `work/frames/frame_00001.jpg …` (+ optional `geo.txt`) |
| **Tool** | `ffmpeg` (sampling) + OpenCV (sharpness) |
| **Run** | `.venv/bin/python scripts/01_extract_frames.py` |
| **Knobs** (`config.toml [frames]`) | `fps`, `max_frames`, `sharpness_threshold`, `resize`, `jpeg_quality` |

What it does: ffmpeg pulls a frame every `1/fps` seconds; each is scored for
sharpness (variance of the Laplacian — blurry frames have low high-frequency
energy); too-blurry frames are dropped; if too many survive, it evenly subsamples
down to `max_frames` so coverage stays spread across the flight. Frames are
downscaled to `resize` px on the long edge — **this is the main memory guardrail
for stage 2.** If a `.srt` is present its GPS is interpolated per frame into an
ODM `geo.txt`; if absent, that's a silent no-op.

**Inspect:** open a few frames — are they sharp, well-exposed, and do consecutive
ones overlap by ~60–80%? Overlap is what makes reconstruction possible.

### Stage 2 — Photogrammetry  · `scripts/02_run_odm.sh`  ⚠️ the swappable box
| | |
|---|---|
| **Reads** | a frames folder (`work/frames/` or `samples/frames`) |
| **Writes** | `work/odm/` (textured `.obj`, point clouds, …) |
| **Tool** | OpenDroneMap 3.6 in Docker (amd64 via Rosetta on Apple Silicon) |
| **Run** | `scripts/02_run_odm.sh --frames samples/frames` |
| **Knobs** (`config.toml [odm]`) | `feature_quality`, `pc_quality`, `max_concurrency`, `end_with` |

What it does, internally (you'll see these stage banners scroll by):
`dataset → opensfm` (find features, match across photos, solve camera poses =
sparse cloud) `→ openmvs` (dense point cloud) `→ filterpoints → meshing` (surface
from points) `→ mvs_texturing` (project photos back onto the mesh). We stop at
texturing (`end_with = mvs_texturing`) because the mesh-first path doesn't need
the later DEM/orthophoto products.

**Inspect:** load `work/odm/odm_texturing/odm_textured_model_geo.obj` in any 3D
viewer. Is the place recognizable? Where are the holes (water, sky, shiny or
textureless surfaces reconstruct poorly)?

### Stage 3 — Mesh cleanup  · `scripts/03_mesh_to_glb.py`
| | |
|---|---|
| **Reads** | `work/odm/odm_texturing/odm_textured_model_geo.obj` |
| **Writes** | `work/mesh/scene.glb` |
| **Tool** | Blender headless (`blender --background --python`) |
| **Run** | `.venv/bin/python scripts/03_mesh_to_glb.py --input <obj> --output work/mesh/scene.glb` |
| **Knobs** | `config.toml [mesh].decimate_ratio`; `--flip-vertical/--no-flip-vertical` |

This stage owns the **coordinate-system reconciliation** that otherwise bites you:
ODM emits a real-world-scale, **Z-up** mesh whose scanned surface faces −Z; Godot
is **Y-up**. Stage 3 imports the OBJ, joins it, **decimates** (collapses ~75% of
the faces — a scan has far more detail than a game needs), recenters it on the
origin and sits it on the ground, **flips it upright** (180° about X), and exports
a single Y-up `.glb` with textures embedded. The script re-runs itself inside
Blender if you launch it with plain Python.

**Inspect:** the script prints the model's metric size (e.g. `X=207 Y=170 Z=17` m)
and face count before/after. Sanity-check the dimensions against the real place.

### Stage 4 — Walkable scene  · Godot 4.x (`godot/`)
| | |
|---|---|
| **Reads** | `work/mesh/scene.glb` |
| **Writes** | a walkable scene (player controller + collision) |
| **Tool** | Godot 4.4 |

The `.glb` is loaded into a Godot project, given **trimesh static collision** (so
you can stand on the terrain) and a player controller, and you walk around. This
playback layer is deliberately thin and decoupled — it's also the seed for the
future game (the reconstructed place becomes set dressing). *This stage is the
most actively evolving part of the project and is developed separately from the
generation pipeline above.*

**Inspect:** can you walk on the surface? Does it look right-side-up and lit from
above? (If the terrain is dark from above / bright from below, the stage-3
vertical flip regressed.)

---

## 3. File formats you'll meet

| File | What it is | Where |
|---|---|---|
| `.mp4` | H.264 drone video — the raw input | `input/` |
| `.srt` | DJI subtitle sidecar; per-second GPS/altitude text | `input/` (optional) |
| `frame_*.jpg` | extracted, sharpness-culled, downscaled stills | `work/frames/` |
| `geo.txt` | ODM georeferencing: `EPSG:4326` then `image lon lat alt` per frame | `work/frames/` |
| `.obj` | **Wavefront mesh**: plain-text vertices (`v`), texture coords (`vt`), faces (`f`). Geometry only | `work/odm/odm_texturing/` |
| `.mtl` | **Material file** the `.obj` points to; maps each material to a texture image (`map_Kd …png`) | next to the `.obj` |
| `*_map_Kd.png` | the **albedo/diffuse textures** — the drone photos reprojected into atlases (`Kd` = diffuse color) | next to the `.obj` |
| `.ply` | **point clouds** (and raw meshes) — sparse from SfM, dense from MVS | `work/odm/odm_filterpoints/`, `opensfm/…/openmvs/` |
| `.glb` | **binary glTF** — one self-contained file with mesh + textures, **Y-up**, the modern game/web 3D interchange format. The clean hand-off to Godot | `work/mesh/` |

Mental model of the `.obj` + `.mtl` + `.png` trio: the OBJ is the *shape*, the MTL
is a *lookup table*, the PNGs are the *paint*. The GLB packs all three (plus the
Y-up convention) into one file so nothing can get separated.

**Not produced by default** (we stop at texturing): a **DEM** (Digital Elevation
Model — a GeoTIFF heightmap) and an **orthophoto** (a flat top-down stitched
image). Those are the inputs the *terrain-first* branch would need (see §5).

---

## 4. Ways through the pipeline

The staged design means you rarely re-run everything. Common routes:

- **Full chain, fresh footage:** stage 1 → 2 → 3 → 4, inspecting between each.
- **Skip stage 1 (no video yet):** point stage 2 straight at the committed
  `samples/frames` set — `scripts/02_run_odm.sh --frames samples/frames`. This is
  how the chain runs green before any real clip exists.
- **Re-tune stage 3 only:** ODM is the slow part. Once `work/odm/` exists, iterate
  on decimation/orientation by re-running just stage 3 against the same OBJ —
  seconds, not minutes.
- **Stop ODM early / go further:** `end_with` controls where stage 2 halts.
  `mvs_texturing` (default) gives the textured mesh; removing it (or a later
  value) also produces the DEM and orthophoto.
- **Swap the box:** if ODM ever becomes unworkable, stage 2 can be replaced
  (Meshroom, a CUDA box, an overnight run) without changing stages 1, 3, 4 —
  they only care about the frames-in / `work/odm/`-out contract.
- **Inspect-only:** run stage 1 alone to vet capture quality before committing to
  a long ODM run.

---

## 5. Where we can enrich things (the reference map)

A menu of levers, by stage. Roughly ordered easy→ambitious within each.

### Capture & Stage 1 — *garbage in, garbage out; this is the highest-leverage stage*
- Fly slower with more overlap, in even light (a capture guide is planned).
- Tune `sharpness_threshold` / `fps` for the specific clip.
- Record/AirDrop the `.srt` so ODM gets GPS → faster, metrically-scaled solves.
- Smarter frame selection (overlap-aware, not just time-spaced).

### Stage 2 — *reconstruction fidelity vs. time/memory*
- Raise `feature_quality` / `pc_quality` (`medium`/`low` → `high`/`ultra`) — denser,
  cleaner geometry, at real memory/time cost. The 16 GB M4 is the ceiling here.
- Feed more frames / higher `resize` (less downscaling).
- Ground Control Points or the `.srt` for true scale and georeferencing.
- The escape hatch: run the heavy settings on the NVIDIA box.

### Stage 3 — *making a scan into a usable asset*
- Less aggressive `decimate_ratio` for more detail (heavier scene), or **LODs**
  for both detail and performance.
- Hole-filling / smoothing / removing floating-junk islands.
- Bake **normal maps** from the high-res mesh so a light mesh keeps fine detail.
- Split a big scan into tiles/chunks for streaming and culling.

### Stage 4 — *from viewer to world*
- Better collision (convex chunks vs. one big trimesh), nicer lighting/sky/fog.
- Player feel: walk vs. fly tuning, footstep clamping to terrain.
- **Gameplay** ("future-C"): the scan as set dressing for mechanics.

### New parallel branches (designed-for, not built)
- **Terrain-first:** ODM's **DEM** → a `03b_dem_to_heightmap.py` → Godot
  **Terrain3D**, with the **orthophoto** as the ground texture. Cleaner, LOD-friendly,
  performant — but 2.5D (loses cliffs/overhangs). A parallel stage 3, not a replacement.
- **Multi-clip / larger areas**, **Gaussian splatting** as an alternate stage 2,
  one-button orchestration once the boundaries are stable.

---

## 6. Thirty-second glossary

- **Photogrammetry** — 3D from overlapping 2D photos.
- **SfM (Structure from Motion)** — solving where each photo was taken + a sparse
  point cloud, from feature matches.
- **MVS (Multi-View Stereo)** — densifying that into a full point cloud / surface.
- **Point cloud** — millions of colored 3D points, no surface yet.
- **Mesh** — points connected into a surface of triangles.
- **Texture / albedo (`Kd`)** — the photographed color draped over the mesh.
- **DEM** — elevation-only heightmap (top-down). **Orthophoto** — flat stitched
  top-down image. **Decimation** — reducing triangle count. **Trimesh collision**
  — physics that matches the mesh triangle-for-triangle.
- **Z-up vs Y-up** — which axis points skyward; ODM is Z-up, Godot is Y-up. Stage 3
  reconciles them.
