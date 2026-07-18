# Exploration — SceneCreationDirector (the 2D scene creator module)

**Status: design locked 2026-07-15; S1–S3 built same day** (level@2.0.0 +
entropy identity; automap/tiles2d.py atlas generator, 4 tests; the Godot
baker + 12-assertion proof incl. pixel-exact water blocking — entropy-remade
commit 6b8fc09; the meadow_test scene is the worked example). **S4 built
same day**: `scripts/13_scene_director.py` (catalog with palette signatures
+ level graph / atlas / bake subcommands — bake reimports between publish
and bake, the baker hard-fails on unimported atlases), the `/create-scene`
skill, and the first director-authored scene: **lakeshore** (prompt → reuse
decision → grid → reciprocal graph edit in meadow_test → bake → snapshot;
entropy-remade cddb521). **Layered scenes shipped 2026-07-16
(level@2.2)**: parallax backdrop layers, `automap/props2d.py` (identity-driven
RGBA prop sprites with foot anchors + footprint-only collision), the baker's
y-sorted World container (player/NPCs/props sort together; the front/behind
flip lands exactly at the foot line via a 44px center-to-feet bias), proven on
forest_glade — a path through a forest where the player visibly passes in
front of north-side trees and behind south-side canopies, trunks blocking at
pixel-predicted geometry. **Asset Creator shipped 2026-07-16**
(plan: ~/.claude/plans/rustling-zooming-meteor.md): `automap/pixelart.py`
(ONE identity master palette — named hue-shifted material ramps, ~34 colors,
published as content/palette/ for color-picking; morphology, clump stamps,
sel-out outlines, silhouette IoU), `automap/trees_px.py` (deciduous/pine/dead
through one indexed-painting renderer; stratified variants gated on validity
THEN distinctness — a broken sprite is maximally "distinct", so validity must
come first), `automap/asset_creator.py` (variety-aware resolver: N distinct
variants of the right style fit, hand-edited assets count, legacy blobs
don't; generates only the gap; recipes in games/<game>/asset_requests.json
replayed by CI), and hash-guarded publishing (a file differing from its
last-published hash was touched up — preserved, provenance manual). Godot
default texture filter set to Nearest. **Automated Asset QC shipped
2026-07-16** (`automap/asset_qc.py`): family-agnostic craft checks (crisp
alpha, palette membership, single mass, outline, LIGHT DIRECTION — highlight
centroid must sit up-left of shadow centroid, band balance, grid alignment)
plus family-DESCRIPTOR checks: each FAMILIES entry declares its conceptual
contract, notably `blocking` — a tree blocks at its trunk_base, measured
from actual trunk pixels and verified against the sprite (center on the
mass, radius within the trunk, canopy zone clear). QC runs inside ensure()
and as `13 assets qc`; iteration is machine-checked (the harness caught
bottom-lit dead trees on its first run — two fix cycles, zero image reads).
The baker consumes the measured footprint, and the baked-scene suite asserts
the semantics behaviorally: walking through canopy passes, the trunk blocks.
**S5 (re-absorb) is the remaining slice; then StoryDirector as its own
module.** Supersedes the
plain "text-prompt level intake" (E2 of the [entropy
campaign](entropy-recreation.md)) with a full module: a director that creates
*scenes* for a 2D game (Entropy-class) using every tool the platform can give
it — the project's existing assets, generated assets parameterized by the
visual identity and the game mechanics, textures and tilemaps used or
generated, and layered scene assembly. Its output is **hand-editable in the
Godot editor** and leaves explicit seams for a future **StoryDirector**
(NPCs, scene control, quests) to populate.

## The tension this module resolves

E1 made levels pure data ("content/ is never hand-edited") — right for
fidelity recreation, wrong for authoring: a creator wants to nudge a tree in
the editor. The resolution is the platform's own manual-provenance pattern
(features.json): the **spec is the source of truth, the .tscn is a baked
projection** — generated, then freely editable. Slice S5 closes the loop by
re-absorbing editor deltas into the spec with `provenance: "manual"`, so
regeneration preserves them; until then, a re-bake overwrites (loudly).

## The director's tool suite

```
                        SceneCreationDirector (LLM-facing, fills specs)
                        │
  ┌─────────────────────┼──────────────────────┬─────────────────────┐
  ▼                     ▼                      ▼                     ▼
asset catalog      asset generation       tile/texture tools    scene assembly
(scan the game     (visual identity +     (use existing atlas   (level@2 doc →
project: BGs,      mechanics as params:   or generate one:      layers, markers,
sprites, atlases,  procedural tiles now,  automap/tiles2d.py;   nav/collision →
palettes, sizes)   diffusion via          TileSet baked with    baked .tscn via
                   genserver later)       physics/nav/custom    headless Godot)
                                          data from mechanics)
```

- **Asset catalog** — inventory of a target project's usable assets
  (backgrounds with palette signature, creature sprite sets, tile atlases),
  so the director *reuses before it generates*.
- **Asset generation, identity+mechanics-parameterized** — the two contracts
  every generated asset must answer to: the visual identity (colors, mood —
  the same `visual-identity@2.3` file the 3D pipeline uses; its terrain
  colors drive tile tinting) and the game mechanics (walkability, speed
  modifiers, hazard flags — baked into the TileSet as physics + custom data
  so the runtime and future mechanics module read them, never re-derive).
  v1 backend is procedural (the facades.py texture engine's 2D sibling);
  a diffusion backend slots behind the same seam later (genserver).
- **Tilemaps** — new to the Entropy world (the original had none): scenes can
  be `kind: "tilemap"` (grid-composed from an atlas, layered) or
  `kind: "backdrop"` (the E1 painted-background shape). Both are level@2.
- **Scene assembly** — layers with distinct jobs: `ground` (base tiles),
  `decor` (overlay tiles, no physics), collision (emerges from tile mechanics
  flags — blockers carry physics polygons in the TileSet), `navigation`
  (reserved: NavigationRegion2D arrives with StoryDirector-era NPC pathing),
  and **markers**: spawns, teleports, and `npc_slots` — named anchor points
  with tags, deliberately empty. Markers are the StoryDirector seam.

## Contracts

- **`level@2.0.0`** (additive over 1.0.0): `kind` (backdrop | tilemap),
  `tilemap` block (atlas ref, tile size, per-layer cell grids as compact
  rows of tile-class ids), `npc_slots` (named, tagged anchor points),
  `nav` reserved. Backdrop levels remain valid 1.0.0 documents.
- **`tiles.json`** (beside each generated atlas): tile classes → atlas
  coords + mechanics flags `{walkable, speed_mod, hazard}`. Consumed by the
  TileSet baker; the mechanics module reads the same flags at runtime via
  TileSet custom data.
- **The baked scene** (`content/scenes/<id>.tscn`): root script keeps the
  Location contract (spawn tags, level id), children are real editor nodes —
  TileMapLayer(s) with a real TileSet resource, SceneSpawn / TeleportArea
  markers, an OverworldPlayer. `Game.change_level` prefers a baked scene
  over the JSON build, so edited scenes win automatically.

## Why bake inside Godot (not a Python .tscn writer)

TileMapLayer cell data and TileSet physics serialize in engine-internal
formats; reverse-engineering them is fragile. The baker is a **headless Godot
tool script inside the game project** — the pipeline invokes it like stage 7
invokes the importer. Python stays the director/spec side; Godot owns Godot
serialization. (Same division as stage 7's publish/import split.)

## StoryDirector (future module — seams only, for now)

Gets: the baked scene's markers (`npc_slots` by tag, zones, teleport graph),
the creature roster, the dialogue-script schema (E3), WorldState. Does:
casting NPCs into slots, attaching dialogue/quests, scene control (locks,
time-of-day, triggered changes). The SceneCreationDirector deliberately stops
at *empty stages with labeled sockets* — population is a different director
with different inputs (story state, not identity/mechanics).

## Slices

- **S1** — this doc + `level@2.0.0` + `identities/entropy.json` (the game's
  soft-fantasy identity as a file; the same contract the 3D pipeline speaks).
- **S2** — `automap/tiles2d.py`: procedural tile atlas (ground/path/blocker/
  water classes, identity-tinted, deterministic) + tiles.json mechanics flags.
- **S3** — the Godot baker (`tools/bake_scene.gd` in entropy-remade):
  level@2 tilemap doc + atlas → editable .tscn with layers, TileSet physics
  on blockers, markers; `change_level` prefers baked scenes. Proof: a
  generated meadow scene opens in the editor, is playable, and a hand-moved
  node survives replay (pre-reabsorb: survives until next bake).
- **S4** — director orchestration: asset catalog scan, the generate-or-reuse
  decision flow, `/create-scene` surface (prompt → level@2 + assets → bake),
  teleport-graph integration with existing levels.
- **S5** — roundtrip re-absorb: .tscn deltas → spec with `"manual"`
  provenance (the fusion-engine pattern), making editor edits regeneration-
  proof. StoryDirector begins as its own exploration after S4.
