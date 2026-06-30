# Automap — Implementation Plan

**Date:** 2026-06-30
**Status:** Proposed — awaiting approval before any heavy work
**Spec (source of truth):** `docs/2026-06-30-automap-pipeline-design.md`

This plan implements the spec; it does not redesign it. It is ordered so the
**ODM-on-Apple-Silicon de-risk spike is the first real step** — nothing
structural gets built around stage 2 until the spike passes.

---

## Sequencing principle

> Hygiene (done, zero-risk) → **SPIKE (gate)** → build stages 1→4 → docs.

If the spike fails, we **stop** and pick a stage-2 alternative with you
(Meshroom / NVIDIA box / overnight ODM) before writing any code that assumes ODM
works locally. Everything after the gate is contingent on it passing.

---

## Phase 0 — Project hygiene  ✅ DONE (zero-risk, pre-approved by spec)

- [x] `input/` drop-zone + `work/{frames,odm,mesh}` created (with `.gitkeep`s)
- [x] `.gitignore` — excludes `input/`, `work/`, and media/3D binary extensions
- [x] **Footage-never-in-git guard verified** — a dummy `input/clip.mp4` and
      `work/**` artifacts are confirmed ignored; `git status` stays clean of them
- [x] `CLAUDE.md` for future sessions
- [ ] Commit this hygiene + the two docs (one commit, no footage)

---

## Phase 1 — ODM de-risk SPIKE  ⚠️ THE GATE (first real step)

**Goal:** confirm OpenDroneMap produces a **textured `.obj` without OOM-ing** on
this M4, and measure how long it takes. Throwaway — code is not kept; the
**result is recorded in an ADR**.

**Pre-step — Docker memory.** Docker's Linux VM currently has only **~7.65 GB**
of the 16 GB. ODM under qemu is memory-hungry. Recommend bumping the VM to
**~12 GB** (Docker Desktop → Settings → Resources) before the run. *(Decision A —
see below.)*

**Spike input — ~40 downscaled frames.** Two options *(Decision B)*:
- **B1 (recommended):** a small known-good public aerial set (e.g. an ODM sample
  dataset, ~40 imgs). Isolates the *one* variable we're testing — "does ODM run
  on this Mac" — without confounding it with our capture quality.
- **B2:** ~40 frames from the park clip (requires you to drop it into `input/`
  first), via a throwaway one-liner ffmpeg extraction.

**Run.** `ddronemaps/odm` (amd64) under Docker, conservative knobs for 16 GB:
`--resize-to 1024 --feature-quality medium --pc-quality low --max-concurrency 4`,
mesh generation on (we need the textured `.obj`).

**Measure & gate.** Record peak memory, wall-clock time, OOM/no-OOM, and whether
`odm_texturing/odm_textured_model_geo.obj` exists.
→ **PASS:** proceed to Phase 2.
→ **FAIL/unbearable:** STOP, write the ADR, escalate to you for the stage-2 swap.

**Deliverable:** `docs/decisions/0001-odm-on-apple-silicon.md` (ADR with the
numbers and the pass/fail call). Committed regardless of outcome.

---

## Phase 2 — Stage 1: frame extraction (proper)  [post-gate]

The first real, kept stage. Establishes the Python project skeleton.

- `pyproject.toml` — deps: `opencv-python`, `piexif`, `typer` (SRT parsing stdlib/regex)
- `config.toml` — the memory guardrails: `fps`, `max_frames`, `sharpness_threshold`,
  `resize`, plus an ODM-knobs section for stage 2
- `scripts/01_extract_frames.py` — typer CLI: ffmpeg extract at `fps` →
  OpenCV variance-of-Laplacian sharpness cull → enforce `max_frames` cap →
  write `work/frames/*.jpg`
- **SRT auto-detect / no-op:** if `input/*.srt` present, parse → write GPS EXIF
  (or ODM `geo.txt`); if absent, skip silently. Never required.
- `samples/` — a tiny committed frame set so the chain runs pre-footage
- Unit tests: extraction count on `samples/`, SRT parser on a fixture
- Commit.

---

## Phase 3 — Stage 2: ODM wrapper (proper)  [post-gate]

- `scripts/02_run_odm.sh` — thin shell wrapper around the Docker invocation,
  with all quality knobs (`--resize-to`, `--feature-quality`, `--pc-quality`,
  `--max-concurrency`) sourced from `config.toml`. Reads `work/frames/`, writes
  `work/odm/`. Encodes the spike-proven settings as defaults.
- Commit.

---

## Phase 4 — Stage 3: Blender headless mesh cleanup  [post-gate]

**Requires installing Blender** (currently missing — `brew install --cask blender`).
*(Decision C: confirm install method.)*

- `scripts/03_mesh_to_glb.py` — run via `blender --background --python`:
  import ODM `.obj` → decimate (ratio from config) → recenter to origin →
  **Z-up → Y-up** rotation → export `work/mesh/scene.glb`
- Headless test on a tiny `.obj` fixture
- Commit.

---

## Phase 5 — Stage 4: Godot scene  [post-gate]

- `godot/` — minimal Godot 4.x project (`project.godot`, `scenes/main.tscn`)
- `scripts/04_prepare_godot.py` — place `scene.glb` into `godot/assets/`
- Walk/fly camera controller + trimesh `StaticBody3D` collision (v1 viewer +
  future-C seed)
- Headless import check
- Commit.

---

## Phase 6 — Docs & wrap

- `docs/pipeline.md` — how to run each stage + what to inspect between them
- `docs/capture-guide.md` — how to fly the Mini 3 (slow, high-overlap; favor
  textured solids over water/grass/reflective)
- `README.md`
- Commit.

---

## Decisions I need from you before running the spike

- **A. Docker VM memory** — OK to bump to ~12 GB before the spike? (You'd set it
  in Docker Desktop; I can't change it from here.)
- **B. Spike input** — B1 known-good public set (recommended, isolates the M4
  variable) or B2 frames from your park clip (needs the clip dropped first)?
- **C. Blender install** — `brew install --cask blender` when we reach Phase 4? (OK)

## Notes
- Each phase ends in its own commit; the spike phase commits only its ADR.
- `samples/` (Phase 2) lets the whole chain run green before the 1.24 GB clip exists.
- The NVIDIA box stays untouched unless the spike fails.
