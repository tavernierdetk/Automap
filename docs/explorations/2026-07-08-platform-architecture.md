# Exploration — From Automap to a game-creation platform

**Status:** brainstorm / architecture brief, 2026-07-08. Nothing here is greenlit;
this is the framing document for the larger ambition. The existing pipeline
(stages 0–7, character A/C, game layer) is treated as **exploratory evidence**,
not as structure to design around.

---

## 1. The reframe

Automap so far: drone clip → walkable stylized Godot scene. The larger project:

> **A game-creation platform on top of Godot** — a structured system of asset
> creation and management where many kinds of media (drone footage, map data,
> photos, plans, text, procedural seeds) are ingested into **typed spec
> documents**, transformed by **swappable stages**, and emitted as **Godot
> scenes/assets/mechanics** — with a parallel emission path into **IFC/BIM**
> so the infrastructure-shaped modules are portable outside gaming.

Two framing decisions (2026-07-08):

- **Entropy is the model of what the pipeline must achieve — not of how the
  code should be structured.** The current `entropy-integrated` codebase is
  prototype-grade and disposable; the capability claim is what counts: the
  platform must be able to **recreate or modify the Entropy game so that our
  pipelines create it and feed it** — level-design modules produce its
  places, character-design modules produce its cast, mechanics modules run
  its combat and story — each creatable from various levels of abstraction
  (text brief, map extract, photo, hand-tuned spec). Entropy is the
  acceptance test, not the architecture.
- **The platform is a new project, not an Automap extension.** Automap's
  folder/data structure does not constrain anything; the platform lives in
  its own workspace as a **constellation of independently-workable modules —
  plausibly individual repos, each its own Claude project** (§10). Automap
  becomes one component in it (the drone-ingestion adapter + world-pipeline
  prototype). Immense total scope is acceptable *because* of this shape.

The most important discovery of the exploratory phase is not photogrammetry —
it's the **contract pattern**. Every seam that worked is a small, git-clean,
text contract between swappable boxes:

| Contract (exists today) | Producers | Consumers |
|---|---|---|
| `features.json` (trees/buildings/roads/water + provenance) | stage 5 detectors, OSM merge | stage 6 transformers |
| visual identity (data in `06_style_scene.py`) | user choice | stage 6 styling |
| `game.json` (NPCs/quests/dialogue, scale-agnostic anchors) | hand-authored | `WorldDirector` + managers |
| `CharacterProfile.tres` | photo→VLM (stage C), hand edit | `character.gd` rig |
| `GameEvents` signal bus | mechanics managers | UI, NPCs |
| glb-by-path seam (§11 of design spec) | pipeline | engine |

The platform is those contracts, generalized: **a registry of versioned spec
schemas + libraries of transformers between them**. Godot is the runtime;
Python CLI stages are the factory; specs are the product that lives in git.

---

## 1b. The acceptance scenario — "a neighborhood out of Montréal"

The sentence the finished architecture must make true:

> *Take a neighborhood out of Montréal, run it through our ingestion
> pipelines, and get a playable Godot level — in which each individual
> building is fully represented in IFC, so the building pipeline's output
> feeds Godot **and** stands alone as a general-purpose BIM artifact.*

Walked through the architecture, with an honest status per step
(✅ have · 🟡 partial/prototyped · ❌ missing):

| # | Step | Module (§10) | Status |
|---|---|---|---|
| 1 | Pick a bbox (e.g. a Plateau block); fetch sources: Québec LiDAR 1 m DTM, **Montréal's textured CityGML LOD2 building models** (city-wide, open, 2009/13/16), OSM/Overture roads/landuse/water, cadastre | ingest-geodata | 🟡 OSM fetch+cache built (`osm.py`); LiDAR/CityGML/Overture providers missing |
| 2 | Optional bonification: drone footage of the same block, fused in for currency/color | ingest-drone | ✅ stages 1–5 built (this repo) |
| 3 | Reconcile all sources into one world model — stable IDs, per-attribute provenance, per-feature LOD tier | worldmodel (fusion) | 🟡 merge semantics proven on buildings (`scan`/`osm`/`scan+osm`); needs generalization + stable IDs + LOD tiers |
| 4 | Per building: promote to an **IFC-complete record** — georeferenced footprint + LOD2 envelope (walls/roof solids from CityGML), storeys estimated (height ÷ floor-height, cadastre/OSM `building:levels`), openings/interiors when a deeper source exists, else generated-and-tagged | ifc-adapter + worldmodel | ❌ the new core piece; CityGML→IFC is a known conversion (IfcOpenShell authoring API) |
| 5 | Emit each building both ways: (a) `.ifc` file — the standalone BIM artifact; (b) game-ready mesh/kit instance via the visual identity | ifc-adapter · asset-factory | ❌ / 🟡 (prism+gable stylization built; IFC emission missing) |
| 6 | Style the level: identity applied to terrain zones, roads, water, buildings, props | godot-runtime (stage 6) | ✅ transformer chain + `madelinot` prove the pattern |
| 7 | Publish a walkable scene; game layer on top (NPCs, quests, dialogue) | godot-runtime | ✅ stage 7 + game.json layer built |
| 8 | Populate: characters/creatures from the asset pipeline at any abstraction level (chat, photo, spec) | asset-factory | 🟡 photo→profile→rig built; spec cascade proven in PixelAssetCreator; generative tier needs genserver |

Two properties make this scenario the right acceptance test: it exercises
**every module** of the constellation except drone capture (which remains an
optional bonifier — step 2), and step 4's "fully represented in IFC" forces
the discipline that makes building modules portable outside gaming
(end-state E) instead of game-shaped.

**Design consequence for the world model:** the building schema must be
**IFC-complete** — every attribute needed to write a valid IfcBuilding
(site georeference, storeys, envelope solids, openings, space boundaries
when known) lives in the world model itself, so `.ifc` emission is a
lossless projection and *any* building source (CityGML, OSM extrusion, scan
detection, plan ingestion, text description, procedural generation) flows
through one schema. Sources that can't fill a field leave it absent-with-
provenance rather than faked — the IFC file records what is known.

---

## 2. Macro-architecture

```
                       ┌────────────────────────────────────────────┐
   INGESTION ADAPTERS  │        CANONICAL WORLD MODEL (hub)          │  EMISSION ADAPTERS
                       │                                            │
   drone footage ────▶ │  terrain surface(s)                        │ ──▶ Godot scene (.tscn/.glb)
   OSM / Overture ───▶ │  feature graph (typed, provenanced,        │ ──▶ IFC file (IfcOpenShell)
   open LiDAR/DEM ───▶ │    georeferenced, multi-LOD)               │ ──▶ minimap/atlas/exports
   text description ─▶ │  semantic regions (landcover, zones)       │
   plans & images ───▶ │  placements (game.json layer)              │
   procedural seed ──▶ │                                            │
                       └───────────────┬────────────────────────────┘
                                       │ styled/instanced by
              ┌────────────────────────┼─────────────────────────┐
              │                        │                         │
      VISUAL IDENTITY           GAME SPEC                 ASSET LIBRARY
      (cross-cutting spec)      (scope, mechanics,        (creatures, items,
                                movement, UI mode)         furniture, kits)
              │                        │                         │
      World pipeline          Mechanics pipeline          Asset pipeline
      (terrain→level)         (story/quests/combat)       (parts→characters)
```

Three **production pipelines** with hard boundaries, two **cross-cutting
specs**, one **hub model**, and adapter rings on both sides. Rules:

1. **Pipelines never import each other.** They interact only through specs
   (the asset pipeline reads Visual Identity; mechanics reads the Asset
   Library's stat blocks; the world pipeline reads both). This is the
   `GameEvents`-bus lesson applied at platform scale.
2. **LLMs fill specs; they never emit geometry or binaries directly.** A
   Claude character-creator writes a `CharacterProfile`; a level-describer
   writes a world-model delta. Specs are reviewable, diffable, regenerable —
   the reproducibility guarantee survives generative AI.
3. **Every feature carries provenance** (`scan` / `osm` / `lidar` / `llm` /
   `manual` / fusions like `scan+osm`) — already proven in `automap/osm.py`.
   Provenance is what makes multi-source merge, licensing compliance, and
   "manual edits survive regeneration" all tractable.
4. **Artifacts are regenerated, never committed.** Same hard rule as today,
   platform-wide: specs in git, binaries in `work/`.

### The canonical world model (the hub)

`features.json` grown up: a semantic scene description that is **engine-
agnostic and source-agnostic**. Sketch of the units:

- **Terrain**: one or more surfaces (heightmap grid and/or mesh), CRS +
  transform to WGS84 when georeferenced (optional — procedural worlds aren't).
- **Features**: typed instances (tree, building, road, water, prop…) with
  geometry (point/polyline/footprint), attributes, **LOD tier**, provenance,
  and stable IDs (so manual edits and re-ingestion reconcile).
- **Regions**: landcover/zone masks (grass splat, sand strip, district tags) —
  the styling substrate.
- **Placements**: gameplay anchors (NPCs, zones, spawn points) — scale-
  agnostic anchoring already solved by `game.json`.

Buildings deserve a note: their attribute set should be **IFC-shaped from the
start** (storeys, wall/ridge heights, openings when known) so the IFC emission
adapter is a projection, not a reconstruction. See §4.

---

## 3. The three pipelines

### 3.1 World pipeline — level design as a funnel

Wide end = generation, narrow end = manual editing, **enterable at any depth**:

```
 seed/spec ─▶ macro layout ─▶ terrain ─▶ semantic features ─▶ styling ─▶ placements ─▶ manual polish
    ▲             ▲              ▲              ▲                ▲            ▲
    │             │              │              │                │            │
 text brief   procedural     LiDAR/DEM      OSM/Overture     visual        game.json
 (LLM fills   noise/graph    or drone       or detectors     identity      authoring
  the spec)   grammars       (ODM DSM)      (stage 5)        (stage 6)     (LLM-assistable)
```

**Intakes and where they enter:**
- **Drone footage** enters at *terrain + semantic features* (stages 1–5 today) —
  its unique contribution is **current, high-res color and 3D detail**;
  elevation alone is free from LiDAR in much of the world.
- **Open map data** enters at *terrain* (LiDAR DTM) and *semantic features*
  (OSM/Overture footprints, roads, landuse, water) — already half-built
  (`automap/osm.py`, `terrain.py`). This is end-state B (§6): skip the drone.
- **Textual description** enters at *seed/spec*: an LLM turns "a fishing
  village on a headland, one lighthouse, fog" into a world-model draft
  (region layout + feature list), which the rest of the funnel realizes.
- **Non-standard/representative images** enter two ways: as *style evidence*
  (drive the visual identity: palette extraction, mood) or as *layout
  evidence* (a sketch/floor plan → features, the hard research end).
- **Procedural** enters at *macro layout / terrain* (noise, road grammars,
  settlement scattering) and can also **backfill** any layer the other
  sources left sparse.

**Transformation capabilities** (e.g. "post-apocalyptic version of this real
place") are cheap *because of the semantic layer*: a transformer rewrites the
feature graph (buildings → ruined variants, roads → cracked, add overgrowth
regions) and swaps the identity — no pixel/mesh surgery. Transformations are
world-model → world-model functions; they compose.

**Reconciliation** (multi-source merge) is a core engine, not a special case:
the greedy provenance-tagged matcher in `osm.py` generalizes to
*match → adopt-best-attribute-per-source → keep-unmatched-with-provenance*.
Rule of thumb proven on mountain_cross: sources are complementary, so never
discard unmatched features from either side.

### 3.2 Asset pipeline

**Taxonomy** (asset families), each with a characteristic schema:

- **Creatures** — shared: size, color identity, detail budget, stat block
  (the mechanics interface). Sub-families: *humanoids* (parts: head, hair,
  facial features, limb proportions, posture, wardrobe), *quadrupeds*
  (body plan params), *custom form factor* (free rig).
- **Items** — wieldable/consumable; icon + world model + stat effects.
- **Furniture / fixtures** — the boundary family: these are **IfcFurniture /
  IfcSanitaryTerminal /**… i.e. IFC-classifiable (§4).
- **Kits** — reusable building blocks (walls, roofs, windows, fences) that
  both the world pipeline (building stylization) and manual editing consume.
  "Textures and building blocks strategy" = kits + palette discipline.

**Generation backends, tiered by cost and fidelity** (each behind the same
profile contract, the stage-A/B/C lesson):

1. **Parametric/primitive** (built): profile → primitive rig (`character.gd`);
   next step MPFB2/MakeHuman headless in Blender for rigged humans.
2. **Kit-bashed procedural**: profile → assembled from the kit library
   (deterministic, seeded — the madelinot tree-kit pattern).
3. **Generative 3D**: image/text → mesh via TRELLIS 2 / Hunyuan3D 2.1 (both
   open-licensed, commercial-OK). ⚠ CUDA-centric, ≥8 GB VRAM even quantized —
   runs on the **remote GPU node** (§5b), not the M4. Output needs auto-rig
   (Mixamo et al.) and *identity conformance* (palette/poly-budget post-pass)
   before it enters the library.
4. **2D/pixel sprites**: catalog compositing (LPC) + AI tilesets —
   PixelAssetCreator territory; its compositor, quantizer, and adapter facade
   lift directly (§8).

**The spec shape for all of this is already prototyped** in PixelAssetCreator's
three-tier cascade: *narrative spec* (LLM-authored, human-readable) →
*selection spec* (enum-locked against the asset taxonomy, so the LLM can only
pick valid parts) → *build spec* (deterministic converter, with a decision
trace for auditability). Generalize that cascade per asset family; it is the
concrete mechanism behind "gradually more granular personalization".

**The Claude character creator** (the flagship asset feature) is a
conversation that fills the narrative spec — a `CharacterProfile v2`
(appearance + personality + role + stat block + dialogue seed) — and the
cascade + backends realize it. Two force
multipliers already in hand: the **photo→traits stage C** (a second intake
into the same profile), and — from Entropy — the **autosim balancing
harness**: *LLM proposes stats, batch simulation validates them against the
game spec's difficulty envelope before the character is admitted*. That
closes the loop that usually makes LLM-generated stats untrustworthy.

**Asset↔mechanics mapping** is a spec, not code: each asset family schema has
a mechanics-facing section (stat block, interaction verbs, slots/tags), and
the mechanics pipeline consumes only that section. An asset with no mechanics
section is scenery by definition.

### 3.3 Mechanics pipeline

What exists — **twice, complementarily**:

- Automap's game layer: `GameEvents` bus + quest/dialogue managers +
  `game.json` — data-driven from day one, tested, with quests and
  scale-agnostic world anchoring, but simple trees and no persistent state.
- entropy-integrated's runtime: a richer **dialogue engine** (addressable
  node-graph scripts with `choices[].next_node`, an `effects[]` contract
  mutating world state, mid-conversation speaker/skin swaps, bus-decoupled
  rendering) + a **narrative blackboard** (`WorldState` flags/vars/event log,
  `Persona` relations/memories, `Faction`) + the **envelope/result pattern**
  (`CombatEnvelope` in → `CombatResult` out) for handing control between
  world and a mechanics stage — but its scripts are hardcoded in GDScript,
  condition evaluation is stubbed, and it has no quests.

The `narrative` module's founding act is **merging these two proofs**: the
game.json data-discipline + quest layer from Automap, the effects contract +
blackboard + envelope pattern from Entropy. Grow module-by-module, each
data-driven:

- **Story design**: standardized story graph (nodes = beats/scenes, edges =
  decision branches) *above* the per-NPC dialogue trees; `game.json` is the
  per-scene compilation target. LLM-assistable (an LLM drafts the graph, the
  schema validates it, the WorldDirector plays it). The dialogue-node schema
  should be extracted from entropy-integrated's de-facto format (`id`, `text`,
  `speaker_id`, `choices[].next_node`, `effects[]` of
  `memory`/`flag`/`var_delta`) — its runtime already consumes exactly that
  shape, it just never got a data loader or validator.
- **Game scope spec**: number of levels, sizes, interaction types, difficulty
  envelope — the budget document other pipelines validate against.
- **Core mechanics as pluggable rule modules**: RPG family (from Entropy's
  designs: 5-attribute model, threshold-gated decaying statuses organic/
  lithic, ATB ticks — rebuild data-driven, don't port the Python), movement
  profiles (walk/sprint/fly already exist; bounded flight, platforming as
  controller variants), environment interaction verbs.
- **Deterministic chaos RNG** (from Entropy, port directly): seeded named
  streams + skew-normal sampling with clip modes — reproducible battles,
  and "luck" as a stat surface. ~120 lines to GDScript.
- **UI**: modal/HUD library that consumes the bus and the visual identity
  (the HUD already only consumes signals — keep that rule).

### Cross-cutting spec 1: Visual identity

One document that *every* emitter respects. Fields:

- **Resolution regime**: native / render-scale / pixelation factor.
- **Palette**: size, ramps, composition rules; enforcement mode (quantize,
  hue-shift toward, free-with-accents). Applies to 3D vertex colors,
  textures, *and* 2D sprites — the same palette object. (An enforcement
  primitive already exists: PixelAssetCreator's nearest-color quantizer +
  nearest downscale, used on its tilesets.)
- **Shading/style masks** — the adjustable 3D-style axes:
  - low-poly flat-shaded (current madelinot)
  - toon/cel + outline pass
  - PBR/photoreal (ortho-textured — current unstyled path)
  - retro PS1/N64 (vertex snap, affine warp, low-res textures)
  - **pixel-art 3D** (low-res render + palette quantize + dither — the bridge
    to PixelAssetCreator's world)
  - painterly / hand-painted-texture look
  - sketch/ink/hatching post-process
  - voxel
- **Materials policy**: ortho texture vs vertex color vs generated textures;
  poly/texel budgets per asset family.
- **Mood**: lighting, fog, post-processing stack.

In Godot most of this is implementable as **global shader material overrides +
a screen-space post stack + a palette LUT**, which is what makes "identity as
a swappable spec" real rather than aspirational — restyling = re-running
stage 6 + swapping a shader set, as `--identity madelinot` already shows.

### Cross-cutting spec 2: Game spec

Scope, mechanics selection, movement profile, UI mode, difficulty envelope.
The world pipeline reads it (level sizes, traversal constraints), the asset
pipeline reads it (stat budgets), mechanics is configured by it.

---

## 4. The IFC question — backbone or projection?

**Recommendation: IFC as a first-class *projection*, not the internal
backbone.** The canonical world model stays engine- and standard-agnostic;
IFC gets a dedicated, high-quality adapter pair (`to_ifc` / `from_ifc`) built
on **IfcOpenShell** (mature, LGPL, Python-first, IFC2x3→IFC4x3, high-level
authoring API; Bonsai gives free Blender-based inspection of our output).

Why not IFC-as-backbone: IFC is a heavyweight AEC exchange schema — forcing
trees, quest anchors, and creatures through it taxes every pipeline with its
ontology; and game-loop code parsing IFC is a dependency nobody wants. Why
still first-class: the brief's portability goal — *any module that ingests
plans/images/text into building descriptions should be extractable as a
standalone BIM component* — only works if those modules speak IFC natively at
their boundary.

**The tier rule the brief hypothesized holds up well:**

> *IFC-classifiability is the boundary between infrastructure assets and
> scenery/character assets.*

- **Infrastructure tier** (has an IFC class): buildings (IfcBuilding/Wall/
  Roof/Slab/Door/Window/Stair), storeys and interior spaces (IfcBuildingStorey,
  IfcSpace), furniture/fixtures (IfcFurniture…), roads/bridges (IFC4x3 adds
  built infrastructure), site & terrain (IfcSite + IfcGeographicElement).
  These features carry IFC-shaped attributes in the world model, georeference
  via IfcSite/IfcMapConversion, and round-trip through the adapter.
- **Game tier** (no IFC class): creatures, gameplay items, quest placements,
  styling. Never touches IFC.

**LOD reconciliation** (the interiors ambition): keep per-feature **LOD tiers**
in the world model, CityGML-style — LOD0 footprint → LOD1 prism (built today)
→ LOD2 roof-shaped (gable detection is already there) → LOD3 openings →
LOD4/interior (storeys + IfcSpaces). Sources fill the tiers they can
(footprints: OSM/Overture; heights: scan or LiDAR nDSM; interiors: plans,
text, or procedural room-graph generation — public data almost never provides
interiors, so **bonification = generation constrained by the shell**, clearly
provenance-tagged `generated`). The fusion engine (§3.1) reconciles per tier,
never across tiers, and the walkable scene picks the deepest tier available
per building.

---

## 5. Real-world data: sources, fusion, licensing

**GPS association is already solved in v1** (`geo.txt` → WGS84 bbox →
Overpass, cached, reprojected into scene frame; DJI + OSM agree within
meters on mountain_cross). Generalize `osm.py` into a **source-fusion
engine** with pluggable providers:

| Source | Gives | Status / caveat |
|---|---|---|
| Drone (ODM) | fresh color, DSM detail, true state | built; capture-quality-bound |
| OSM/Overpass | footprints, roads, water, landuse, names | built v1; ODbL share-alike **on the data layer**; produced works (the game) are free |
| **Overture Maps** | 2B+ building footprints, cleaner schema, bulk download | add as provider; open-licensed |
| **Open LiDAR (Qc/Canada)** | 1 m DTM + canopy height, province-wide (Données Québec); federal HRDEM | the drone-less terrain source; QC is a best-case jurisdiction |
| **Montréal open 3D** | **textured CityGML LOD2 building models, city-wide** (2009/13/16 vintages) + city MNT + aerial LiDAR | the acceptance scenario's building source (§1b); LOD2 solids beat footprint extrusion; CityGML→IFC conversion path |
| Cadastre / municipal open data | parcels, building heights, zoning | provider slot; per-city variance |
| **Google Photorealistic 3D Tiles** | — | **excluded**: license prohibits extraction, offline use, and derived assets |

Fusion semantics (generalizing what's proven): stable-ID matching per feature
class → per-attribute source priority (e.g. footprint: survey > scan;
height: scan/LiDAR > tags; color: scan only) → provenance recorded per
attribute → unmatched features from every source survive. Manual edits are
just another source with top priority — that's how "regeneration doesn't
destroy hand-polish" falls out of the same mechanism.

---

## 5b. Compute fabric — the M4 and the GPU node

**Decision (2026-07-08): remote GPU work is in-scope.** A privately-networked
NVIDIA machine we control is promoted from "escape hatch" to a planned
platform component; establishing the pipeline to it is its own **side
project** (small, independent module — exactly the kind the architecture is
supposed to absorb).

The design burden on the platform itself is deliberately tiny, because every
stage is already *spec-in / artifact-out*. Remote execution is therefore a
**transport concern, not an architecture concern**:

- **Backend registry**: each generation backend declares its requirements
  (`local`, `cuda`, `vram_gb`, model assets). The dispatcher routes a job to
  the M4 or the GPU node; callers never know where a backend ran.
- **Job protocol v1** (keep it boring): push spec + inputs to the node
  (ssh/rsync over the private LAN), run a containerized worker per backend
  (TRELLIS 2, Hunyuan3D, segmentation models, MPFB2 renders, even ODM —
  which would drop the qemu-emulation tax), pull artifacts back into
  `work/`. Content-address inputs/outputs (hash-keyed) so re-runs are
  cache hits and transfers are incremental.
- **Same laws apply remotely**: artifacts are regenerated-never-committed;
  the node holds no state that isn't reproducible from specs; a job's spec +
  backend version fully determine its output (modulo model nondeterminism —
  record seeds).
- **Privacy boundary**: the node is inside the private network, so the
  "photos never leave the machine" guarantee relaxes to "never leave the
  network" — an explicit, acceptable widening; cloud APIs remain a separate,
  per-case decision.

What this unlocks, immediately: tier-3 generative asset backends (§3.2),
ML detection backends (DeepForest/SAM/segmentation, semantic-layer slice 4),
native-speed ODM, and MPFB2/Blender batch renders — all without touching the
16 GB ceiling that the interactive/Godot side still lives under.

---

## 6. End-states — value, requirements, distance

Not mutually exclusive; each is a shippable plateau. Distances assume the
contract/spec layer (§9 step 1) exists.

**A. Place-to-postcard** — drone clip → stylized walkable scene *(≈ today)*
- **Value:** personal-place capture, demos, the pipeline testbed.
- **Needs:** polish only (capture guide exists, identities exist). Cheap.

**B. Anywhere-generator (drone-less)** — coordinates → walkable stylized world
- **Value:** unlimited coverage, zero capture cost, minutes not hours;
  the first genuinely *productizable* output.
- **Needs:** LiDAR/DEM ingestion as an alternate terrain stage (replaces ODM;
  `03b` terrain-first branch is the head start), OSM/Overture as *primary*
  (not overlay) feature source, and **style synthesis without an orthophoto**
  (landcover→palette; the madelinot zone-styling already colors terrain
  without ortho texture — that's the proof). Medium effort, mostly recombination.
- **Note:** A+B compose — drone bonifies a B-world where footage exists
  (fusion engine does the merge; that's the "data-source merge" ambition).

**C. Multi-LOD twin with interiors (IFC-centric)**
- **Value:** the serious/non-game market — AEC visualization, digital twins,
  serious games in real buildings; where the BIM portability pays off.
- **Needs:** IFC adapter pair, LOD-tier model (§4), interior sources (floor-
  plan-image → IFC is a research-grade subproject; text → room-graph →
  IfcSpaces is nearer), per-tier reconciliation. Large effort — gate behind B.

**D. Game-creation studio** — the full three-pipeline platform
- **Value:** the ambition itself: small teams/solo creators produce varied
  games (RPG family first) with AI doing the volume work under spec control.
- **Needs:** schema registry, asset taxonomy + library + at least two
  generation backends, mechanics modules (combat, inventory, save), story-
  graph tooling, Claude creator flows, multi-scene game spec. Build as thin
  vertical slices on top of A/B (the phare quest slice is slice #1 in spirit).

**E. Portable BIM components** — text/image/plan → IFC, as standalone modules
- **Value:** reusable outside gaming entirely (the brief's explicit goal);
  each module ships as its own package with IFC in/out.
- **Needs:** C's foundations; enforce "IFC at module boundary" from day one so
  extraction is repo-splitting, not rewriting.

Sequencing that respects value-per-effort: **A (close it out) → B (new
plateau, mostly recombination) → D thin slices (one real game vertical) → C/E
(when the infrastructure tier earns it)** — with the §9 platform chassis
built first, since every path needs it.

---

## 7. Weak spots & inflection points

1. **Compute ceiling vs generative ambitions — RESOLVED in principle (§5b).**
   The private GPU node is in-scope; the remaining risk moves to execution:
   the dispatch/transfer side project must stay boring (ssh + containers +
   content-addressed artifacts), and backends must declare requirements so
   local-vs-remote stays invisible to callers. Policy order for any new
   capability: local small models (Ollama pattern — proven) → GPU node →
   cloud API (per-case, since it crosses the privacy boundary).
2. **Schema governance.** The platform *is* its schemas; today they live as
   Python dicts, GDScript resources, and markdown. *Inflection:* the third
   consumer of any schema. Fix: a `specs/` registry — versioned JSON Schemas,
   one source of truth, validated in CI, mirrored to GDScript resources.
   This is step 1 of §9 and the highest-leverage cheap thing on the list.
3. **2D/3D duality.** PixelAssetCreator is 2D sprites; Automap is 3D; the
   identity spec claims to span both. *Decision to make early:* 3D-first
   with pixel-art-3D as the bridge style (recommended — one runtime, one
   scene model), vs. true 2D game support (second runtime path through
   everything; big scope tax).
4. **IFC scope creep.** The moment IFC entities appear inside game-tier code,
   the backbone has inverted. Guardrail: IFC types exist only in the adapter
   package; the world model uses its own vocabulary (§4 tier rule).
5. **LLM boundary discipline.** Generative steps must stay inside the
   "fill a spec, validate, regenerate" loop. The Entropy autosim pattern
   (propose → simulate → admit) is the template for making every LLM output
   *earn* admission. The moment an LLM writes a binary or an unvalidated
   blob into the library, reproducibility is gone.
6. **Licensing plumbing.** ODbL share-alike applies to the *data layers* we
   derive from OSM (features.json with OSM footprints is arguably a derived
   database) — keep per-attribute provenance (§5) so any layer can be
   published or withheld deliberately. Google tiles stay excluded.
7. **Reconciliation identity.** Multi-source + manual edits + re-ingestion
   only stays sane with **stable feature IDs** (spatial-hash or
   source-ID-based). Retrofitting IDs later is painful — put them in the
   world-model schema from v1.
8. **Scene-centric today, game-scoped tomorrow.** Everything is per-scene;
   a game is scenes + persistent state + progression. The game spec (§3.3)
   and a save system are the missing spine — design the spec early, build
   late.
9. **Orchestration temptation.** At platform scale the pressure for a
   one-button build will return. Keep the law: a conductor may *chain*
   stages, but every inter-stage artifact stays a file a human can inspect,
   diff, and hand-edit.
10. **Parallel-session ownership.** Generation (Python, world model, specs)
    vs. runtime (Godot engine/game) is already a working split. Draw module
    boundaries to match it: the world model + adapters land on the
    generation side; bus + managers + UI on the runtime side; `specs/` is
    the shared, low-churn middle.

---

## 8. Reuse ledger

### Automap (this repo) — the platform seed

| Component | Disposition |
|---|---|
| Contract pattern + provenance fusion (`osm.py`) | **Foundation** — generalize into world model + fusion engine |
| Stages 1–3b (frames, ODM, mesh, terrain-first, sea surgery) | **Keep** as the drone ingestion adapter |
| Stage 5 detectors (trees hardened, buildings point-first) | **Keep** as scan-source providers behind the fusion engine |
| Stage 6 transformer registry + identities-as-data | **Keep** — becomes the styling stage; identities graduate into the Visual Identity spec |
| Game layer (bus, quest/dialogue managers, `game.json`) | **Keep** — mechanics pipeline v1 |
| Character A/C (profile, primitive rig, photo→VLM) | **Keep** — asset pipeline v1 + the local-model backend pattern |
| Engine/pipeline path seam, scene publishing (stage 7) | **Keep** — the Godot emission adapter v1 |

### EntropySnapShot — design mine + two real assets

Reality check: **not a Godot game** — a ~1,400-line Python 3.11 console
combat-balancing simulator. No engine, assets, UI, data files, or LLM code.
Verdicts:

| Subsystem | Verdict |
|---|---|
| Seeded skew-normal "chaos" RNG (`Systems/RNG.py`, `SkewRNG.py`) | **Already ported** — entropy-integrated's `RNG.gd` is a faithful GDScript port (seeded named streams, Azzalini skew-normal, entropy field); keep the Python twin as the balancing-sim reference |
| AutoSim harness (`AutoSim/`: batch runner, policies, win-rate aggregation) | **Rebuild the pattern** — becomes the platform's balance validator, incl. for LLM-proposed stats (§3.2) |
| Status system (organic/lithic families, threshold-gated, decaying) | **Design spec only** — novel and coherent; re-express as data-driven Godot resources |
| ATB tick combat, template-method skills, 5-attribute stat model | **Design spec only** — sound patterns, console-coupled code; known balance bug in turn-order reset |
| Class-relations matrix | Stub (all zeros, unapplied) — keep the idea |
| Terrain/inventory/save/dialogue/UI | Absent — nothing to port |

### PixelAssetCreator (`pixelart-backbone`) — the spec-cascade prototype

Reality check: a TypeScript/pnpm monorepo (React + Express + BullMQ/Redis +
`sharp`), prototype-stage (WIP orchestration, empty Prisma schema, deprecated
OpenAI Assistants API). Chat → structured character JSON → **composited ULPC
(LPC spritesheet) character** + AI tilesets + Godot `.tres` export. Crucially,
the LLM **selects and specs; it does not draw** — sprites are composited from
the vendored CC-licensed LPC art library (humanoids only).

| Subsystem | Verdict |
|---|---|
| **Three-tier spec cascade + validators**: `CharacterLite` (narrative: identity/personality/physical/stats) → `CharIntermediary` (enum-locked part selection over a 104-category taxonomy) → `ulpc.build` (render spec), each JSON-Schema + AJV | **Adopt the pattern wholesale** — this *is* the "LLM fills specs, gradually more granular" funnel, already proven for characters. Regenerate the enums for our asset library |
| Deterministic converter with decision `trace[]` (`intermediary-converter`) | **Reuse structure** — the spec→build engine; the audit trace is the reviewability guarantee (§2 rule 2) in code |
| Sprite compositor + orientation slicer + manifest (`sprite-compose`) | **Reusable as-is** — engine-agnostic layered pixel-art compositing (any 2D asset family) |
| Palette quantizer + nearest downscale (`tileset-compose/quantize.ts`) | **Reusable as-is** — the first real *palette-enforcement* mechanism for the Visual Identity spec (needs dithering + configurable palettes) |
| `renderTres` Godot serializer | **Reusable** — generic `.tres` writer; the character/tileset resource shapes are game-specific, rewrite |
| Image adapter facade (`gpt-image-1` / Stable Diffusion / stub) | **Reusable as-is** — the pluggable-generation-backend seam, with an offline stub for tests |
| Tileset generators (blob47/coast16; direct / mask-first / procedural Wang) | **Re-toolable** — autotile logic + quantize/stitch worth keeping; prompts, sizes, palette hardcoded |
| Project settings ("aesthetics", resolutions, provider config) | **Seed of the Visual Identity spec** — right fields, unenforced today (`palette_path` unwired) |
| LLM layer (Assistants API threads, 500 ms polling) | **Re-tool** — keep validated-JSON turns + enum-constrained prompts + slug stabilization; move to structured outputs |
| BullMQ orchestration, Express/React apps, Postgres/MinIO | **Not worth porting** — stage chaining lives in the client, retries off, DB/object-store unused; our staged-CLI philosophy replaces it |

**Two findings that matter beyond the code:**
- `CharacterLite.stats` is **Entropy's exact 5-attribute model** (`creature_affinity, chaos_mastery, kinesthetic, lucidity, terrain_control`) — the two prototypes already share an asset↔mechanics contract across repos. The platform's asset↔mechanics mapping (§3.2) is a formalization of something already practiced.
- The character art is **selection over a catalog, not generation** — which is exactly the kit-bashed backend tier (§3.2 #2). Original creatures beyond the catalog need a different art source; the converter/compositor generalize, the LPC data does not.

### entropy-integrated — the reference game (and proof the pipelines connect)

Reality check: Godot 4.4, pure GDScript, single-commit prototype, signal-bus
architecture (`CombatBus`, `DialogueBus` + 3 more autoloads). Its greatest
value is evidentiary: **the whole chain already runs once, end-to-end** —
PixelAssetCreator's full spec chain (`char_def_lite` → `intermediary` →
`ulpc.json` → sprite manifest) ships beside the sprites in `Assets/Creatures/`,
the in-game `Creature.tres` carries the same 5 stats, the simulator's chaos
RNG / organic-lithic statuses are faithfully ported, and combat runs as a
swappable stage. That is the platform thesis demonstrated at prototype grade.

| Subsystem | Verdict |
|---|---|
| **Dialogue engine** (controller + bus + skinnable HUD; node-graph scripts with `choices[].next_node`, `effects[]`, speaker/skin swaps) | **The story-graph runtime seed.** Already spec-shaped (`start_session(script: Array)`); needs a JSON/`.tres` loader (scripts are hardcoded in `_build_script()` today), the stubbed condition-eval in `DialogueSystem.choose_line`, and a schema+validator |
| **Narrative blackboard** (`WorldState` flags/vars/tagged event log, `Persona` relations + `NPCMemory`, `Faction`) | **Adopt the design as-is** — the persistent-narrative-state layer the platform lacks; under-wired today (memory commit commented out) but the resource shapes are sound |
| **Envelope/result pattern** (`CombatEnvelope` → `CombatRouter` → `CombatResult`) | **Adopt as the generic world↔mechanics-stage handoff** — the inter-module contract pattern, already working |
| Chaos RNG service (`RNG.gd`, seeded named streams, skew-normal, entropy field) | **Reusable as-is** — the EntropySnapShot port already exists in GDScript; no re-port needed |
| Combat screen (`BattleStage`, `TurnController`, statuses, target modes) | **Re-toolable into the combat mechanics module** — carries the full stat/chaos/status model with UI; caveats: round-robin turns (NOT the sim's ATB — restore it from the sim's design), 2 skills, hardcoded damage formula, prototype-grade code |
| Creature model (`Creature.tres`: 5 stats, derived formulas, chaos dials, XP/levels, `user://` persistence) | **Reusable as the shared contract** — CharacterLite JSON → `Creature.tres` is a near-1:1 automatable mapping |
| Sprite integration (directory-convention `ulpc_frames/` scan) | **Re-tool** — two competing asset conventions + path rot; replace with a manifest-driven loader (the sprite manifest already has frames/fps/folders, it's just unread) |
| Overworld (8-dir movement, party-follow chain, spawn-tag scene transitions) | **Design reference** for the 2D runtime skeleton; debug-scaffolded, slug-coupled |
| Quests, cutscene engine, narrative director, inventory, LLM/validators | **Absent** — quest layer builds on `WorldState.flags` + event log; the rest is new work |

**Cautionary tale it also teaches:** the JSON specs are *inert* at runtime —
the game ignores the manifests and rediscovers assets by directory convention,
and `.tres` files carry dead paths from a folder reorg. That is precisely the
failure mode `platform-specs` + validators exist to prevent (§7 weak spot 2).

---

## 9. What to build first (if greenlit)

Scope can be immense **as long as it is modular**: the explicit mandate is to
build the overarching architecture first — the spec registry, the world-model
hub, and the seams — so that each capability (a detector, a backend, the GPU
transport, an IFC adapter, a narrative module) is an independently workable
component that plugs in without renegotiating the whole.

1. **`specs/` schema registry** — extract the schemas that already exist
   (features, identity, game.json, character profile) into versioned JSON
   Schemas with validators; mirror to GDScript. Cheap, unblocks everything,
   forces the world-model design conversation.
2. **World model v1 + fusion engine extraction** — promote `features.json`
   to the hub model (stable IDs, LOD tier, per-attribute provenance);
   refactor `osm.py`'s matcher into the generic reconciler. Mostly
   restructuring of working code.
2b. *(parallel side project)* **GPU-node transport v1 (§5b)** — backend
   registry + ssh/rsync job runner + content-addressed artifact cache, proven
   on one real workload (ODM native, or DeepForest on mountain_cross).
   Independent of everything else by design; unlocks tier-3 backends later.
3. **End-state B vertical slice** — pick a bbox with no drone footage
   (anywhere in southern Québec): LiDAR DTM + OSM/Overture features →
   madelinot-styled walkable scene. Proves the platform claim (same funnel,
   different intake) with zero new research.
4. **Claude character creator slice** — conversation → CharacterProfile v2
   (+ stat block) → autosim validation → walk as them in the B-world.
   First LLM-fills-spec flow, first asset↔mechanics mapping in anger.
5. Then choose the next plateau (§6) with evidence in hand.

---

## 10. Project topology — a constellation of repos

The modularity mandate made structural: modules are **individually-ownable
repos** (each plausibly its own Claude project with its own memory/CLAUDE.md),
coupled *only* through versioned specs. A module can be rewritten, outsourced
to a parallel session, or extracted for use outside the platform (the
end-state-E requirement) without renegotiating anything else.

```
platform-specs        the shared center: JSON Schemas + validators + codegen
  │                   (Python / GDScript / TS mirrors). Low-churn, versioned;
  │                   every other repo pins a spec version. THE first build.
  │
  ├── worldmodel      canonical world model + fusion/reconciliation engine
  │                   (Python lib; grows out of features.json + osm.py)
  │
  ├── ingest-drone    ← Automap stages 1–3b/5, re-homed (this repo's successor)
  ├── ingest-geodata  OSM / Overture / LiDAR / cadastre providers (end-state B)
  ├── ingest-media    text briefs, reference images, plans → world-model deltas
  │                   (the LLM spec-filler flows live here)
  │
  ├── genserver       GPU-node transport + containerized backend workers (§5b)
  ├── asset-factory   spec cascade + generation backends + asset library
  │                   (absorbs PixelAssetCreator's compositor/quantizer/converter)
  │
  ├── godot-runtime   the engine side, as Godot addon(s): map loader, GameEvents
  │                   bus, mechanics modules (quest, dialogue, combat, inventory,
  │                   save), UI kit, identity shader stack
  ├── narrative       story-graph schemas + narrative director/runtime
  │                   (seeded by whatever entropy-integrated proves out —
  │                   possibly starts inside godot-runtime, splits when real)
  │
  ├── ifc-adapter     to_ifc / from_ifc on IfcOpenShell; the portable BIM
  │                   components (end-states C/E) ship from here
  │
  └── entropy         the game — reference consumer & requirements driver;
                      never a dependency of anything
```

Working rules for the constellation:

1. **Dependency direction is one-way**: everything may depend on
   `platform-specs`; nothing depends on a consumer (games, exporters).
   Ingesters and the asset factory depend on `worldmodel`; runtime modules
   depend only on specs (they read published artifacts, the §11-of-design-spec
   path seam generalized).
2. **A module earns a repo** when it has an owner-session, a spec boundary,
   and a consumer — until then it incubates inside an existing repo (the
   narrative module inside godot-runtime, the fusion engine inside Automap).
   Splitting early creates coordination cost with no isolation benefit.
3. **Cross-repo integration is tested by the reference game**: "can Entropy
   still be produced/run" is the platform's CI question, the way
   mountain_cross is stage 5's.
4. **Parallel Claude sessions map to repos** — the ownership split that
   already works here (generation vs. runtime) becomes the norm; memory and
   CLAUDE.md stay per-module, `platform-specs` is the only shared context
   every session needs.

Bootstrap sequence for the new workspace: create `platform-specs` and seed it
by *extracting* the schemas that already exist (features.json, identity,
game.json, CharacterProfile, CharacterLite/CharIntermediary) — §9 step 1 is
literally the founding act of the new project.

---

## 11. Gap analysis — have / don't have / need

The consolidated ledger, per module of the constellation. "Have" counts
working prototype code anywhere in the four repos; "need" is what stands
between here and the two acceptance tests (§1: recreate Entropy; §1b: the
Montréal neighborhood).

| Module | Have (proven somewhere) | Don't have | Need to build |
|---|---|---|---|
| **platform-specs** | 6+ de-facto schemas living as code (features.json, identity, game.json, CharacterProfile, CharacterLite→Intermediary→build cascade, dialogue-node format); AJV validation practice (PixelAssetCreator) | A registry; versioning; single source of truth; GDScript/Python mirrors; CI validation | The registry repo itself + extraction of the existing six + codegen. **The founding act** |
| **worldmodel** | features.json with typed features + provenance; merge semantics (greedy match, per-source attribute adoption, unmatched survive); scale-agnostic anchoring | Stable feature IDs; per-attribute provenance; LOD tiers; regions as first-class; IFC-complete building schema; multi-scene/game scoping | Promote features.json → world model v1; extract `osm.py`'s matcher into the generic fusion engine |
| **ingest-drone** | The whole thing: frames→ODM→mesh/terrain→detectors (trees, point-first buildings)→sea surgery | — (mature for its scope) | Re-home behind world-model contracts; becomes the *bonifier* (§1b step 2) |
| **ingest-geodata** | OSM Overpass fetch+cache+reproject; roads/water/buildings parsing | LiDAR/DEM provider (Qc 1 m, HRDEM); **CityGML LOD2 provider (Montréal)**; Overture bulk; cadastre; drone-less terrain stage | The end-state-B workhorse; CityGML parsing (citygml4j-class tooling or direct GML→solids) |
| **ingest-media** | Photo→traits VLM flow (local Ollama, categorical schema, validation); LLM-fills-spec pattern (PixelAssetCreator assistants) | Text brief→world-model delta; reference-image→identity (palette/mood extraction); plan/sketch→layout (research-grade); modern structured-output LLM layer | Start with text→world-spec and image→identity (cheap, high leverage); plans much later |
| **genserver** | Nothing (decision made §5b; box exists on the private LAN) | Everything | Backend registry + ssh/container job runner + content-addressed cache; prove on ODM-native or DeepForest |
| **asset-factory** | Spec cascade + converter-with-trace; sprite compositor/slicer; palette quantizer; image-gen adapter facade; photo→profile; primitive rig | 3D asset families (creatures beyond humanoid, items, furniture, kits); MPFB2 backend; generative-3D backend + auto-rig; identity conformance pass; asset library w/ manifests; asset↔mechanics section enforcement | Asset taxonomy schemas first, then backends tier by tier (parametric → kit → generative via genserver) |
| **godot-runtime** | Map-loader path seam; third-person controller; GameEvents bus; quest+dialogue managers; game.json loader; HUD; publish pipeline (stage 7); identity-as-data styling (stage 6); headless integration tests | Identity shader stack (cel/PS1/pixel-3D…); manifest-driven asset loader (replace directory convention); inventory; save/persistence beyond creatures; multi-scene game shell; combat module integration | Package as addon(s); port the envelope/result pattern in; unify the two dialogue runtimes |
| **narrative** | TWO half-engines: Automap's data-driven quests + entropy-integrated's effects-contract dialogue, WorldState/Persona blackboard, event log | Story graph above dialogue trees; condition evaluation (stubbed); quest layer on blackboard; narrative director; cutscenes; LLM story-drafting flow with validation | Merge the two proofs behind one schema set; then the story-graph runtime; director last |
| **ifc-adapter** | Nothing but the decision (§4) and IFC-shaped building attributes in features.json (footprint/height/ridge/roof) | Everything IFC: to_ifc/from_ifc, georeferencing (IfcMapConversion), storey/space modeling, CityGML→IFC, LOD tiers, plan→IFC | IfcOpenShell-based emitter for LOD1–2 buildings first (Montréal scenario step 4–5); from_ifc later |
| **mechanics (in godot-runtime)** | 5-stat model ×3 repos; chaos RNG (Python + GDScript ports); organic/lithic statuses; combat stage w/ UI; envelope/result handoff; autosim balancing harness (Python) | ATB scheduler in-game (round-robin today); data-driven damage/skill formulas; skill library (2 exist); inventory; balance-validation service wired to LLM flows | Extract combat rules to data + validators; restore ATB from the sim; wire autosim as the admission gate |
| **entropy (reference game)** | A playable prototype proving the chain connects end-to-end | Producibility *from* the platform (its content is hand-wired, specs inert at runtime) | Regenerate it progressively from specs — each module's integration test |

Reading the matrix vertically: the **have** column is remarkably full — the
exploratory year produced working prototypes of almost every pattern the
platform needs. The **need** column clusters into three genuinely new builds
(platform-specs, genserver, ifc-adapter) plus systematic *extraction and
merging* of everything else. That is what "architecture first" buys: the rest
of the work is refactoring proven code behind contracts, not research.

---

## Appendix — external grounding (checked 2026-07-08)

- **IfcOpenShell**: mature LGPL C++/Python IFC toolkit, IFC2x3→IFC4x3, high-
  level authoring API; Bonsai (ex-BlenderBIM) for GUI inspection.
  [ifcopenshell.org](https://ifcopenshell.org/) · [bonsaibim.org](https://bonsaibim.org/)
- **Google Photorealistic 3D Tiles**: license prohibits extraction, offline
  use, machine-derived assets — unusable as an asset source.
  [policies](https://developers.google.com/maps/documentation/tile/policies)
- **OSM (ODbL)** / **Overture Maps** (2B+ footprints, open, bulk-downloadable):
  game-asset-friendly with attribution; share-alike applies to derived *data*.
  [OSM Legal FAQ](https://wiki.openstreetmap.org/wiki/Legal_FAQ) ·
  [Overture](https://docs.overturemaps.org/attribution/)
- **Québec open LiDAR**: province-wide 1 m DTM/canopy (Données Québec) +
  federal HRDEM (CanElevation, on AWS Open Data).
  [Données Québec](https://www.donneesquebec.ca/recherche/dataset/produits-derives-de-base-du-lidar) ·
  [HRDEM](https://registry.opendata.aws/canelevation-dem/)
- **Montréal open 3D**: city-wide **textured CityGML LOD2 building models**
  (2016, plus 2009/2013 vintages; photogrammetric roofs, extruded textured
  walls; CityGML/3DM/GDB formats), digital terrain model, aerial LiDAR — all
  on the city's open-data portal.
  [Bâtiments 3D 2016 (LOD2)](https://donnees.montreal.ca/dataset/batiment-3d-2016-maquette-citygml-lod2-avec-textures2) ·
  [MNT](https://donnees.montreal.ca/dataset/modele-numerique-de-terrain-mnt)
- **Generative 3D**: TRELLIS 2 (Microsoft, open, commercial-OK) and Hunyuan3D
  2.1 (Apache-2.0) are the current open image/text→3D leaders; CUDA-centric,
  ≥8 GB VRAM quantized — not M4-viable, plan for API/remote.
  [survey](https://trellis2.app/blog/best-image-to-3d-models-huggingface)
