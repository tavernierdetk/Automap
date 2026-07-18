# Exploration — the Entropy recreation campaign

**Status: CAMPAIGN COMPLETE, 2026-07-15 — E0 through E5 built in one day.**
The acceptance question is a command: `PRODUCE=1 tools/ci.sh` in
entropy-remade regenerates every artifact from Automap (publish + bake) and
plays the full game headless — overworld, dialogue with committed effects,
real teleports, ambush, interactive ATB battle, position-restored return,
save/load — exiting 0 with `ENTROPY REPRODUCED: ALL SUITES PASS`.
Commit trail: b2d5043 (E0) → 8ec122e (E1) → 6b8fc09/cddb521 (SCD S1–S4,
which absorbed E2) → 04ce848 (E3a) → e0075eb (E3b) → 001dc86 (E4) →
9a22ab1 (E5). Remaining beyond the campaign: SCD S5 (re-absorb),
StoryDirector (all sockets ready), pixelart-backbone access for new creature
art, licensing review before any distribution.

*(Original plan below, kept for the record.)*
E0: `~/Cowork/entropy-remade` scaffolded + `scripts/12_publish_game.py`
cascade. E1: `level@1.0.0` in platform-specs (sample = the real
witch_cottage transcription); all five locations hand-transcribed to
`games/entropy/levels/` (committed factory sources — coordinates verbatim
from the original .tscn, including the dangling-spawn-tag and orphan-level
quirks, which the publisher warns about); publisher pulls binaries per
`assets.json` and generates per-creature sprite manifests **that the runtime
actually reads**; the game's generic `Location` scene builds any level from
JSON (one scene replaces five hand-built ones), faithful player shell,
teleports target level ids. Proof: 14-assertion headless suite ALL PASS +
witch_cottage rendered with zo and Carmilla at original coordinates. The platform's own acceptance test, made real: *"can Entropy
be produced from the platform"* (platform brief §10 rule 3). We recreate the
game **2D-faithful** — engine, levels, creatures — as a **new Godot project
generated from Automap**, with regeneration cascading into it. Every missing
platform component this needs (text-prompt level intake, 2D runtime target,
dialogue/combat modules, the external-game publish seam) gets built *because*
this needs it.

Reference repos (cloned 2026-07-15, read-only ground truth):
- `~/Cowork/entropy-integrated` — the game (Godot 4.4, 2 commits, no LICENSE)
- `~/Cowork/EntropySnapShot` — the Python combat sim (ATB + statuses reference)
- `pixelart-backbone` (ULPC sprite compositor) — **not accessible** (manifests
  point to a machine path that doesn't exist here; repo not public). Vendored
  sprites cover the existing creatures; new creature art is gated on this.

## Ground truth (from the 2026-07-15 code surveys)

**The reframe that shapes everything: Entropy has no tilemaps.** A location is
one painted 1024×1024 background `Sprite2D` + hand-placed collision rectangles
+ `SceneSpawn` markers + `TeleportArea2D` exits (+ optional NPC with a dialogue
rig). Characters are 64×64 ULPC pixel sprites (walk cycles, 4 directions,
loaded by directory convention). Two art registers, deliberately contrasted:
painted world, pixel people.

Scope is tractable: **5 working locations** (ecole, castle_outside,
forest_buit, witch_cottage, witch_cottage_inside; 7 painted BGs, 2 unused),
**8 creatures** (3 ULPC overworld + 5 painted battle), **1 authored
conversation** (Carmilla, 4 nodes), **0 quests**, 5 faction crests, 2 battle
terrains. The engine is the real substance:

- **Buses**: `CombatBus`, `DialogueBus` (+ `RNG`, `Game`, `PartyState`
  autoloads); await-driven controllers. `CombatRouter` is *expected* as an
  autoload but never registered — a live bug.
- **Dialogue**: script = `Array[Dictionary]` (`id, speaker_id, text,
  choices[].{label,next_node,effects}, effects[], visual_skin, end_session`);
  effects vocabulary `flag | var_delta | memory`. Scripts are **hardcoded** in
  per-NPC `_build_script()`; condition-eval and memory-commit are **stubs**.
- **Blackboard**: `WorldState` (flags/vars/factions/places/events),
  `Persona` (relations/memories), `NPCMemory`, `Faction`, `Place`, `Event` —
  sound resource shapes, under-wired.
- **Combat**: `CombatEnvelope → CombatRouter → CombatResult` handoff (result
  never actually populated); **round-robin** turns despite `spd/acdb` on
  Creature (the sim's ATB was lost); damage `= atk.kinesthetic*6 −
  def.kinesthetic, min 1, ×skew-RNG, ×2 overexert`; organic/lithic statuses
  threshold-gated with purge decay; target modes 0–6.
- **Creature** (Resource): the 5 stats (defaults 10), derived `hp = kin*10 +
  terrain*5`, `spd = 50 + kin*3`, thresholds/purge from kin; chaos_dials
  (sigma_v0/alpha/clip); XP flat 100/level (+1 kin, +1 terrain per level);
  `user://saves/party_members/` persistence; lucidity + creature_affinity
  currently inert.
- **RNG.gd**: SHA-seeded named streams, Azzalini skew-normal with per-stream
  Box–Muller spare cache, winsor/truncate/soft clipping — already GDScript,
  reproduce exactly for parity.
- **Sprite loading**: two directory-scan conventions (overworld
  `Assets/Creatures/<slug>/ulpc_frames/<Anim>/*.png`; battle
  `CharacterVisual.animations_root`). The JSON spec chain
  (`char_def_lite → intermediary → ulpc.build → manifest`) ships beside the
  sprites but is **inert at runtime** — the exact failure platform-specs
  exists to prevent.
- **Known rot** (fix-by-spec, not by patch): broken `.tres` paths (zo, Caden),
  `terrain_key="Field"` unloadable (file naming), dead `CombatScreen.gd`,
  no main scene, commented-out confusion/berserk targeting.

## Architecture decisions

1. **`entropy-remade` is a sibling Godot project** (`~/Cowork/entropy-remade`,
   own git) — the constellation's reference consumer. **Nothing in it is
   hand-wired**: engine scripts are code, but every piece of *content* (level,
   creature, dialogue, encounter) arrives as a spec-validated artifact
   published from Automap. Re-running generation **cascades**: Automap builds
   → publishes into the game folder → the game plays it. One-way dependency,
   per the constellation rule.
2. **Four new specs in platform-specs** (the campaign's founding act, E1/E2):
   - `level@1.0.0` — the scene-graph a location IS: background ref (+size),
     collision rects, spawns (tagged), teleports (target level + tag),
     npc placements (slug + dialogue ref), encounter regions (envelope ref).
     Consumed by a **level loader** in the game (one generic Location.tscn
     builds itself from JSON — replaces 5 hand-built scenes).
   - `dialogue-script@1.0.0` — the long-queued extraction of entropy's
     de-facto format (id/speaker/text/choices/effects + a real `when`
     condition clause). Consumed by a data-driven DialogueRunner (kills
     `_build_script()`), and eventually shared with Automap's 3D dialogue.
   - `creature@1.0.0` — unifies `char_def_lite` + `Creature.tres`: identity/
     personality prose + the 5 stats + chaos_dials + skills + visual manifest.
     Projected to `.tres` by the pipeline (stage-10 pattern); admission gate
     runs the autosim.
   - `combat-envelope@1.0.0` — terrain key, enemy refs, seed, trigger kind,
     reward dials (the envelope Resource, as data).
3. **Level generation = scene-graph + background provider.** The text-prompt
   intake (E2) fills `level@1` (layout, exits, npcs — LLM proposes, schema
   validates, graph checks reciprocal teleports). The background image comes
   from a **provider tier**: (a) the existing 7-BG library, selected by
   prompt/identity match — enough to recreate every current level and author
   new ones from stock; (b) a diffusion backend (genserver) later — the same
   slot, nothing downstream changes (the facades.py seam philosophy).
   **2D visual identity** = a new identity flavor: BG library + palette/mood
   descriptors + the ULPC wardrobe constraints (soft-fantasy register).
4. **Engine: rebuild data-driven, fidelity to the *intent*.** Decisions where
   the code and the design disagree:
   | Point | Original code | We build |
   |---|---|---|
   | Turn order | round-robin | **ATB restored** from EntropySnapShot (spd/acdb finally used); formulas data-driven, current damage formula as default |
   | Dialogue conditions | stubbed | implemented (`when` clauses over WorldState flags/vars/relations) |
   | Memory commit | commented out | implemented (persona.remember) |
   | CombatRouter | missing autoload | autoloaded |
   | CombatResult | never populated | populated (it's the mechanics↔world contract) |
   | Sprite loading | directory scan, inert manifests | **manifest-driven loader** (the manifests finally get read) |
   | Field terrain | unloadable | fixed by convention in the spec |
5. **Determinism end-to-end**: RNG.gd reproduced exactly (named streams,
   spare-cache skew-normal); levels/creatures deterministic per spec; the
   headless proof (E5) replays a full loop on a fixed seed.
6. **Licensing flag**: entropy-integrated has no LICENSE; ULPC assets are
   CC-BY-SA/GPLv3 territory. Fine for this personal recreation; revisit
   before any distribution. pixelart-backbone access needed for new creature
   sprites — flagged, not blocking.

## The slices

- **E0 — this doc + scaffold + cascade seam.** `entropy-remade` project
  skeleton (autoloads registered, main scene, empty content dirs), and
  `scripts/12_publish_game.py` in Automap: copies validated artifacts
  (levels/creatures/dialogues/BGs) into the game's `content/` tree — the
  cascade. Proof: a placeholder level publishes and opens.
- **E1 — 2D runtime foundation.** The generic level loader (level@1 →
  built Location at runtime), overworld shell rebuilt (8-dir player, party
  chain, spawn/teleport contract — faithful), manifest-driven sprites,
  headless test harness from day one (Automap's test_game_integration
  pattern). Proof: witch_cottage recreated *as data* plays identically.
- **E2 — text-prompt level intake.** `/create-level` skill (interview or
  one-shot prompt) → level@1 + dialogue refs + BG pick, validated + published.
  The ingest-media seed. Proof: a brand-new location authored by prompt,
  connected to the existing map, walkable.
- **E3 — engine modules.** Dialogue runner with conditions/effects/memory;
  WorldState/Persona wiring; ATB combat with envelope/result populated;
  creature admission gate (autosim) + .tres projection. Proof: Carmilla
  conversation runs from data; a seeded battle replays deterministically.
- **E4 — full content recreation.** All 5 locations + 8 creatures + the
  Carmilla script re-authored as specs through the intake; original repo
  becomes pure reference. Proof: side-by-side parity walk.
- **E5 — playable loop parity + CI.** Boot scene, overworld → dialogue →
  encounter → combat → return, save/persistence; one headless run plays the
  loop and exits 0. "Can Entropy be produced from the platform" is now a
  command.

Cross-links: [platform brief](2026-07-08-platform-architecture.md) §§8–11,
[sophisticated-characters](sophisticated-characters.md) (C1 state ≈ WorldState
convergence), [character-runtime-stack](character-runtime-stack.md) (the 3D
twin of the creature/asset questions).
