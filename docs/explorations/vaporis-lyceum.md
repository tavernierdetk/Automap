# The Lyceum Vaporum — a scale test for the SceneCreationDirector (2026-07-16)

Two things in one document: (1) an elaborate scene brief — an order of
magnitude past forest_glade — and (2) the SceneDirector ↔ Asset Creator
relation it exercises, with the gaps it exposes named and ordered.

---

## Part 1 — Scene brief: LYCEUM VAPORUM (magical school, Roman steampunk)

A working school of the arcane-mechanical arts, built like a Roman forum
and plumbed like a boiler room: pale marble colonnades wrapped in bronze
steam pipes, an aqueduct that carries pressure instead of water, lawns
quartered by terracotta pavement, statuary of philosopher-engineers, steam
drifting over everything. Sunlit but hazy — brass glints, verdigris stains,
white stone.

**Two levels** (the graph matters at this scale):

### `vaporis_lyceum` — the campus (exterior)
- **Grid 64×40** (2048×1280 px) — 10.7× forest_glade's area.
- **Zones**, south to north:
  1. **Porta Fumaria** (S center): the school gate — flanking columns,
     twin lit braziers, wall tiles closing the south edge; entry spawn.
  2. **Via Triumphalis**: terracotta avenue from the gate to the Atrium
     steps; alternating columns and statues down both sides.
  3. **The Peristylium** (center): the grand quad — lawn quartered by
     paths, the **Fountain of Minerva** at the crossing (large, animated
     water), benches and topiary along the walks.
  4. **Aqueduct of the Alchemists**: crosses the full map E-W on the north
     third as wall-tile arches with walk-through gaps; bronze pipes ride
     it (decor rows); a machine hisses at each junction.
  5. **Fabrica** (W wing): the workshop — building facade in wall tiles,
     door teleport (to a future interior), gear-machines and a brazier
     forge outside, boulders/scrap (rock family reused) by the wall.
  6. **Hortus Arcanus** (E): botanical court — vaporis-palette trees,
     topiary spheres, a canal (water tiles) with a bridged crossing.
  7. **Turris Astrorum** (NE): observatory tower base, locked door
     (teleport wired, target future), statue of the founder.
  8. **Atrium Magnum steps** (N center): the school's main door →
     teleport into `vaporis_atrium`.
- **Parallax ×2** (multi-layer test): distant dome-and-aqueduct city
  silhouette (motion 0.25, steam-grey modulate); near steam-haze band
  (motion 0.6, translucent warm white).
- **Props ~100** across 8 families; **npc_slots ~12** (rector, two
  professors, mechanicus, gardener, prefect, students ×4, gatekeeper,
  fountain spirit).

### `vaporis_atrium` — the Great Hall (interior)
- **Grid 28×18**; marble floor with mosaic center (path class as inlay),
  two column rows, braziers between columns, lectern + founder statue at
  the north end, door teleport back to the steps. No parallax; interior
  reads from props + floor alone.

### Asset demand (the Director's shopping list)
| family | substyles | size | count | supply path | anim | blocking |
|---|---|---|---|---|---|---|
| column | intact, broken, piped | 32×96 | 6 | **NEW family** (genlab) | – | base |
| statue | robed, founder | 32×64 | 4 | **NEW family** (genlab) | – | base |
| brazier | standing | 32×64 | 2 | **NEW family** (genlab) | flame 2f | base |
| fountain | tiered | 96×96 | 1 | **NEW family** (genlab) | water 2f | base |
| machine | gear-stack, boiler | 64×64 | 3 | **NEW family** (genlab) | shimmer 2f | base |
| topiary | sphere, spiral | 32×64 | 4 | **NEW family** (genlab or trees_px variant) | sway 2f | base |
| bench | marble | 64×32 | 2 | **NEW family** (genlab) | – | base |
| tree | deciduous, pine | mixed | 8 | **existing family, NEW identity** (procedural regen) | sway ✓ | trunk_base |
| rock | boulder | large | 4 | existing (vaporis recolor via new identity) | – | base |
| ground atlas | lawn/terracotta/canal/marble-wall/hedge | – | 1 | `13 atlas --identity vaporis` | – | class flags |

New identity: **`identities/vaporis.json`** — pale marble (cliff slot),
terracotta (path), cool lawn (grass), canal teal (water), laurel foliage
(canopy), dark bronze-brown (trunk) — **plus bronze/verdigris, which have
no slot today (gap G1 below)**.

---

## Part 2 — SceneDirector ↔ Asset Creator: the relation, precisely

**The Director is the demand side; the Asset Creator is the supply side;
the catalog is the ledger; the identity file is the contract that keeps
supply coherent.**

```
/create-scene skill (LLM director)          13_scene_director.py (tools)
  reads INTENT ("Roman steampunk school")     catalog · atlas · bake · snapshot
        │
        ▼
  1. catalog ────────────── the ledger: what exists, per family+identity
  2. per family needed:
       assets status ────── Asset Creator RESOLVE: fitness = N distinct
        │ fit?                variants of (family, identity, substyle),
        │                     style-current OR manual
        ├─ yes → reuse by NAME in the level doc
        └─ no  → two supply channels:
             ensure ──────── procedural painter (trees_px), instant
             request/ingest─ genlab: rich prompt → reference → repixel
                             — BOTH exit through the same QC gate into
                               the same catalog (props/1.1)
  3. fill level@2.2 (grids, props by name, teleports both ways, npc_slots)
  4. bake ─────────────── publish (hash-guard: touch-ups survive; atlases
                           packed per family) → baker (per-family painted
                           layers, y-sort, footprint collision, tile anim)
  5. snapshot ─────────── verdicts of taste come from pixels, not intent
```

Key properties of the seam:
- **Demand is by NAME, supply is by CONTRACT.** Level docs reference
  `column_0`; the Director never touches pixels. What makes `column_0`
  right is the family descriptor (perspective, blocking, shadow) + the
  identity palette — both machine-enforced by QC.
- **Fitness is per (family, identity, substyle).** A second identity in
  the same game does not collide: `identity_name` rides every catalog
  entry, variant numbering is shared, files are flat. Vaporis trees are
  new ASSETS of an existing FAMILY — `ensure` regenerates them under the
  new palette for free (procedural), no new code.
- **Onboarding a family is a registry entry** (descriptor, sizes,
  materials, substyles, prompt subjects) — proven twice (rock, stump).
  Seven new families for this scene is authoring work, not engineering.
- **The scene ships empty of story** — npc_slots are the StoryDirector's
  sockets; the Director provisions them generously.

### Gaps this scene forces (ordered by how hard they block)

- **G1 — the master palette's material list is CLOSED.**
  `pixelart.MATERIALS` = six nature slots keyed to identity attributes
  (canopy/trunk/cliff/water/path/grass). Roman steampunk needs **bronze**
  (pipes, gears, braziers) and ideally **verdigris** — and every slot is
  already spoken for (trees need wood, the canal needs water). Fix:
  visual-identity 2.4 adds an optional `materials: {bronze: [r,g,b], …}`
  block; `master_palette()` appends those ramps; family `materials`
  tuples may then name them. Small, backward-compatible, unblocks the
  whole aesthetic. **Do first.**
- **G2 — ground classes are also closed** (grass/path/water/stone/bush).
  Enough for this scene (marble walls = stone class non-walkable,
  buildings are wall tiles + door teleports — no new machinery), but
  steam-vent tiles (walkable + hazard) have no slot. Defer vents, note
  the pattern: CLASSES wants the same identity-driven extension as G1.
- **G3 — animation kinds.** `sway_frames`' band-drift is generic (it
  never knew about leaves) — flame flicker and fountain spray should
  work by pointing `mutable` at the right materials. True mechanical
  motion (gear ROTATION) cannot be band edits; machines get a heat
  shimmer, not a spin. Honest limit, note in the family entry.
- **G4 — review at scale.** The snapshot frames ~1152×648; a 2048×1280
  scene needs a zoomed-out shot plus per-zone close-ups (snapshot tool
  gains an optional CAMERA_POS/ZOOM env — trivial).
- **G5 — director ergonomics at 64×40.** Hand-writing 40 grid rows is
  error-prone; acceptable now, but a zone-plan → rows helper is the
  first thing to build when it hurts.

### Implementation order (when greenlit)
1. G1: visual-identity 2.4 `materials` block + `master_palette` extras
   (+ schema bump in platform-specs, tests).
2. `identities/vaporis.json`; ground atlas `vaporis_terrain`; regenerate
   trees/rocks under vaporis (pure `ensure`/existing requests).
3. Seven family registry entries + prompt subjects; genlab requests;
   synthetic stand-in references (real cloud references drop in later —
   quality follows the reference).
4. Snapshot tool CAMERA_POS/ZOOM (G4).
5. Author the two level docs; bake; iterate on snapshots per zone.
6. Full CI both repos.
