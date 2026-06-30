# Automap — Design Spec

**Date:** 2026-06-30
**Status:** Approved (design) — pending written-spec review
**Repo:** `~/Cowork/Automap` (own git repo → personal GitHub; never a Baseline remote)

---

## 1. Purpose & scope

Automap is a **self-contained, reproducible pipeline that turns a drone video clip into a walkable Godot scene.**

The drone footage is the *test input*, not the deliverable. The deliverable is the toolchain itself: a staged `drone video → playable Godot scene` pipeline that can be re-run on any clip.

### Primary target (build this)
**A reusable pipeline (mesh-first).** Given an `.mp4`, produce a crude-but-real textured 3D mesh of the filmed place and let you walk around it in Godot. Reproducibility and clean stage boundaries matter more than this one scene looking polished. A "scan-artifact world" is an acceptable — even expected — v1 result.

### Future ambition (plan toward, don't build yet)
**A rudimentary video game (future-C).** The reconstructed environment becomes set dressing for something with mechanics. We design so this is a *bolt-on* to the existing Godot project, not a rewrite — hence stage 4 already ships a player controller and a real scene.

### Non-goals (v1)
- Polished/optimized game-ready terrain (that's the terrain-first branch, see §8).
- One-button orchestration (premature — see §4).
- Gaussian splatting, cloud rendering, multi-clip stitching.
- Any dependency on a Baseline system, MCP, or remote.

---

## 2. Constraints

| Constraint | Implication |
|---|---|
| **Machine: Apple M4, 16 GB unified memory, macOS 15.5** | Memory is the ceiling, not CPU. Every heavy stage needs guardrails (frame caps, downscaling, conservative ODM quality). |
| **Local-first** | Everything runs on the MacBook for now. An NVIDIA 16 GB box exists as an escape hatch but is explicitly *not* the early path. |
| **All tools free / open-source** | ffmpeg, OpenDroneMap, Blender, Godot — all FOSS. |
| **Native arm64 preferred** | ffmpeg, Blender, Godot are native arm64. **ODM is the exception** (see §3, §7). |

---

## 3. Governing principle: de-risk ODM-on-Apple-Silicon first

The single assumption that can sink this plan is **OpenDroneMap running acceptably on the M4.** ODM's Docker image targets `amd64`; on Apple Silicon it runs under qemu emulation — slower *and* more memory-hungry — and Docker Desktop only allocates its Linux VM a slice of the 16 GB.

**Therefore the first thing the project does is a throwaway spike**, before any structure is polished:

> Feed ~40 downscaled frames through ODM in Docker and confirm it produces a textured `.obj` on this machine without OOM-ing — and measure how long it takes.

- **Spike passes** → proceed exactly as designed.
- **Spike fails / unbearable** → pivot stage 2 *before* building around a false assumption. Options: Meshroom, the NVIDIA box, or accepting overnight runs.

The pipeline is structured so **stage 2 is a swappable box**, precisely because it is the risky one. The spike result is recorded in `docs/decisions/`.

---

## 4. Architecture: staged, manually-chained CLI (mesh-first)

Five stages. Each is a standalone command that reads the previous stage's output folder and writes its own. You run them in sequence and **inspect the artifact between each** — photogrammetry fails visibly, and the staged approach exists to catch garbage early.

We deliberately do **not** build a one-button orchestrator in v1: it would hide exactly the intermediate failures we need to see. The stage *boundaries* are what matter; wrapping them in a `Makefile` or a single command later is cheap once they're stable.

| # | Stage | Tool | Reads | Writes | Inspect |
|---|-------|------|-------|--------|---------|
| 0 | **Input** | — (drop zone) | — | `input/clip.mp4` (+ optional `.srt`) | — |
| 1 | **Extract frames** | `ffmpeg` + OpenCV sharpness cull | `input/` | `work/frames/*.jpg` | Frames sharp, well-overlapped? |
| 2 | **Photogrammetry** ⚠️ | **OpenDroneMap (Docker)** — the swappable risky box | `work/frames/` | `work/odm/` (textured `.obj`, point cloud, DEM, orthophoto) | Mesh reconstructed? Holes? |
| 3 | **Mesh cleanup** | **Blender headless** (`--background --python`) | `work/odm/…obj` | `work/mesh/scene.glb` | Decimated, scaled, Y-up, centered? |
| 4 | **Godot scene** | **Godot 4.x** | `work/mesh/scene.glb` | `godot/assets/` + walkable scene | Can I walk around it? |

### Stage notes
- **Stage 1 — DJI `.SRT` is auto-detected, never required.** If a sidecar is present, parse it → write GPS EXIF onto frames (or an ODM `geo.txt`) so ODM gets georeferencing for free. If absent (the common AirDrop case for the DJI Mini 3), skip silently; ODM solves structure-from-motion blind. Frame rate, max-frame cap, and sharpness threshold live in `config.toml` — these are the **memory guardrails**.
- **Stage 2** is a thin shell wrapper around the Docker invocation, with ODM quality knobs (`--resize-to`, `--feature-quality`, `--pc-quality`, `--max-concurrency`) surfaced in config. This is the box we tune hardest for 16 GB and the box we'd swap if the spike fails.
- **Stage 3** owns the coordinate-system fix that will otherwise bite: ODM outputs real-world scale, Z-up; Godot is Y-up, metric. Blender recenters to origin, rotates, decimates.
- **Stage 4** ships a minimal Godot project with a fly/walk camera and trimesh static-body collision — both the v1 viewer *and* the seed for future-C.

---

## 5. Directory structure

```
Automap/
├── README.md
├── config.toml                  ← all tunables: fps, frame cap, ODM quality, decimate ratio
├── pyproject.toml               ← Python deps (opencv, piexif/SRT parser, typer for CLI)
├── .gitignore                   ← input/, work/, *.glb, large binaries — NEVER commit footage
├── input/                       ← drop clip.mp4 (+ .srt) here          [gitignored]
│   └── .gitkeep
├── work/                        ← ALL intermediates                    [gitignored]
│   ├── frames/
│   ├── odm/
│   └── mesh/
├── scripts/
│   ├── 01_extract_frames.py
│   ├── 02_run_odm.sh
│   ├── 03_mesh_to_glb.py        ← run via Blender's bundled Python
│   └── 04_prepare_godot.py
├── godot/                       ← Godot 4.x project (viewer + future-game seed)
│   ├── project.godot
│   ├── scenes/main.tscn
│   └── assets/                  ← glb lands here (large ones gitignored)
├── samples/                     ← tiny fallback frame set, runs the chain pre-footage
└── docs/
    ├── pipeline.md              ← how to run + what to inspect at each stage
    ├── capture-guide.md         ← how to fly the Mini 3 for good reconstruction
    └── decisions/               ← short ADRs (the ODM-arch spike result lives here)
```

Two deliberate choices:
- **`work/` and `input/` are gitignored** — footage is ~1.24 GB; git is the wrong home for it.
- **`samples/`** holds a tiny frame set so the chain is runnable and testable *before* the park clip lands.

---

## 6. Test input

- **Drone:** DJI Mini 3, flown via DJI Fly on an iPhone 11 Pro.
- **First clip:** a local park, 2:04, ~1.24 GB `.mp4` (≈80 Mbps, consistent with 4K). At ~0.5–1 fps extraction that's ~60–120 frames — a reasonable ODM job for 16 GB once downscaled and capped.
- The target Îles-de-la-Madeleine footage does not exist yet; the park clip is the shake-out input. `samples/` covers the gap before even that lands.

---

## 7. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **ODM under qemu on M4 is too slow / OOMs** | High | The §3 spike, run first. Stage 2 is swappable (Meshroom / NVIDIA box / overnight). |
| **Docker VM memory slice too small** | Medium | Tune Docker Desktop memory allocation; downscale frames; cap frame count. |
| **Motion blur / fast cinematic flying** | Medium | OpenCV sharpness cull in stage 1; capture-guide documents slow, high-overlap flying. |
| **Hard-to-reconstruct subjects** (water, waves, tall grass, reflective surfaces) | Medium | Capture-guide steers toward textured solids (cliffs, roads, dunes, buildings). Park clip is a decent middle case. |
| **Coordinate-system / scale mismatch** | Low | Owned explicitly by stage 3. |

---

## 8. Future branches (designed-for, not built)

- **Terrain-first branch.** Same ODM output (stage 2) → a `03b_dem_to_heightmap.py` (GDAL) → Godot **Terrain3D**, orthophoto as ground texture. Cleaner, performant, LOD — the better substrate for the game, but 2.5D (loses cliffs/overhangs). Added as a parallel stage 3, not a replacement.
- **Future-C game.** The `godot/` project already carries a player controller and a real scene; gameplay grows there incrementally.

---

## 9. Testing approach

Photogrammetry output itself isn't unit-testable, but the **glue is**:
- Frame extraction produces N frames from the `samples/` set.
- SRT parser: unit tests on a sample `.srt`.
- Blender script runs headlessly on a tiny test `.obj`.
- Godot project opens / imports the glb headlessly.

The `samples/` fallback lets the whole chain run green before the 1.24 GB clip exists.

---

## 10. Decisions locked

- Target **B (self-contained pipeline)**, **mesh-first**, future-C as a bolt-on.
- Local on the M4; NVIDIA box is an escape hatch only.
- **Staged manually-chained CLI** (approach A), not one-button.
- Repo at `~/Cowork/Automap`, own git, personal GitHub, never Baseline.
- **De-risk ODM-on-M4 before anything else.**
