# ULPC × casting chain — animated composable people (2026-07-18)

The examination the Casting Director asked for: hook the NPC Creator to
the ULPC composer built in **PixelAssetCreator**
(`~/Cowork/PixelAssetCreator`, github.com/tavernierdetk/PixelAssetCreator)
so cast members stop being single-frame figures and become composed,
fully animated people (walk/run/idle in four facings) drawn from the
free LiberatedPixelCup asset base.

## What each side already has

**Theirs (PixelAssetCreator — reuse, don't rebuild):**
- `packages/sprite-compose` → `composeULPCExport({build, outBaseDir,
  slug})` — a PURE function: `ulpc.build/1.0` spec (layers:
  category/variant + palette/tint) → per-animation composed sheets +
  sliced frames + `ulpc.manifest/1.0`. No redis/workers/api needed.
- `packages/sprite-catalog/vendor/ulpc-src` — git submodule of the
  Universal LPC Spritesheet Generator (CC-licensed sheets +
  `sheet_definitions`). The free, composable asset base.
- `packages/intermediary-converter` — CharIntermediary (body/head/
  categories/colors) → validated build spec (color dictionary, variant
  resolution). Optional for v1; the LLM-assistants package is NOT
  needed (the session is the assistant).
- The slicer's `orientationDirs` output names folders
  `${TitleCase(anim)}_${orientation}` with orientations
  front/back/left/right.

**Ours (Automap / entropy-remade):**
- Stage-12 publisher already builds engine manifests from frames dirs
  with per-animation subdirs — the zo/lily/carmilla reference people
  came from `ulpc_frames/` dirs of exactly this shape.
- Engine (`overworld_player.gd`) resolves animations as
  `Run_<face>` → `Walk_<face>` → `Idle_<face>` → `Walk`/`Idle`,
  faces `front|back|left|right`; `CreatureSprites` normalizes texture
  height to 96 px (ULPC 64 px frames scale 1.5 — proven by the player).
- The casting chain (sheets, populate gate, baker placement) — R3.
- `creature@` already has `visual.family: "ulpc"`.

## The animation normalization contract (the law this doc exists for)

One naming convention, engine-side, everywhere:

| ULPC anim × LPC row | engine animation | fps | notes |
|---|---|---|---|
| walk × down/up/left/right | `Walk_front/back/left/right` | 8 | LPC col 0 is the stance frame — kept (read as step-cycle rest) |
| idle × 4 rows | `Idle_front/back/left/right` | 4 | engine falls back `Idle_front` → `Idle` |
| run × 4 rows | `Run_front/back/left/right` | 10 | engine falls back to Walk_<face> when absent |
| slash/thrust/shoot/hurt/jump/sit/emote/climb/combat | `TitleCase_<face>` | 8 | composed ONLY when a build asks (combat arrives with R5 encounters) |

- The slicer's folder naming IS this contract (`Walk_front`, …) — the
  bridge maps nothing, it only relocates and prunes.
- Manifest fps becomes per-animation: `creature_sprites` entries in
  `assets.json` accept `"fps": {"Walk_front": 8, "Idle_front": 4, …}`
  (int still valid = same fps for all). The publisher writes fps per
  animation into the runtime manifest it already builds.
- Overworld cast composes `walk + idle + run` only; nothing else is
  paid for until a chair needs it.
- Stature stays an ENGINE concern (`height_target_px`); ULPC children
  use the LPC `child` body type, not canvas headroom.

## The bridge (what actually gets built)

1. **Committed source of truth per person**:
   `games/<g>/casting/builds/<slug>.ulpc.json` — an `ulpc.build/1.0`
   spec (mode `split_by_frame`, animations `["walk","idle","run"]`).
   Recipes committed, pixels staged — same law as props.
2. **Compose door**: `15 npc compose <slug>` →
   `tools/ulpc_compose.mjs` (node, imports `@pixelart/sprite-compose`
   from the PixelAssetCreator checkout; `PIXELASSET_ROOT` env
   overrides) → frames staged to
   `work/game/<g>/creatures_px/<slug>/<Anim>/` → `assets.json`
   registered with per-anim fps (`"local": true`, family `ulpc`).
3. **Publisher**: fps-dict support (one small edit) — manifests carry
   per-animation fps.
4. **Engine — NPCs that actually walk**: `overworld_npc.gd` gains a
   `behavior` (`post` = stand, `wander` = stroll within a radius of the
   socket, facing-correct Walk anims, pause beats); casting sheets gain
   the optional field; the baker passes it through. Dialogue lock:
   wandering pauses while talking, same as the player.
5. **Chair placement**: the tool belongs to the NPC Creator under the
   Casting Director — `/npc-director` documents the ULPC channel as
   the DEFAULT for cast bodies; `figure_px` remains for portraits and
   one-off look development (the 16 generated faces become dialogue
   portraits when the Interface chair lands — they are too good to
   discard, and too styled to walk beside LPC bodies).
6. **Style law**: a scene's cast is ONE body family — no figure_px
   body standing beside a ULPC body (they read as different games).
   The fair recasts to ULPC bodies in the same change that lands the
   bridge.

## Setup facts (one-time)

- `git submodule update --init packages/sprite-catalog/vendor/ulpc-src`
  (the sheet library; large).
- `pnpm install && pnpm --filter @pixelart/sprite-compose... build`
  (sharp et al.). Node ≥ 20 present (v25).
- PixelAssetCreator stays a sibling checkout, read-mostly: Automap
  imports its BUILT packages; any fixes needed upstream go to its own
  repo, never copied in.

## Landed 2026-07-18 (same day) — what the pilots taught

All six work items below shipped; the fair's 16 sprite-bearing cast
members are ULPC bodies with walk/idle/run ×4 facings, seven of them
wandering. Contract corrections discovered by the pilots, now law:

- **Build specs speak DISK vocabulary**: categories are vendor
  `spritesheets/` paths (sheet_definitions layer paths, e.g.
  `torso/clothes/longsleeve/longsleeve/male` — NOT the pretty enum
  names), variants are file stems (`forest_green`). The
  intermediary-converter that translated pretty→disk is not wired;
  if it ever is, it slots in front of this contract unchanged.
- **Walk-only compose + synthesis**: most clothing layers ship ONLY
  walk (+combat) sheets; composing idle/run natively drops those
  layers → naked NPCs. The bridge composes `walk` (fully dressed by
  construction) and synthesizes `Idle_*` (stance frame, 4 fps) and
  `Run_*` (step cycle, 10 fps). Native idle/run can return per-build
  later behind a flag once layer coverage is verified.
- **Front/back swap**: the composer labels LPC row 0 (walking up,
  back visible) "front"; engine "front" faces the camera. The bridge
  swaps; left/right are true.
- **bg/fg-split hair** (braid, bunches) doesn't resolve through the
  composer's path logic — silently bald. Use styles with per-anim
  dirs (bob, bangsshort, pigtails); upstream fix belongs in
  PixelAssetCreator's resolver, not copied here.
- **Result via file, not stdout** — the composer's pino logger owns
  stdout; the bridge CLI writes its JSON result to a path.

## Order of work

1. Plan doc (this) + submodule/deps setup.
2. Bridge CLI + `15 npc compose` + publisher fps-dict + tests
   (normalization mapping tested against a synthetic frames tree; the
   compose test skips when the vendor tree is absent).
3. Pilot: 3 builds (prefect_cassia, magister_brontes, student_aulus) —
   compose, publish, snapshot beside the player for scale/style.
4. Wander behavior in the engine + sheet `behavior` field + re-bake.
5. Batch: builds for the remaining cast; recast the fair; zone
   verdicts appended to the brief.
6. `figure_px` portraits filed for the Interface chair (R5 debt).
