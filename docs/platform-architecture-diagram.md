# Platform architecture — working diagram

**Living document.** This is the artifact we comment on, edit, and eventually
lock. Prose rationale lives in the
[architecture brief](explorations/2026-07-08-platform-architecture.md);
this file is the structural source of truth once locked.

- **Color = gap status** (from brief §11): green = have (working prototype
  somewhere in the four repos) · yellow = partial · red = missing · purple =
  external to the platform.
- Solid arrows = data/artifact flow. Dashed arrows = spec/contract
  dependency or compute offload.
- Each box maps to a module of the constellation (brief §10) — i.e., a
  candidate repo / Claude project.

```mermaid
flowchart LR

  %% ==================== SOURCES ====================
  subgraph SRC["Media & data sources"]
    direction TB
    drone["Drone footage (MP4 + SRT)"]:::have
    osm["OSM / Overture"]:::partial
    lidar["Open LiDAR / DEM (Qc, Canada)"]:::have
    citygml["Montréal CityGML LOD2 (textured)"]:::missing
    cadastre["Cadastre / municipal data"]:::missing
    photos["Photos (people)"]:::have
    briefs["Text briefs / descriptions"]:::missing
    refimg["Reference images / plans"]:::missing
    seeds["Procedural seeds"]:::partial
  end

  %% ==================== INGESTION ====================
  subgraph ING["Ingestion adapters"]
    direction TB
    ingdrone["ingest-drone<br/>frames → ODM → DEM/mesh → detectors"]:::have
    inggeo["ingest-geodata<br/>OSM + HRDEM LiDAR providers<br/>coverage probe · UTM reproject · cache"]:::have
    ingmedia["ingest-media<br/>VLM photo→traits · LLM text→spec"]:::partial
    proc["procedural generators<br/>noise, grammars, scattering"]:::partial
  end

  %% ==================== HUB ====================
  subgraph HUB["worldmodel — the hub"]
    direction TB
    fusion["Fusion / reconciliation engine<br/>stable IDs · per-attribute provenance<br/>source priority · manual edits survive"]:::have
    wm["Canonical world model<br/>per-scene docs LIVE (scene-features@2.0.0)<br/>IFC-complete buildings · regions · LOD 3+ = next"]:::partial
    fusion --> wm
  end

  %% ==================== SPECS ====================
  subgraph SPECS["platform-specs — schema registry (the shared center · repo LIVE)"]
    direction TB
    reg["Versioned JSON Schemas + validator lib<br/>founding four @1.0.0: scene-features ·<br/>visual-identity · game · character-profile<br/>(codegen deferred by decision)"]:::have
    vid["Visual identity spec<br/>colors/transformers @1.0.0 ·<br/>resolution + style masks = v2"]:::partial
    gspec["Game spec<br/>scope · mechanics · difficulty envelope"]:::missing
  end

  %% ==================== GENERATIVE ORCHESTRATION ====================
  subgraph GENAI["Generative orchestration"]
    direction TB
    llm["LLM spec-fillers (Claude)<br/>fills specs, never binaries<br/>v1 surface: /create-character session"]:::have
    gate["Admission gates<br/>schema validation · autosim balance<br/>(balance.py: cast duels vs envelope)"]:::have
    llm --> gate
  end

  %% ==================== ASSET FACTORY ====================
  subgraph AF["asset-factory"]
    direction TB
    cascade["Spec cascade<br/>narrative → selection → build (traced)"]:::partial
    b_param["Parametric backend<br/>(primitive rig, MPFB2)"]:::partial
    b_kit["Kit-bash backend<br/>(seeded, deterministic)"]:::partial
    b_gen3d["Generative 3D backend<br/>(TRELLIS 2 / Hunyuan3D + auto-rig)"]:::missing
    b_2d["2D sprite compositor<br/>+ palette quantizer"]:::have
    alib["Asset library<br/>manifests · taxonomy · stat blocks"]:::missing
    cascade --> b_param & b_kit & b_gen3d & b_2d
    b_param --> alib
    b_kit --> alib
    b_gen3d --> alib
    b_2d --> alib
  end

  %% ==================== GPU NODE ====================
  gpu["genserver — private GPU node (repo LIVE)<br/>transport v1: job keys · registry · ssh/rsync/docker<br/>node unprovisioned — ODM-native = acceptance test"]:::partial

  %% ==================== GODOT RUNTIME ====================
  subgraph GR["godot-runtime (addons)"]
    direction TB
    styler["Styling transformers (stage 6)<br/>identity applied to world model"]:::have
    publish["Scene publish (stage 7)<br/>.glb/.tscn by path seam"]:::have
    engine["Engine core<br/>map loader · controllers · shaders"]:::have
    bus["Signal buses (GameEvents)"]:::have
    narr["Narrative runtime<br/>dialogue graph · blackboard · quests · director"]:::partial
    mech["Mechanics modules<br/>combat (envelope/result) · chaos RNG<br/>inventory · save"]:::partial
    ui["UI kit + identity shader stack"]:::partial
    styler --> publish
  end

  %% ==================== IFC ====================
  subgraph IFC["ifc-adapter (incubating in automap/ifc.py)"]
    direction TB
    toifc["to_ifc / from_ifc<br/>IfcOpenShell 0.8 · IfcMapConversion<br/>LOD0-2 tiers · provenance pset"]:::have
    ifcart[".ifc artifacts<br/>one per building (lagrave: 126)"]:::have
    toifc --> ifcart
  end

  game["entropy — reference game<br/>(acceptance test, consumer only)"]:::partial
  bim["External BIM world<br/>Revit · Bonsai · viewers"]:::ext
  planifc["External plan→IFC modules<br/>(e.g. CubiCasa pipeline) — .ifc only,<br/>no code crosses the boundary"]:::ext

  %% ==================== FLOWS ====================
  drone --> ingdrone
  osm --> inggeo
  lidar --> inggeo
  citygml --> inggeo
  cadastre --> inggeo
  photos --> ingmedia
  briefs --> ingmedia
  refimg --> ingmedia
  seeds --> proc

  ingdrone --> fusion
  inggeo --> fusion
  ingmedia --> fusion
  proc --> fusion

  ingmedia --> cascade

  wm --> styler
  wm --> toifc
  ifcart --> bim
  bim -.->|from_ifc| toifc
  planifc -.->|.ifc → from_ifc → source "bim"| fusion
  toifc -.->|building substitution<br/>ifc_to_glb → representation override| alib

  alib --> publish
  alib -.->|stat blocks| mech

  publish --> game
  bus --> game
  narr --> game
  mech --> game
  ui --> game
  engine --> game

  gate -->|world deltas| fusion
  gate -->|asset specs| cascade
  gate -->|story graphs| narr

  vid -.-> styler
  vid -.-> cascade
  vid -.-> ui
  gspec -.-> mech
  gspec -.-> cascade
  gspec -.-> gate

  reg -.-> HUB
  reg -.-> AF
  reg -.-> GR
  reg -.-> IFC

  b_gen3d -.->|jobs| gpu
  ingdrone -.->|heavy jobs| gpu
  inggeo -.->|ML detectors| gpu

  %% ==================== STYLES ====================
  classDef have fill:#c8e6c9,stroke:#2e7d32,color:#1b1b1b
  classDef partial fill:#fff9c4,stroke:#f9a825,color:#1b1b1b
  classDef missing fill:#ffcdd2,stroke:#c62828,color:#1b1b1b
  classDef ext fill:#e1bee7,stroke:#6a1b9a,color:#1b1b1b
```

## Reading notes

- **The hub discipline:** nothing flows source → consumer directly; every
  ingested thing becomes world-model content (with provenance) or a spec.
  The one deliberate exception: `ingest-media → cascade` (a photo or chat
  fills a character spec without touching the world model).
- **The IFC dual emission** (acceptance scenario §1b): a building leaves the
  world model twice — as a styled game asset via `styler → publish`, and as
  a standalone `.ifc` via `to_ifc`. Both projections of one IFC-complete
  record.
- **`platform-specs` has no data flow** — only dashed contract edges. It is
  the center precisely because it does nothing at runtime.
- **`genserver` is invisible to callers** — dashed offload edges only;
  no module's contract changes based on where a backend ran.
- **`entropy` consumes everything and feeds nothing** — the dependency
  direction that keeps the platform honest.

## Decisions locked (2026-07-08)

- [x] **Module boundaries**: only `platform-specs` earns a repo today
  (`Cowork/platform-specs`). Everything else incubates where it lives:
  fusion engine + worldmodel in Automap, narrative inside `godot/`, the
  spec cascade in PixelAssetCreator until extracted. A module earns a repo
  when it has an owner-session, a spec boundary, and a consumer (brief §10
  rule 2, applied literally).
- [x] **World model scope**: per-scene world-model documents (features.json
  grown up, **stable feature IDs from v1**) + a thin game-level manifest
  listing scenes and persistent state. Promote to a game-scoped store only
  when cross-scene reconciliation actually appears.
- [x] **IFC-complete building schema**: mandatory attributes per LOD tier
  are decided inside the schema-writing work (worldmodel v1 + ifc-adapter),
  not before it. Deferred deliberately, not forgotten.
- [x] **Spec registry mechanics**: JSON Schema 2020-12; semver carried in
  each schema's `$id`; one Python validator library in `platform-specs`.
  GDScript mirrors stay hand-written until schema churn proves codegen is
  worth building. No TS target until a TS consumer exists.
- [x] **The `gate` placement**: validators are a shared **library**
  (shipped by `platform-specs`), invoked per-module — not a service. The
  diagram's `gate` box is a pattern, not a deployable.
- [x] **2D/3D duality**: 3D-first, one runtime, one scene model. Pixel-art
  is a visual-identity style mask (low-res render + palette quantize +
  dither). PixelAssetCreator's compositor/quantizer survive as 2D **asset**
  backends (sprites, icons, tilesets), not a second game runtime.
- [x] **Where manual editing enters**: spec-file editing is the v1
  mechanism (diffable, reviewable, survives regeneration as a top-priority
  source). Godot editor plugins are a later convenience layer over the same
  files.
- [x] **Naming**: module names stay placeholders; each locks when its repo
  is created. Locked so far: `platform-specs`, `genserver`.

## Changelog

- 2026-07-12 — v0.9: **character creator v1** (brief §9 step 4, the first
  LLM-fills-spec flow): a Claude Code session (`/create-character` skill)
  interviews and writes `character-profile@2.0.0` (new in platform-specs:
  narrative + appearance + the Entropy five-attribute stat block);
  `scripts/10_create_character.py` admits it through schema validation + the
  rebuilt AutoSim pattern (`automap/balance.py` — seeded chaos RNG, short ATB
  duels vs a self-admitting reference cast, difficulty envelope) and projects
  the appearance to the rig's `.tres`; `--play` makes it the player via the
  inherited game.tscn shell. Proven end-to-end on Marguerite à Théodore in
  lagrave (28-point draft rejected, 26-point revision admitted at 0.42).
  `llm` and `gate` flip to have. Envelope graduates to the game spec later;
  NPC placement + dialogue-tree generation are the logged follow-ups.
- 2026-07-10 — v0.8: **building substitution** — drop an IFC plan in to
  replace a generated building (`scripts/09_replace_building.py`). from_ifc +
  `automap/placement.py` (georeference or footprint-fit) + `ifc.ifc_to_glb`
  produce a placed asset; the world model gains an optional building
  `representation` override (`scene-features@2.1.0`, additive) written as
  source `bim` — which now ranks just under `manual` in the fusion engine, so
  it outranks detectors and survives regeneration. Stage 6 instances the
  asset (terrain-draped) instead of a proxy. Proven on lagrave (manoir →
  building-0072, survives a stage-5 re-run). Plans can originate from the
  external CEC-SHA pipeline — IFC files only, no code crosses.
- 2026-07-10 — v0.7: **ifc-adapter v1** (brief §4, the deferred IFC decision):
  `automap/ifc.py` — `to_ifc` projects world-model buildings to georeferenced
  IFC4 (LOD0-2 tiers decided here, provenance pset, IfcMapConversion), proven
  on all 126 lagrave buildings; `from_ifc` reads plan→IFC models back as a
  `bim` fusion source, reducing detailed walls/storeys models to footprint +
  height. `toifc`/`ifcart` flip to have. **CEC-SHA seam**: the mature
  (proprietary Baseline) plan→IFC pipeline stays external — only `.ifc` files
  cross, no code, per the IFC-as-module-boundary rule.
- 2026-07-10 — v0.6: **end-state B proven** (brief §9 step 3): `lagrave`
  (La Grave, Havre-Aubert) built from public data only — NRCan HRDEM LiDAR
  (`automap/geodata.py`: STAC + COG windowed reads + pixel coverage probe)
  + OSM through the fusion engine, madelinot-styled, published. Same funnel,
  different intake, zero drone footage — `inggeo` and the `lidar` source
  flip to have. Follow-ups logged: LiDAR-CHM tree detection (no-RGB gates),
  open orthophoto texture provider, Overture footprints.
- 2026-07-09 — v0.5: `genserver` repo bootstrapped at `Cowork/genserver`
  (second locked module name): transport v1 — content-derived job keys,
  backend registry (echo + odm mirroring stage 2), LocalTarget/SshTarget
  over ssh/rsync/docker, proven end-to-end on local Docker (fresh run /
  cache hit / failure diagnosis) — `gpu` flips missing → partial. Node
  provisioning runbook written; ODM-native on the node is the acceptance
  test that flips it to built.
- 2026-07-09 — v0.4: worldmodel v1 lands (brief §9 step 2): per-scene
  world-model documents (`scene-features@2.0.0` — stable feature ids,
  per-attribute provenance, building LOD tiers) + the generic fusion engine
  (`automap/worldmodel.py`, extracted from the OSM merge). Proven on
  mountain_cross: re-run is a byte-identical fixed point, manual edits
  (provenance `manual`) survive regeneration, stage 6 consumes v2 unchanged —
  `fusion` flips partial → have; worldmodel keeps incubating in Automap per
  the module-boundary decision.
- 2026-07-08 — v0.3: `platform-specs` repo bootstrapped at
  `Cowork/platform-specs` (founding four schemas transcribed + validator lib,
  12 tests incl. the real phare game.json) — `reg` flips missing → have.
- 2026-07-08 — v0.2: all eight agenda decisions locked (session review);
  `platform-specs` bootstrap greenlit.
- 2026-07-08 — v0.1: initial diagram from the architecture brief (§2, §10,
  §11 statuses).
