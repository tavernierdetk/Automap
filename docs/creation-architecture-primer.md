# Primer — the creation architecture (2026-07-17)

The system's shape after the scene-generation correction plan
(docs/explorations/scene-generation-correction-plan.md, S1–S6) and the
genlab quality campaign (docs/explorations/genlab-quality-campaign.md,
rounds 1–3), both landed today. Companion docs:
`scene-generation-primer.md` (operational how-to) and
`vaporis-pipeline-primer.md` (how the Lyceum was actually built) — both
predate today's changes; where they disagree with this document, this one
is current.

## The shape at a glance

```
                      INTENT                          (human + director)
                        │
              scene brief (<id>.brief.md)      ← REQUIRED upstream; gated
                        │
        ┌───────────────┼────────────────────┐
        ▼               ▼                    ▼
   visual identity   terrain register    asset register
   (identities/*.json│(atlas spec:       (FAMILIES request:
    colors+materials)│ classes/colors/    family/substyle/size)
        │            │ transitions)           │
        │            ▼                        ▼
        │       tiles2d painters      ┌── procedural (trees_px)
        └──────► atlas + tiles.json   └── genlab: prompt → ImageGen →
                     │                     preview (HITL) → repixel →
                     │                        ┌───────────┘
                     ▼                        ▼
                mechanics flags        asset_qc — THE one gate
                     │                        │
                     ▼                        ▼
              level@2 document ◄──── props catalog (props.json)
                     │
          publish (stage 12) gates → headless Godot baker
                     │
              editor-editable .tscn  → snapshot → verdicts, appended
                                        to the brief (the loop closes)
```

Two repos: Automap holds specs, generators, staging (`work/`, gitignored);
the game repo (e.g. ~/Cowork/entropy-remade) holds published `content/`
(never hand-edited) and the baker tool.

Content layout (who owns what — organized 2026-07-18):
- `content/levels|backgrounds|creatures|props|tilesets/…` — PUBLISHER-owned:
  wiped and rewritten by every stage-12 publish (tilesets = atlas PNGs +
  tiles.json).
- `content/scenes/*.tscn` — BAKER-owned, never wiped: one baked scene per
  level id (`Game.change_level` resolves here).
- `content/scenes/tilesets/*.tileset.tres` — BAKER-owned TileSet resources,
  shared across scenes. They live under scenes/ (not content/tilesets/)
  because the publisher wipes content/tilesets on every publish — baked
  resources must not sit in publisher-owned dirs.

NPC population is deliberately NOT here — scenes ship as empty stages
with `npc_slots`; that's the StoryDirector seam.

## Principle 0 — intent before pixels

A scene is generated FROM a brief, never before one. Every scene owns
a folder — `games/<game>/levels/<id>/` holds `<id>.json` (spec) and
`<id>.brief.md` (intent), organized 2026-07-18. The brief carries the place, the ordered
reads, light & air, zones, the REGISTER (terrain classes + assets, reused
vs to-create, scoped as SYSTEMS — a track, not a cart), motion
(dead vs alive), and acceptance reads written before pixels.
`13_scene_director.py bake` errors without it (`_check_briefs`).
Snapshot verdicts append to the brief per run — judgment accumulates in
the artifact, not in memory.

## Principle 1 — vocabulary agency

When the brief names a surface or asset the catalog lacks, generating it
is the DEFAULT action. Nothing is contorted into meaning something else
(grass is not moss; a bush is not fungus). Generation is deterministic
and cheap; the catalog dedupes; volume is the point.

## Layer 1 — the style contract

- `identities/<name>.json` (`visual-identity@2.4`): terrain colors +
  `materials` block (bronze, verdigris, flame…).
- `pixelart.master_palette()` derives THE palette: per material a 5-band
  ramp + hued outline dark + neutrals. Everything downstream is
  palette-member by construction.

## Layer 2 — terrain (tiles2d: a painter library executing specs)

- An atlas is authored as a SPEC, committed at
  `games/<game>/atlases/<name>.spec.json`: classes
  `{name, painter, color, mechanics flags, args, on, relief, animation}`
  + transition pairs whose `base` is whatever the scene's floor is.
  Colors may be literal RGB — an underground atlas owes nothing to the
  surface identity fields. No spec = DEFAULT_SPEC (the surface five,
  byte-identical to pre-spec atlases).
- Painters: grass, path, water, stone (free-standing blocker,
  self-shading), rock (MASS — cross-tile strata, no per-tile lighting),
  earth, moss; overlay painters clump (on an underlay) and rail
  (oriented). Every pixel derives from sha256(identity, class, variant) —
  re-runs byte-identical.
- Boundaries: 16-mask dual-grid transitions; `relief: "raised"` grows a
  footing shadow + lit crest where a mass meets the floor (what sells
  "carved").
- Motion: `animation: {frames: N}` packs phase-shifted frames as adjacent
  columns (tiles/1.2); the baker sets Godot tile animation, desynced.
  Known gap: transition rim tiles stay static.
- Mechanics flags (walkable/speed_mod/hazard) ride tiles.json → TileSet
  physics + custom data. Collision EMERGES from the atlas, never authored
  per scene.

## Layer 3 — assets (two backends, one gate)

`asset_creator.FAMILIES` is the registry: per family a generator,
substyles, style tokens, allowed materials, per-size canvases, an
`animation` contract (which materials MAY move; `static_substyles` says
whether THIS subject is the kind of thing that does — a cart is dead
metal), and the DESCRIPTOR: blocking concept, perspective, per-family
prompt anatomy (`texture_motifs`, `anchor`, substyle-keyed
`prompt_notes`, `lighting`). `asset_qc.resolve_descriptor` resolves
dict-valued keys per substyle.

**Procedural backend** (trees_px): paints (material, band) index maps
from scratch. **GenLab backend**: recreates them from an image-model
reference —

1. `compose_prompt` — deterministic, palette-exact, family-anatomy-true
   (tree language leaking into a doorway prompt was the arch failure;
   never hardcode anatomy in the shared scaffold).
2. ImageGen box (swappable, like ODM): `drop` mode (human fills
   `incoming/`) or `api` mode (`13 assets generate`; gpt-image-1, key at
   `~/.automap/imagegen.json`, canvas matched to sprite aspect,
   generation.json archived). Either way PNGs land in `incoming/` and
   downstream neither knows nor cares.
3. `preview` (`13 assets preview`) — the human-in-the-loop seam: dry-run
   recreation + QC into a side-by-side sheet (reference | sprite |
   verdict), staging NOTHING. Judge, cull, regenerate, re-preview; only
   then ingest.
4. `repixel` — the recreation. Round-2 state: subject mask (alpha or
   keyed background) → DOMINANT-color reduce (mode per cell — hard edges
   survive; a mean blends detail into off-palette mush) → hue-weighted
   palettize (L×0.55: a material is a chroma family) → majority-vote
   material smoothing → reband ANCHORED to the observed band range (no
   invented near-white extremes) → sel-out outline → dithered shadow.
   Index maps out; animation substrate identical to the procedural path.
5. `asset_qc.run_qc` — THE gate both backends share: crisp alpha,
   palette membership, single mass, outline, light direction (judged
   within the DOMINANT material; `lighting: ground_plane` opts out
   radially-lit ground features), band balance, grid alignment, blocking
   footprint (same 7-row window as the measure). Set-level: variant
   distinctness (silhouette IoU), interior contrast.
6. Catalog (`props.json`): family/substyle/style/provenance/frames/
   anchor/footprint per asset. Hash guard on publish — hand-edited
   sprites are never overwritten; touch-ups flip provenance to
   `manual`, which always "fits". Recipes
   (`games/<game>/asset_requests.json`) regenerate everything from text;
   replay skips recipes whose gitignored references are gone.

Quality is empirical, not aspirational: the campaign runs image →
recreation across asset types, reads preview sheets per stage, and each
finding lands in a named layer (PROMPT / REPIXEL / QC / SIZE) before the
next round re-tests on the SAME references. As of round 3, recreation
quality is bounded by the reference, not the pipeline.

## Layer 4 — scenes (SceneCreationDirector)

Brief → register audit against `13 catalog` → generate gaps (Layers 2–3)
→ fill `level@2.2` (`games/<game>/levels/<id>.json`): palette-mapped
ground rows (think silhouettes; water is never an axis-aligned
rectangle), props placed by FOOT position (y-sorted, blocking only at
footprint; `deco_` never collides in the 3D pipeline, prop footprints
carry it here), spawns/teleports (reciprocity is on you — the publisher
errors on unknown targets), generous `npc_slots`. Then
`13 bake <id>`: brief gate → stage 12 (schema validation + teleport
graph + hash-guarded publish + per-family tileset packing) → headless
Godot baker (TileMapLayers + dual-grid blend layers + physics from
flags + animated tiles + prop layers + markers) → snapshot → verdicts
into the brief.

## The gates, in firing order

| gate | where | catches |
|---|---|---|
| brief gate | 13 bake | scenes generated before intent (F8) |
| schema validation | stage 12 / platform-specs | malformed level/identity/tiles docs |
| teleport graph | stage 12 | dangling exits (error), orphan spawns (warn) |
| intent QC | genlab (stub) | reference ≠ request (future VLM) |
| preview (human) | 13 assets preview | weak references, before anything commits |
| asset QC | ingest + ensure | palette/silhouette/light/footprint defects |
| set distinctness | qc_set | near-clone variants |
| anim frame QC | attach_frames | silhouette drift, over-large frame deltas |
| hash guard | stage 12 publish | overwriting hand-edits |
| snapshot verdicts (human) | brief | does the map READ |

## Known seams (named, deliberate)

- **StoryDirector**: npc_slots/markers are its sockets; population never
  happens here.
- **Pass-through blocking**: portal props block their base SPAN — an
  arch cannot straddle a walkway yet (kept out of scenes until a
  two-footprint or jamb-only blocking mode lands).
- **Per-instance motion**: dead-vs-alive is per-substyle; a scene cannot
  yet cool one boiler while the lyceum's twin runs hot.
- **Transition rim animation**: animated water's shore tiles are static.
- **Re-absorb slice (S5 of the SCD plan)**: editor edits to baked scenes
  die on re-bake, loudly, until deltas re-absorb into the spec as
  `manual` provenance.
- **IntentQC**: interface + provenance slot exist; the VLM judge does not.
- **Providers**: one (gpt-image-1); the config field is the seam.
