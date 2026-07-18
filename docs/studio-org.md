# The studio org — every chair needed to make a game

Committed 2026-07-18 (R1 of the studio refactor). The visual companion
(org chart + this ledger rendered) is the studio-org artifact; this file
is the source of truth. Phases R1–R4 at the bottom track what is real.

## The design rule (the house type, applied to roles)

A role is four things, always the same four:

1. **One owned committed document type** — the role's output IS a file
   in git, nothing else.
2. **A skill as the human's door** — the human sits in any chair by
   invoking its skill; editing the owned artifact directly is also
   doing the job (provenance-marked, never gate-exempt).
3. **Gates on its outputs** — schema validation, QC, canon, balance;
   a gate applies to the human in the chair exactly as to the agent.
4. **A library it consults before creating** — reuse is audited before
   generation, every time, in every chair.

Roles communicate ONLY by writing artifacts the next role reads. No
side-channels: if an interaction isn't a row in the ledger below, it
doesn't exist.

## The hierarchy

```
Game Director
├── Story Director ──── Lore Keeper (canon gate)
│        ⇅
│   Casting Director
│   ├── PC branch  (existing character-admission pipeline — other session's lane)
│   └── NPC Director ── NPC Creator (balance gate, character library)
├── World Director  (commissions scenes; graph-as-intent)
│   └── Scene Director
│        └── Asset Director ── Asset Creator (asset QC gate, asset library)
├── Systems Director (balance targets, mechanics flags)
└── Audio Director  (named seam only)

Casting ⇄ Scene handshake: the populate doc (game@) fills a baked
scene's npc_slots — casting and scene-making run in parallel and meet
at the sockets.
```

## Charters

| Role | Status | Owned document | Skill door | Gate on output | Library consulted |
|---|---|---|---|---|---|
| **Game Director** | new (R4) | `games/<g>/game.md` — pitch, pillars, scope, commissions | `/game-director` (R4) | pillars review (human) | world + story + systems docs |
| **Story Director** | seam (R2) | `games/<g>/story/` — arcs, beats, quests, dialogue commissions | `/story-director` (R2) | Lore Keeper canon gate; dialogue-script@ schema | lore bible, cast book |
| **Lore Keeper** | new (R2) | `games/<g>/lore/` — canon bible (places, names, history, tone) | `/lore-keeper` (R2) | consistency review on canon edits | existing briefs (canon seeds) |
| **Casting Director** | new (R3) | `games/<g>/cast/cast-book.md` — roster of who exists | `/casting-director` (R3) | cast book review vs story needs | character library, lore bible |
| **PC branch** | built (other lane) | `godot/characters/<slug>.json` → `.tres` | `/create-character` | schema + autosim balance harness | — (consumed via artifacts only) |
| **NPC Director** | new (R3) | per-scene casting sheet — which archetypes → which npc_slots | `/npc-director` (R3) | slots exist in baked scene; roles covered | cast book, scene brief |
| **NPC Creator** | partial (R3) | NPC profiles + sprites + stats | via NPC Director | balance gate (same harness); creature@ schema | character library (`13 library` sibling) |
| **World Director** | new (R4, wearable by Game Director) | `games/<g>/world.md` — regions, roster, graph-as-intent | `/world-director` (R4) | teleport-graph gate (publisher) | level graph, region briefs |
| **Scene Director** | built | `games/<g>/levels/<region>/<id>/` — brief + level doc | `/create-scene` | brief gate, level@ schema, teleport gate, acceptance reads | THE LIBRARY, atlases, concepts |
| **Asset Director** | partial → R1 | the brief's **Register** section + `library.md` custody | `/asset-director` (R1) | doctrine custody + preview cull before ingest | `games/<g>/library.md` + contact sheets |
| **Asset Creator** | built | staged variants under `work/game/<g>/` → catalog | via Asset Director (`13 assets …`) | asset QC (`run_qc`): palette, outline, light, footprint, distinctness | family registry, archived references |
| **Systems Director** | partial (R4) | balance targets + mechanics flags doc | `/systems-director` (R4) | autosim harness thresholds | balance runs |
| **Audio Director** | seam only | — | — | — | — |

## The interaction ledger

Every edge in the org, its artifact, and its gate. Load-bearing rows
are marked ★ — they are where quality is actually enforced.

| # | From → To | Artifact exchanged | Gate |
|---|---|---|---|
| 1 | Human → any chair | skill invocation or direct edit of the owned doc | the chair's own gates (never exempt) |
| 2 | Game Director → Story Director | commission in `game.md` (pillars, scope) | pillars review |
| 3 | Story Director → Lore Keeper | proposed beats/arcs | ★ **canon gate** — beats contradicting the bible are blocked |
| 4 | Lore Keeper → Story Director | canon bible + verdicts | consistency review on bible edits |
| 5 | Story Director ⇄ Casting Director | character needs per arc ↔ cast book | cast book covers named roles |
| 6 | Casting Director → PC branch | PC briefs | schema + autosim (existing pipeline, other lane) |
| 7 | Casting Director → NPC Director | roster slice per scene | roster exists in cast book |
| 8 | NPC Director → NPC Creator | casting sheet (archetype → npc_slot) | slots must exist in the baked scene |
| 9 | NPC Creator → catalog | profiles + sprites + stats | ★ **balance gate** (autosim harness) + creature@ schema |
| 10 | Casting chain → Scene | populate doc (`game@`) filling npc_slots | publisher schema + slot existence |
| 11 | Game/World Director → Scene Director | scene commissions in `world.md` | teleport-graph two-way rule |
| 12 | Scene Director → Asset Director | the brief's Register (terrain/reuse/create lists) | register is systems-scoped, not prop lists |
| 13 | Asset Director → Asset Creator | generation requests (`13 assets request/ensure`) | library audit first — reuse before generate |
| 14 | Asset Creator → catalog | staged variants | ★ **asset QC** + doctrine preview cull (Asset Director) |
| 15 | Asset Director → Scene Director | updated library + catalog | contact-sheet review |
| 16 | Scene Director → baker/publisher | level doc + brief | brief gate, level@ schema, teleport gate |
| 17 | Scene Director → brief (verdicts) | dated verdict blocks per snapshot | acceptance reads pass zone-by-zone |

## Phases

- **R1 — names before machinery** (this commit): this document; the
  `/asset-director` skill split out of `/create-scene` (register
  intake, library audit, doctrine custody, preview bench). No engine
  changes.
- **R2 — Lore Keeper + Story Director v1**: seed `games/entropy/lore/`
  from existing briefs; beat document type + the canon gate; first arc
  for the fair.
- **R3 — Casting chain v1**: cast book; NPC Director casting sheet for
  the fair's npc_slots; NPC Creator wrapping existing
  character/creature machinery + a character library; populate doc
  baked into the fair. Maps become a game.
- **R4 — Game/World/Systems chairs**: formalize only once ≥2 arcs /
  regions exist. Until then the human wears those hats informally —
  which is fine, because the rule is the document, not the title.
