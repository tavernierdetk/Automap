# Correction plan — brief-first scene generation & terrain vocabulary agency

**Date:** 2026-07-17. **Trigger:** the vaporis mine_hall critique (stone walls
flat, wall→floor straight cuts, cart without track, square lake, weak arches,
static water, "grass with a circle" tiles, surface grass and columns
underground). **Diagnosis in one line:** the brief was mostly right and was
written *after* the scene; the engine could not say what the brief meant —
its terrain vocabulary is a hardcoded surface meadow (`grass/path/water/
stone/bush`, grass-based transitions, identity-global colors), and its asset
prompts are tree-templated. The failures are, in order: process (no brief
upstream), vocabulary (no mine words), rendering (walls as a ground class,
static terrain), and prompting (per-family contamination).

This plan supersedes the queued "per-atlas darkening override" finding —
darkening tints the wrong vocabulary; we need new words, not tinted old ones.

## Priority 1 — Brief-first authoring (a gate, not a convention)

The mine_hall run went one-line-ask → grid; the brief was retro-authored
(its own finding F8). That inverts the whole design: the director is supposed
to fill specs from *intent*, and every downstream judgment (asset gaps,
terrain classes, snapshot verdicts) keys off intent it didn't have.

**Correction:**

- `games/<game>/levels/<id>.brief.md` becomes a REQUIRED upstream artifact.
  No zone plan, no grid, no asset request until it exists. The mine_hall
  brief is the template — its sections are the contract:
  1. **The place** — fiction + the ordered "reads" a visitor gets;
  2. **Light & air** — palette mood, what's warm/cold/dark;
  3. **Zones** — walked in order, each naming its props and NPC sockets;
  4. **Register** — three lists: terrain classes the ground needs
     (NEW section — see Priority 2), assets reused, assets to create;
  5. **Motion** — what lives, what is dead (explicit statics);
  6. **Acceptance reads** — the snapshot rubric, written before pixels.
- The create-scene skill flow is reordered: **brief → register audit →
  generate gaps → zone plan → grid → bake → snapshot judged against the
  brief's acceptance reads**. Step 1 of the skill becomes "write or load the
  brief with the user", not "catalog".
- Enforcement lives where the other gates live: `13_scene_director.py bake`
  (via stage 12) errors when no brief file exists beside the level JSON,
  and the level's `intent` field must state it summarizes the brief.
  Cheap, mechanical, annoying enough to work — same philosophy as the
  teleport-reciprocity gate.
- Snapshot verdicts are recorded against acceptance-read items (a short
  verdict block appended to the brief per run), so "does the map read?"
  accumulates history instead of vibes.

## Priority 2 — Vocabulary agency: the director identifies and generates terrain

The root cause of grass-in-a-mine, bush-as-fungus, the lawn rim on the sump,
and surface-cliff walls: `tiles2d.CLASSES` is a fixed five-class surface
biome, colored from identity-global fields, with transitions hardcoded to
`base: grass`. The director had no way to ask for earth floor, rock wall,
moss, or rail — so it painted the nearest surface word and the brief's
intent was lost in translation.

**Correction — per-atlas terrain vocabulary, director-authored:**

- The brief's register names the **terrain classes the scene needs**
  (mine_hall: packed earth, rock wall, dark water, moss, rail) with their
  mechanics flags and their transition pairs (water-over-earth,
  moss-over-earth, rail-over-earth, wall-footing-over-earth).
- `tiles2d.py` stops being a fixed menu and becomes a **painter library +
  atlas spec executor**: an atlas is built from a spec
  `{classes: [{name, painter, color, mechanics}], transitions: [...]}` where
  `painter` picks from a growing set (grass, earth, water, rock, moss,
  rail-overlay, …) and `color` is per-class in the spec — identity colors
  are the *default*, never the ceiling. The spec is authored by the director
  from the brief (and kept beside the atlas, so re-runs are deterministic).
  `tiles.json` already carries classes/flags/transition tables downstream —
  the baker barely changes.
- **Transitions are pairs in the spec, not constants**: `base` is whatever
  the scene's floor is. The sump rim becomes moss-over-earth; the lawn ring
  dies by construction.
- The **gap-detection loop that `assets ensure` already runs for props is
  extended to terrain**: catalog → diff against the brief's register →
  `atlas ensure` generates missing classes/atlases → re-catalog. The
  director's job description gains a sentence: *when the brief names a
  surface the catalog lacks, generating it is the default action, not an
  escalation.*
- **Volume is the point.** Atlases are deterministic, tiny, and free to
  regenerate; the catalog dedupes. We would rather have `vaporis_surface`,
  `vaporis_mine`, `vaporis_interior` each speaking their own vocabulary
  than contort one meadow atlas into three biomes. Never reuse a class
  because it's *there* — reuse it because the brief means it.

## Priority 3 — Walls are a thing, not a ground class

`_stone()` renders every tile with its own lit top edge and shadowed bottom
— a grid of self-shading blocks — in sunlit surface `cliff_color`, with no
transition masks at all (hence the straight cuts) and no distinction between
a wall's face, its top, and where it meets the floor.

**Correction — a wall tile family, edge-aware:**

- Minimum slice: a **stone↔floor transition pair** through the existing
  16-mask system, plus a **footing row** (shadow where wall meets floor —
  the line that sells "carved from rock"), and per-atlas wall color (dark
  wet grey for the mine, from the Priority-2 spec).
- Real fix: **face / top / footing autotiling** — the baker already builds
  TileSets; Godot terrain sets do the edge matching. Per-tile edge lighting
  is removed from the class painter and belongs to boundary tiles only.
  Variation must span tiles (strata, cracks crossing tile borders, seeded
  per wall run) so a wall reads as one mass, not 4 variants repeated.
- The cave-in requirement ("a MASS breaking the wall line") lands here too:
  wall-damage tiles that interrupt the face are the terrain half; boulder
  props overlapping the footing are the prop half.

## Priority 4 — Assets are requested as systems, with per-family prompts

Two distinct genlab defects surfaced:

- **The prompt template is tree-contaminated.** The minecart and timber-frame
  prompts both instruct "canopy mass seen mostly from above", "trunk clearly
  wider than 5 px", "leaf clumps, bark streaks". For a doorway that guidance
  is actively harmful — the weak arches come from here. Correction: the
  family registry gains **per-family PERSPECTIVE and texture language**
  (structure/portal family: "the opening is negative space the player walks
  through, posts read to the ground"; vehicle family: "wheels on a ground
  line"), and portal-scale props get a larger pixel budget than 64×96.
- **Props were requested in isolation.** The cart carries its own baked-in
  "stub of stone track bed" while no track exists in the world — a prop
  answering a question the scene never asked. Correction: the brief's
  register requests **asset systems, not props** — one brief per system:
  *the track system* (rail ground-overlay class from Priority 2: straights,
  corners, end caps; cart re-prompted without the track stub, wheels sized
  to gauge; ore heaps described as spill along the track), *the portal
  family* (timber frame, arch, bricked-off stub), *the pit-head* (shaft
  mouth ring — still missing — winch that straddles it). GenLab's request
  flow already batches; the unit of request just moves up one level.

## Priority 5 — Motion: terrain animates, machines opt out

- **Water frames.** Tile animation exists (tree sway, desynced, QC-gated)
  but only for prop band maps; terrain tiles are single static frames.
  `_water()`'s banding is already sinusoidal — emit 2–3 phase-shifted
  frames per water tile in the atlas and let the baker register them as
  animated tiles (the genlab doc already names "water shimmer" under Later;
  this promotes it). Same seam later gives moss glisten or lava.
- **Per-substyle animation opt-out** (finding F6): cold machines must not
  inherit the family's heat shimmer. `animation` moves from family-level
  to substyle-overridable; "dead" assets in the brief's Motion section map
  to opted-out substyles.

## Priority 6 — Authoring lints & intent hygiene

- **Grid lints at bake time:** no axis-aligned water rectangles (shoreline
  cells must vary by ≥N inflections); flag any class used in an atlas whose
  vocabulary doesn't declare it scene-appropriate (a `bush` in a mine atlas
  stops being possible after Priority 2, but the lint catches the next
  category error).
- **Intent-level decisions are the brief's to defend.** The columns were
  *delivered as asked* — the brief imports the Order's surface architecture
  wholesale. The mine_hall brief gets revised deliberately: either cut the
  free-standing columns or re-describe them as mine architecture the Order
  dressed (engaged into walls, clad roof props). Surface-vocabulary imports
  underground must be argued in "The place", not inherited by default.

## Sequencing (thin slices, each independently shippable)

1. **S1 — brief gate:** skill flow reorder + bake-time brief check +
   verdict blocks. Pure process; no engine code.
2. **S2 — terrain vocabulary:** atlas spec + painter library +
   parameterized transitions + `atlas ensure` gap loop. Highest leverage;
   unblocks S3.
3. **S3 — wall family:** stone↔floor transitions + footing row first;
   autotiled face/top as the follow-up slice.
4. **S4 — asset systems:** per-family prompt templates; track/portal/
   pit-head system briefs; regenerate cart, timber frame, arch, shaft mouth.
5. **S5 — motion:** water tile frames + per-substyle animation opt-out.
6. **S6 — acceptance:** revise the mine_hall brief (columns decision,
   terrain register), regenerate the scene through the new flow, judge the
   snapshot against its acceptance reads. mine_hall is the campaign's proof
   scene: the plan is done when it passes its own brief.

## Status (2026-07-17 — all six slices landed same-day)

- **S1** ✅ brief gate in `13_scene_director.py bake` (`_check_briefs`) +
  skill flow reordered brief-first + verdict-block convention. Legacy
  levels hit the gate on their next re-bake — write their brief then.
- **S2** ✅ `tiles2d.py` is a painter library executing atlas specs
  (committed at `games/<game>/atlases/*.spec.json`); transitions
  parameterized (any base); literal colors; default spec byte-identical
  to pre-spec atlases. Mine vocabulary: earth/wall/water/moss/rail.
- **S3** ✅ `rock` painter (mass, cross-tile strata, no per-tile
  self-shading) + `relief: raised` → footing shadow + lit crest on
  boundary tiles. `stone` untouched (surface blockers keep their look).
- **S4** ✅ per-family prompt anatomy (`texture_motifs`/`anchor`/
  `prompt_notes` in descriptors; generic perspective text); cart
  re-prompted without its track stub; `portal` family added (arch /
  bricked / shaftmouth, 96px). Requests staged; references pending
  (drop → `13 assets ingest`).
- **S5** ✅ water tile animation (tiles/1.2: frames as adjacent columns;
  baker sets frame count + desynced starts) + `static_substyles`
  (cart/winch cold — F6). Named gaps: transition rims static; gearstack/
  boiler shimmer is per-substyle, not per-instance.
- **S6** ✅ mine_hall brief revised (terrain register, nave columns cut,
  Order confined to the shrine), grid rewritten in the mine vocabulary,
  baked through the gate, two snapshot verdict rounds recorded in the
  brief. Open: portal/cart/timber references, pale ore heaps.
