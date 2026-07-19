# The studio org — every chair needed to make a game

Committed 2026-07-18 (R1), extended same day (v2: the systems wing —
items, economy, encounters, interface, QA, audio). The visual companion
(org chart + this ledger rendered) is the studio-org artifact; this file
is the source of truth. Phases R1–R6 at the bottom track what is real.

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
doesn't exist. Directors decide; creators make; bakers project — a
"creator" chair exists only where making is judgment-heavy (assets,
characters, items, creatures). Mechanical projection (spec → engine
resource) is machinery, never a chair.

## The hierarchy

```
Game Director
├── Story Director ──── Lore Keeper (canon gate)
│        ⇅                ├ Dialogue Writer (wearable by Story Director)
│        ⇅                └ Cutscene Director ── (actors from the Casting
│        ⇅                   Director; stages from the Scene Director)
│   Casting Director
│   ├── PC branch  (existing character-admission pipeline — other session's lane)
│   └── NPC Director ── NPC Creator (balance gate, character library)
├── World Director  (commissions scenes; graph-as-intent)
│   └── Scene Director
│        └── Asset Director ── Asset Creator (asset QC gate, asset library)
├── Systems Director  (rulers: stat budgets, difficulty curves, currency targets)
│   ├── Item Director ──── Item Creator      (stat-budget gate, item library)
│   ├── Economy Director                     (economy-sim gate, price book)
│   └── Encounter Director ── Creature Creator (difficulty gate, bestiary)
├── Interface Director  (menus, HUD, dialogue box, inventory/shop screens)
├── Audio Director ── Audio Creator (seam — registers reserved in briefs)
└── QA Director  (cross-cutting: acceptance reads → headless playtest runs)

Handshakes (parallel work meeting at sockets):
- Casting ⇄ Scene: populate doc (game@) fills a baked scene's npc_slots.
- Economy ⇄ Scene: shop inventories fill a baked scene's shop sockets.
- Encounter ⇄ Scene: encounter tables bind to a scene's spawn zones.
```

## Charters

| Role | Status | Owned document | Skill door | Gate on output | Library consulted |
|---|---|---|---|---|---|
| **Game Director** | new (R6) | `games/<g>/game.md` — pitch, pillars, scope, commissions | `/game-director` (R6) | pillars review (human) | world + story + systems docs |
| **Story Director** | built (R2) | `games/<g>/story/` — arcs, beats, quests; + `story/sequences/` (sequence@1, the tier above arcs — a prologue's segments + state ledger) | `/story-director`, `/sequence-director` | Lore Keeper canon gate; ★ **sequence gate** (warn=to-author, error=contradiction); dialogue-script@ schema | lore bible, cast book |
| **Continuity Director** | seam (named 2026-07-18) | cross-sequence invariants (`continuity_rules`, narrative checks) | (future) | ★ continuity gate (mechanical: equal-status, fixed choices, arc-independent-of-class, ledger completeness) + judgment (not-telegraphed, fragment-fairness) | the sequence ledger |
| **Lore Keeper** | new (R2) | `games/<g>/lore/` — canon bible (places, names, history, tone) | `/lore-keeper` (R2) | consistency review on canon edits | existing briefs (canon seeds) |
| **Dialogue Writer** | wearable | dialogue-script@ documents under `story/` | via Story Director | dialogue-script@ schema + canon gate | lore bible, cast book |
| **Cutscene Director** | built (2026-07-18) | `games/<g>/cutscenes/` — cutscene@1 staged story (puppets, free camera, frozen/absent PC) | `/cutscene-director` | ★ **cutscene gate**: stage exists, actors real + region-legal (R-005), speakers staged, dialogues exist, choreography in bounds | cast book, scene briefs |
| **Casting Director** | new (R3) | `games/<g>/casting/` — cast-book.md + per-scene sheets | `/casting-director` (R3) | populate gate (slots, creatures, dialogues, R-005 regions) | cast book, lore bible |
| **PC branch** | built (other lane) | `godot/characters/<slug>.json` → `.tres` | `/create-character` | schema + autosim balance harness | — (consumed via artifacts only) |
| **NPC Director** | new (R3) | per-scene casting sheet — which archetypes → which npc_slots | `/npc-director` (R3) | slots exist in baked scene; roles covered | cast book, scene brief |
| **NPC Creator** | partial (R3) | NPC profiles + sprites + stats | via NPC Director | balance gate (same harness); creature@ schema | character library (`13 library` sibling) |
| **World Director** | new (R6, wearable by Game Director) | `games/<g>/world.md` — regions, roster, graph-as-intent | `/world-director` (R6) | teleport-graph gate (publisher) | level graph, region briefs |
| **Scene Director** | built | `games/<g>/levels/<region>/<id>/` — brief + level doc | `/create-scene` | brief gate, level@ schema, teleport gate, acceptance reads | THE LIBRARY, atlases, concepts |
| **Asset Director** | built (R1) | the brief's **Register** section + `library.md` custody | `/asset-director` | doctrine custody + preview cull before ingest | `games/<g>/library.md` + contact sheets |
| **Asset Creator** | built | staged variants under `work/game/<g>/` → catalog | via Asset Director (`13 assets …`) | asset QC (`run_qc`): palette, outline, light, footprint, distinctness | family registry, archived references |
| **Systems Director** | partial (R4 targets, R6 chair) | `games/<g>/systems.md` — stat budgets per tier, difficulty curves, currency targets, mechanics flags | `/systems-director` (R6) | autosim harness thresholds | balance runs, economy sims |
| **Item Director** | new (R4) | `games/<g>/items/` — weapons, armor, consumables, key items (item@: stats, tags, tier, icon ref) | `/item-director` (R4) | stat-budget gate (Systems' tier curves) + item@ schema | item library (`13 library` sibling) |
| **Item Creator** | new (R4) | the item entries themselves — stat block + fiction + icon commission | via Item Director | item@ schema + stat budget; icon passes asset QC | item library dedup — reuse before generate |
| **Economy Director** | new (R4) | `games/<g>/economy/` — currency, price book (every item priced), shop inventories per scene, loot/drop tables, reward schedule | `/economy-director` (R4) | **economy-sim gate**: walk the intended progression; sources vs sinks (no dead-end wallets, no trivializing surplus); no unpriced item | price book, item library |
| **Encounter Director** | new (R5) | `games/<g>/encounters/` — encounter tables per region/scene, group comps, spawn zones, tiers | `/encounter-director` (R5) | **difficulty gate**: balance harness runs party-vs-comp at intended level | bestiary, region briefs |
| **Creature Creator** | partial (R5) | bestiary entries — creature@ profiles + sprites + stats (NPC Creator's twin over the same machinery) | via Encounter Director | difficulty gate + creature@ schema + sprite QC | bestiary (character library sibling) |
| **Interface Director** | new (R5) | `games/<g>/ui/` — menu specs (title, HUD, dialogue box, inventory, equipment, shop, save), UI theme | `/interface-director` (R5) | **readability gate**: min font px at target res, contrast, every menu node reachable by pad; schema | UI chrome library (assets via Asset Director) |
| **Audio Director** | seam | `games/<g>/audio/` — music briefs per region, SFX register per scene | named only | format/loudness when real | — |
| **QA Director** | new (R6, wearable by Game Director) | `games/<g>/qa/` — playtest scripts: acceptance reads + quest specs turned into repeatable headless runs | `/qa-director` (R6) | the runs themselves must pass (seed: test_game_integration plays Marguerite's quest to completion) | every brief's acceptance reads |

## Coverage map — every need of a finished game, and who owns it

The examination the org must survive: nothing a shipped game needs may
be unowned. Three answers are legal — a chair, a deliberate fold, or a
deliberate exclusion. Silence is not.

| Need | Owner |
|---|---|
| Story, quests | Story Director |
| Cutscenes / staged story (triggered + interstitials) | Cutscene Director (under Story) |
| Canon, naming, world history | Lore Keeper |
| Dialogue text | Dialogue Writer (wearable by Story Director) |
| Playable characters | PC branch (other lane) |
| NPCs in scenes | Casting chain |
| Monsters / bestiary | Creature Creator under Encounter Director |
| Combat encounters, difficulty | Encounter Director + Systems rulers |
| Items, weapons, armor, consumables, key items | Item Director → Item Creator |
| Prices, shops, loot, currency flow | Economy Director |
| Scenes, terrain, layout | World → Scene Director |
| Props, tiles, sprites, item icons, UI chrome | Asset Director → Asset Creator |
| Menus, HUD, inventory/shop screens, controls & key bindings, accessibility | Interface Director |
| Balance rulers (stat budgets, curves, currency targets) | Systems Director |
| Save/load, progression flags, gating | **fold** → Systems Director (mechanics contracts) |
| VFX / particles / animation frames | **fold** → Asset Director (animation is a family concern) |
| Tutorials / onboarding | **fold** → Story (a quest) + Interface (highlights) joint |
| Localization | **fold** → Story Director (text lives in committed docs; a pass, not a chair) |
| Music, SFX, ambience | Audio Director (seam) |
| Playtesting, regression | QA Director |
| Marketing, release, distribution | **excluded** — the human is the publisher |
| Multiplayer / netcode | **excluded** by design |

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
| 18 | Story Director → Item Director | reward/key-item requisition (a beat names a reward) | item must exist before the beat ships |
| 19 | Item Director → Item Creator | build order (tier, slot, fiction) | item library dedup — reuse before generate |
| 20 | Item Creator → Systems Director | stat block vs tier budget | ★ **stat-budget gate** |
| 21 | Item Director → Asset Director | icon commission (icon family; enamel-icon doctrine) | asset QC |
| 22 | Economy Director → Item Director | price book coverage | no unpriced item (publisher check) |
| 23 | Economy ⇄ Scene (handshake) | shop inventories ↔ shop sockets in scenes | every shop socket has inventory AND a keeper |
| 24 | Economy Director → Casting Director | shopkeeper requisition | cast book |
| 25 | Economy Director → Systems Director | sources/sinks model | ★ **economy-sim gate** — progression walk must afford itself |
| 26 | Encounter Director → Creature Creator | bestiary build order | bestiary dedup — reuse before generate |
| 27 | Creature Creator → Systems Director | comp vs intended party level | ★ **difficulty gate** (balance harness) |
| 28 | Encounter ⇄ Scene (handshake) | encounter tables ↔ spawn zones in level docs | zones exist in the baked scene |
| 29 | Interface Director → Asset Director | UI chrome commission (panels, cursors, icons) | asset QC |
| 30 | Interface Director → engine | menu specs + theme (baked, never hand-.tscn) | ★ **readability gate** — font px, contrast, pad-navigable graph |
| 31 | Scene/Story Director → Audio Director | audio register (music brief + SFX list per scene) | seam — briefs reserve the section today |
| 32 | Every director → QA Director | acceptance reads + quest specs | ★ playtest scripts run green headless |
| 33 | Story Director → Cutscene Director | a beat commissions a staged scene | the beat must exist |
| 34 | Cutscene Director → Casting Director | actor requisition (staged ids → creatures) | cast book — no creature/sprite, no stage |
| 35 | Cutscene Director → publisher/engine | cutscene@ document | ★ **cutscene gate** (stage, actors, R-005, speakers, dialogues, bounds) |
| 36 | Audio Director key door | `automap/audio.py` (`~/.automap/musicgen.json`, SUNO_API_KEY) | seam — pipeline pending |
| 37 | Story Director → its own sequence tier | sequence@1 (`story/sequences/`) — segments + state ledger | ★ **sequence gate** (checklist vs contradiction) |
| 38 | Sequence → every downstream chair | to-author warnings route work (scenes→Scene, dialogue→Dialogue, cast→Casting, design-blocked→human) | each chair's own gate |

## Phases

- **R1 — names before machinery** ✅ (2026-07-18): this document; the
  `/asset-director` skill split out of `/create-scene`.
- **R2 — Lore Keeper + Story Director v1** ✅ (2026-07-18):
  `games/entropy/lore/` seeded from the briefs (bible.md + canon.json,
  rulings R-001–R-005); arc/beat document type + the canon gate
  (`automap/story.py`, `scripts/14_story_director.py`, `/lore-keeper` +
  `/story-director` skills); first arc `fair_opening` (five beats,
  socket-bound to vaporis_fair, gate-clean with the two expected R4
  item warnings).
- **R3 — Casting chain v1** ✅ (2026-07-18): `games/entropy/casting/`
  (cast-book.md + the fair's 20-socket sheet); populate gate
  (`automap/casting.py`, fatal in the publisher — slots, creatures,
  dialogues, R-005 regions, canon admission); NPC Creator
  (`automap/npc_creator.py` + `scripts/15_casting_director.py`):
  creature docs in the 25–27 stat band (creature@1.1: figure_px +
  persona.region), figure sprites via genlab request → quantize (the
  figure pipeline keeps the reference's own banding; children get
  stature via canvas headroom); character library (`15 library`);
  baker places OverworldNPC per cast slot; 14 dialogues; the fair
  populated and verdict-passed zone by zone. Maps became a game.
- **R4 — Items + Economy** ✅ (2026-07-18, the game-shell round —
  docs/explorations/game-shell-round.md): item@/skill@/economy@ schemas,
  `games/entropy/{items,skills,economy}/` + systems.md rulers,
  stat-budget + economy-sim gates fatal in the publisher, brass tokens
  live at two fair stalls with cast keepers, the bronze valve closes
  the fair_opening arc warning-free.
- **R5 — Encounters + Interface**: **Interface half ✅** same round —
  ui@ schema + readability gate, vaporis-themed menus (pause stack:
  items/equipment/status/save), HUD, dialogue portraits (the figure_px
  faces), save slots, data-driven battle skills/items. **Encounters
  half pending**: bestiary on the creature machinery, encounter tables
  + difficulty gate.
- **R6 — Chairs of record**: Game/World/Systems/QA formalized (charter,
  world map, systems rulers doc, playtest scripts); Audio stays a seam
  until a pipeline exists. Formalize only once ≥2 arcs/regions exist —
  until then the human wears those hats, which is fine: the rule is the
  document, not the title.
