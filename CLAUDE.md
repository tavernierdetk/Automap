# CLAUDE.md — Automap

Personal project. **Not work — no Baseline anything, never push to a Baseline remote.**

## What this is
A self-contained, reproducible pipeline that turns a drone video clip into a
walkable Godot scene. **Mesh-first.** The drone footage is the test input, not
the deliverable — the deliverable is the staged toolchain itself.

The source of truth is **`docs/2026-06-30-automap-pipeline-design.md`**. Read it
before changing architecture. Don't redesign it; implement it. The implementation
plan lives in `docs/2026-06-30-automap-implementation-plan.md`.

## The 5 stages (manually chained, inspect between each)
0. **Input** — drop `input/clip.mp4` (+ optional `.srt`) [gitignored]
1. **Extract frames** — `ffmpeg` + OpenCV sharpness cull → `work/frames/`
2. **Photogrammetry** ⚠️ — OpenDroneMap in Docker → `work/odm/` (the risky, swappable box)
3. **Mesh cleanup** — Blender headless → `work/mesh/scene.glb`
4. **Godot scene** — Godot 4.x → walkable scene

We deliberately do NOT build a one-button orchestrator. Stage boundaries are the
point; you run each stage and inspect its artifact before the next.

## Hard constraints
- **Machine: Apple M4, 16 GB unified memory, macOS 15.5. Memory is the ceiling.**
  Everything heavy needs guardrails: frame caps, downscaling, conservative ODM quality.
- **Local-first.** Everything runs on this Mac. The NVIDIA 16 GB box is a
  last-resort escape hatch — do NOT reach for it unless the ODM spike proves
  ODM is unworkable here.
- **Biggest risk: OpenDroneMap on Apple Silicon** (amd64 image → qemu emulation,
  memory-hungry). De-risk it FIRST with a throwaway spike before building structure.
- Stage 2 (ODM) is a deliberately swappable box.

## Conventions
- Code and comments in **English**.
- CLI built with **typer**. Godot **4.x stable**.
- DJI `.SRT` GPS sidecar is **auto-detect / no-op, never required**.

## The one rule that's annoying to undo
**Footage and intermediates NEVER enter git.** `input/` and `work/` are gitignored,
plus media/3D binary extensions. The park clip is ~1.24 GB. Verify `git status` is
clean of it before any commit.

## Dev setup / how to run
- Python venv: **`.venv`** (Python 3.13, native arm64; gitignored). Deps:
  `opencv-python`, `piexif`, `typer`, `pytest`. Recreate with
  `python3.13 -m venv .venv && .venv/bin/pip install -e ".[dev]"`, then
  `.venv/bin/pip install -e ../platform-specs` (schema validation; runtime
  auto-detect/no-op without it).
- `work/<scene>/features.json` is the **per-scene world model**
  (`scene-features@2.0.0`; `automap/worldmodel.py` is the fusion engine).
  Stage-5 re-runs preserve feature ids and merge per attribute; to hand-edit
  a value so regeneration keeps it, also set its `provenance` entry to
  `"manual"`.
- Tests: `.venv/bin/python -m pytest -q` (stage-1 tests self-generate a synthetic
  clip; nothing binary is committed).
- Stage 1: `.venv/bin/python scripts/01_extract_frames.py` (reads `input/`, writes
  `work/frames/`; flags override `config.toml`).
- `samples/frames/` is a committed fallback frame set (downscaled Sheffield Park 3,
  BSD) so stages 2+ can run before real footage exists.
- **Geodata scenes (end-state B)**: `scripts/02b_fetch_geodata.py --scene <name>
  --center lat,lon --size m` (or `--geojson <polygon>.geojson` — bounds only,
  clip is a logged gap) replaces stages 0–2 with public LiDAR (NRCan HRDEM);
  then 03b/05/06/07 run without `--ortho` (no scan detection — OSM features
  only through the fusion engine); stage 5 also measures building heights per
  footprint from DSM−DTM (fusion source `lidar`, outranks OSM tag defaults).
  Proven scenes: `lagrave` (madelinot identity), `plateau` (MTL — see
  docs/explorations/mtl-acceptance-run.md and postapo-identity.md).
- **Identities are files**: stage 6 takes `--identity <name>` (built-ins) or
  `--identity identities/<file>.json` (validated vs `visual-identity@2.1.0`).
  v2 axes: decay (ruin/damage/weathering), overgrowth + road wear, and an
  `environment` block that stage 6 emits as an env.json sidecar, stage 7
  publishes beside the scene, and the engine's map_loader applies at load
  (sky/sun/fog/saturation). v2.1: the `textures` block bakes procedural
  textures (`automap/facades.py`) — storey-tile walls (UV repeat turns LiDAR
  heights into window rows), near-neutral roof/road tiles tinted per
  instance. First game identity: `identities/postapo.json`.
- **`deco_` meshes never collide**: roads/weeds/water export with `deco_*`
  names and map_loader skips their colliders — the terrain carries the
  player; a road is walked through, never jumped onto. Anything that should
  block must NOT be named `deco_*`.
- **IFC projection (stage 8)**: `scripts/08_export_ifc.py --scene <name>`
  writes one georeferenced `.ifc` per building (`automap/ifc.py`; needs
  `pip install -e '.[ifc]'`). `ifc.from_ifc` reads external plan→IFC models
  back as a `bim` fusion source. **CEC-SHA (`~/Claude/CEC-SHA`) is proprietary
  Baseline — never copy its code or `.ifc` here; the seam is IFC files only.**
- **Building substitution (stage 9)**: `scripts/09_replace_building.py
  --scene <name> --ifc <plan.ifc> --id building-NNNN` drops an authored IFC
  in place of a generated building — tessellated to `work/<scene>/assets/`,
  placed (georeference or `--footprint-fit`), written as a `representation`
  override with source `bim`. `bim` outranks detectors in the fusion engine,
  so the drop-in survives every re-run. Stage 6 renders the asset (add
  `--restyle` to repaint it in the identity).
- **Character admission (stage 10)**: `scripts/10_create_character.py
  --character godot/characters/<slug>.json [--play]` gates a
  `character-profile@2.0.0` JSON through schema validation + the autosim
  balance harness (`automap/balance.py`; aim stat totals near 25–27), then
  projects `godot/profiles/<slug>.tres`; `--play` makes it the player in every
  published scene (edits the inherited game.tscn shell). The interview flow
  that fills the JSON is the `/create-character` skill. The JSON is the
  committed source of truth; never hand-write the `.tres` or skip the gate.
- **Populate a scene**: admitted characters become NPCs via the scene's
  `godot/scenes/<name>/game.json` (`npcs[].profile` + `dialogue_variants`;
  validate against `game@1.0.0`). Worked example: Marguerite's old-quay quest
  in lagrave, played to completion headless by `test_game_integration.tscn`
  (`[lagrave populate]`). Platform plateau locked 2026-07-12: **D
  (game-creation studio) in thin vertical slices** — see the diagram changelog.

## Prerequisites (status as of 2026-06-30)
- ffmpeg ✅ (arm64, homebrew)
- Docker ✅ running — **VM allocated only ~7.65 GB / 10 CPUs**; may need bumping for ODM
- Python 3.14 ✅
- Godot.app ✅ in /Applications (no CLI symlink yet)
- Blender ❌ NOT installed — needed for stage 3
