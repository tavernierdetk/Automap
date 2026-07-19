# Exploration — alignment pass vs. the "AI-Native 2D RPG Maker" proposal

**Status: analysis, 2026-07-15.** A second LLM drafted a full authoring-platform
architecture without seeing this project. This doc is the adopt / reject /
defer verdict against our model, and the concrete changes it produced. The
headline: **its central principle is ours, independently derived** — which is
strong evidence the architecture is right — while its *delivery model*
(Godot-editor-centric, big-bang module taxonomy, Resources as the data model)
contradicts what makes our platform work.

## Where it independently confirms us

| Proposal | Ours (already built/decided) |
|---|---|
| "Three forms: intent / structured data / runtime" (§19) | prompt → spec (level@2, character-profile) → baked .tscn/.tres — our exact pipeline shape |
| "AI proposes structured artifacts; Godot is runtime + visual editor" | the LLM-boundary rule + the SCD baker; word for word our model |
| Scene Planner / Creator / Director split (§4.3–4.5) | conflated inside SceneCreationDirector: spec-filling = planner, baker = creator, the snapshot-critique loop = director-as-judge |
| Locking & sub-artifact ownership (§10.5) | manual provenance in the fusion engine — ours is per-ATTRIBUTE, finer than their artifact locks; validates the S5 re-absorb design |
| Balance Simulator + Automated Playtester (§9.4–9.5) | autosim admission gate + headless integration tests that play quests to completion (deterministic = their "replayable traces") |
| Project Identity Profile (§2.3) | visual-identity@2.3 — ours is versioned + schema'd; theirs is broader in scope (see adoptions) |
| Semantic Scene layer (§4.7) | npc_slots / spawns / teleports / zones — the StoryDirector sockets |
| Story Director, Character Creator, reuse-before-generate | same names, same rules, already in our docs/skills |

## Adopted (concrete changes)

1. **Game Design Model as a file — adopted NOW, reshaping E3.** The brief's
   "gspec box" finally earns its schema: `game-design@1.0.0` — player verbs,
   combat model (turn scheme, damage formulas, status rules **as data**),
   difficulty envelope (graduating `balance.Envelope` as long promised),
   progression. E3's combat module reads its rules from this document instead
   of hardcoding formulas — the proposal's best idea landing exactly where we
   had a placeholder.
2. **The Director / Creator / Editor / Validator taxonomy (§14)** — adopted as
   naming convention for future modules (we were already accidentally
   compliant). The Planner/Creator/Director lifecycle is now documented as
   SCD's internal shape rather than three modules.
3. **`intent` field on specs (§19)** — an optional human-readable purpose
   sentence on levels/creatures/quests ("a dangerous harbour alley suitable
   for an ambush"). Cheap, and it's the continuity anchor every later
   LLM pass wants. Enters each schema at its next additive bump.
4. **Asset Adapter (§3.3)** — recolor/palette-match existing assets instead of
   generating: a real gap, cheap with PIL + the quantizer pattern from the
   PixelAssetCreator ledger. Queued as an SCD tool (`13_scene_director.py
   adapt`) when a use case lands.
5. **Operating modes affect permissions, not prompts (§12)** — adopted as a
   skill-authoring rule: each skill states which files the flow may touch
   (create-scene already does implicitly; future skills make it explicit).
6. **Uniform lifecycle (§13)** — inspect → propose → generate → validate →
   explain → apply is already the skill shape (catalog → fill → bake →
   snapshot); adopted as the checklist for writing new director skills.
7. **Narrative Validator (§9.3)** — quest-graph reachability checks, adopted
   into the E3+ plan (the teleport-graph gate generalized to story graphs).

## Rejected (conflicts with what works)

1. **Godot-editor-centric authoring (custom docks/workspaces/plugin
   framework, §15, Foundation F).** Our authoring surface is the session +
   staged CLIs; Godot is the runtime and the *touch-up* surface (baked
   scenes). An editor-plugin platform is an enormous parallel UI investment
   that duplicates what specs + snapshots + re-absorb already deliver, and it
   couples authoring to one engine.
2. **Custom Godot `Resource` classes as the core data model (§11).** Directly
   contradicts the engine/pipeline decoupling: our contracts are engine-
   agnostic JSON Schemas; `.tres`/scenes are *projections*. Entropy-integrated
   itself is the cautionary tale (inert specs, path rot) — and its fix was
   schemas outside the engine, not more Resources inside it.
3. **The 60-module canonical map as a build plan (§20).** Taxonomy before
   need. Our rule stands: a module earns existence when it has an owner, a
   spec boundary, and a consumer. The list is kept as a *vocabulary ledger*,
   not a roadmap.
4. **Registry-as-database with approval workflows (§2.4, §10.3).** Git +
   publish manifests + per-attribute provenance already provide identity,
   history, and reviewability in text. A proposal/approval UI layer is a
   product decision for a multi-user future, not platform substance now.
5. **Capability/permission registry (§8.6).** The harness's own permission
   model + file-boundary conventions + schema gates are the working
   equivalent; an in-platform ACL system is premature abstraction.

## Deferred (right idea, no consumer yet)

Audio domain (music director, ambient), localization, economy/crafting
editors, cutscene timeline, visual logic graphs, dependency explorer (a light
`deps` subcommand on the catalog can come cheap when deletion/regeneration
needs it), visual regression testing (the snapshot harness is its seed),
terrain sets/animated tiles in the TileSet baker, NavigationRegion2D tooling.

## Net effect on the campaign

E3 proceeds **reshaped**: combat/dialogue rules become data under
`game-design@1.0.0` (adoption #1), dialogue scripts get `intent`-ready
schemas, and the module naming follows the taxonomy. Everything else about
the campaign (E3 engine modules → E4 content fidelity → E5 loop parity, then
SCD S5 and StoryDirector) stands as planned — the proposal's development
sequence (§18) independently matches it, which is the second confirmation
worth recording.
