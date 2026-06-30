# ADR 0001 — ODM on Apple Silicon (the de-risk spike)

**Date:** 2026-06-30
**Status:** Accepted — **SPIKE PASSED**
**Context:** Spec §3 governing principle — de-risk OpenDroneMap on the M4 before
building any structure around stage 2.

## Question

Can OpenDroneMap, whose Docker image is `amd64` (emulated on Apple Silicon),
produce a **textured `.obj` on this M4 (16 GB) without OOM-ing**, in a tolerable
time? If yes → proceed as designed. If no → swap stage 2 (Meshroom / NVIDIA box /
overnight) before writing code that assumes ODM works locally.

## Setup

| | |
|---|---|
| Machine | Apple M4, 16 GB unified memory, macOS 15.5 |
| Docker Desktop VM | **12.16 GiB RAM, 10 CPUs** (bumped up from the 7.65 GiB default for this run) |
| Emulation | amd64 image runs via **Rosetta**, not qemu — this is why it's fast |
| ODM | `opendronemap/odm:latest` = **ODM 3.6.0** (`sha256:fc56c7cd…f49521`) |
| Input | **Sheffield Park 3** — 32 georeferenced DJI images (known-good public set), pre-downscaled to 2048px longest edge with `sips` (GPS EXIF preserved) |
| Knobs | `--feature-quality medium --pc-quality low --max-concurrency 4 --end-with mvs_texturing` |

Deliberately used a known-good public dataset, not the park clip's video frames,
to isolate the single variable under test: *does ODM run on this machine.*

## Result — PASS

| Metric | Value |
|---|---|
| Exit code | **0** |
| Wall-clock | **8m30s** (510 s) |
| **Peak container memory** | **2.81 GiB / 12.16 GiB (~23%)** — reached during SfM/MVS |
| OOM | **None** |
| Full 3D textured mesh | `odm_texturing/odm_textured_model_geo.obj` — **194,909 verts / 314,191 faces**, 34 MB + 13 texture PNGs |
| 2.5D mesh | also produced (202,660 verts / 383,988 faces) |

Stage timeline (all clean): dataset → split → merge → opensfm → openmvs →
odm_filterpoints → odm_meshing → mvs_texturing.

## Decision

**Proceed exactly as designed. ODM stays as stage 2.** The NVIDIA escape hatch is
not needed. The conservative knobs above become the stage-2 defaults in
`config.toml` / `scripts/02_run_odm.sh`.

## Notes & caveats

- **Two false starts, both my CLI errors, neither a machine problem** (each died
  in <45 s at argument parsing): `--end-with odm_texturing` → the stage is named
  `mvs_texturing`; and `--resize-to` **was removed in ODM 3.6.0** (it auto-resizes).
  We pre-downscale frames in stage 1 instead, which is the memory guardrail anyway.
- **What this does NOT prove:** reconstruction quality on *our* input. The spike
  used 32 sharp, well-overlapped, geotagged photos. The park clip yields video
  frames (more of them, possibly lower overlap/sharpness, no GPS). The
  machine-viability question is settled; capture/reconstruction quality is a
  separate risk owned by stage 1 (sharpness cull) and the capture-guide.
- **Headroom for scaling:** 32 imgs peaked at 2.81 GiB. The park clip at 0.5–1 fps
  is ~60–120 frames — memory/time will rise, but with ~9 GiB of headroom plus the
  frame-cap and `--pc-quality low` guardrails, the 12 GiB VM is comfortable.
  Keep Docker's VM at ≥12 GiB.
- **Reproduce:** `work/spike/run_spike.sh` (throwaway, under gitignored `work/`).
  The proper stage-2 wrapper will encode these settings.
