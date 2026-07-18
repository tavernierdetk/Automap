# Scene Generation Primer — step-by-step operations for a new 2D scene

The generic, operational walkthrough of the SceneCreationDirector path: from
"I want a rocky lakeshore east of the meadow" to an editor-editable, walkable
Godot scene. Every command is copy-paste runnable from the Automap repo root.

This is the *how-to* doc. Companions:
- [vaporis-pipeline-primer.md](vaporis-pipeline-primer.md) — a forensic
  reconstruction of one real build (the Lyceum Vaporum), with verbatim
  prompts, QC rejections, and catalog entries. Read it to see this flow
  under load.
- [explorations/scene-creation-director.md](explorations/scene-creation-director.md)
  — the design rationale and slice history.
- [primer.md](primer.md) — the *3D* pipeline (drone clip → walkable mesh).
  Different pipeline entirely; not covered here.
- The `/create-scene` skill (`.claude/skills/create-scene/SKILL.md`) — the
  interactive surface that drives this same flow.

---

## 0. The mental model and the two repos

**You fill a `level@2` JSON document; the pipeline validates it; the baker
projects it into a Godot scene.** You never hand-write a `.tscn` and you
never write into the game's `content/` tree.

| repo | role | what's committed |
|---|---|---|
| `~/Cowork/Automap` | the platform (generators, director, schemas' consumer) | `games/<game>/levels/*.json` (scene source of truth), `games/<game>/asset_requests.json` (asset recipes), `identities/*.json` |
| `~/Cowork/entropy-remade` (the game repo) | the consumer | `content/` is **published, never hand-edited** — except deliberate touch-ups to sprites, which the hash guard detects and preserves (`provenance: manual`) |

Intermediates live under `work/game/<game>/` (gitignored): staged tilesets,
props, genlab requests. `scripts/12_publish_game.py` moves staged → published;
`scripts/13_scene_director.py` is the director CLI wrapping everything below.

The contracts everything hangs on:

| artifact | role |
|---|---|
| `identities/<name>.json` | the style contract (`visual-identity@2.4`): color attrs + optional `materials` block |
| `automap/pixelart.master_palette()` | derives THE one palette from the identity — 5-band hue-shifted ramps per material |
| `automap/asset_creator.FAMILIES` | the asset family registry: generator, substyles, canvases, animation spec, and the descriptor QC enforces |
| `content/props/props.json` (game repo) | the ledger: every published asset with provenance, anchor, footprint |
| `platform-specs` (own repo) | the schemas: `level`, `visual-identity`, `props-tileset`, … — everything validates before it moves |

---

## 1. Catalog — reuse before generate

```
.venv/bin/python scripts/13_scene_director.py catalog --game entropy
```

Prints (and writes to `work/game/entropy/asset_catalog.json`):
- **backgrounds** with size + a palette-mood signature,
- **creatures** and their animations,
- **tilesets** — each atlas's identity, tile size, classes and their
  walkable/hazard mechanics flags,
- **props** — every ledger sprite with size and collision radius,
- **the level graph** — every level's id, kind, spawn tags, exits, npc_slots.

Read this before anything else. Two questions it answers:
1. *Can existing assets carry the new scene?* (Same identity/mood → skip
   steps 2–3 entirely.)
2. *Where does the new scene attach to the graph?* (Which neighbor level
   gets the reciprocal teleport.)

## 2. Identity + tile atlas — only if the scene needs a new look

Skip this whole step when an existing atlas fits.

**2a. Identity file.** Create `identities/<name>.json` and validate:

```
.venv/bin/python -c "import json, platform_specs; platform_specs.validate(
    json.load(open('identities/<name>.json')), 'visual-identity', '2.4.0')"
```

The 6 classic color attrs drive terrain; an optional `materials` block
(e.g. `bronze`, `verdigris` with `{color, hue_span}`) extends the master
palette for props.

**2b. Ground atlas.**

```
.venv/bin/python scripts/13_scene_director.py atlas \
    --identity identities/<name>.json \
    [--name <atlas_name>] \
    [--mechanics '{"stone": {"walkable": true}, "water": {"hazard": false}}']
```

`automap/tiles2d.py` renders the 5 fixed ground classes
(grass/path/water/stone/bush) in identity colors plus dual-grid transition
pieces, into `work/game/<game>/tilesets/` (staged — published later by
bake). `--mechanics` is the game-mechanics dial: it's how an interior gets a
walkable marble floor, or a lava level gets hazardous "water". One identity
can yield several atlases (`--name <identity>_interior`, etc.).

## 3. Prop supply — ensure what the scene will place

Also skippable when the ledger already has what you need (the catalog told
you). Two routes, both landing in the same ledger through the same QC gate:

**3a. Procedural (no prompts, pure code)** — trees today:

```
.venv/bin/python scripts/13_scene_director.py assets ensure \
    --family tree --substyle deciduous --min-variants 4 \
    --identity identities/<name>.json
```

`ensure` is idempotent and variety-aware: it resolves fitness against the
ledger (N *distinct* variants of the right style; hand-edited assets count),
paints only the gap, runs automated QC (`automap/asset_qc.py`), adds sway
frames to leafy trees, stages the sprites, and records the recipe in
`games/<game>/asset_requests.json` so `assets replay` can regenerate
everything from committed text.

**3b. Genlab (image-model reference → repixelized)** — for families the
procedural generators don't cover:

```
# 1. write the request (one per family/substyle/size)
.venv/bin/python scripts/13_scene_director.py assets request \
    --family column --substyle piped --size-class large \
    --identity identities/<name>.json
# → work/game/<game>/genlab/<req_id>/{request.json, prompt.md, incoming/}

# 2. take prompt.md to any cloud image tool; drop result PNGs into incoming/

# 3. ingest — repixelize + measure + QC-gate + stage
.venv/bin/python scripts/13_scene_director.py assets ingest \
    [--req <req_id>] --identity identities/<name>.json
```

Ingest runs RePixel (mask → downscale → CIELAB palettize → material
smoothing → re-band → sel-out outline + shadow), measures anchor and
blocking footprint *from the pixels*, then the 8-check QC gate
(crisp alpha, palette membership, single mass, outline, light direction,
band balance, grid alignment, blocking footprint). A FAIL is not staged —
fix the reference and re-ingest. `assets status` inspects the ledger,
`assets qc` re-runs the gate standalone.

**Provenance rules worth knowing:** every sprite carries
`procedural | generated | manual`. Hand touch-ups in Aseprite/editor are
legitimate — the publish hash guard notices the file changed since last
publish, preserves it, and flips provenance to `manual` (which *counts* as
fitting for `ensure`).

## 4. Author the level document

Write `games/<game>/levels/<id>.json` — the committed source of truth.
A layered scene (level@2.2) composes depth from four strata, back to front:

1. **`parallax[]`** — slow-scrolling backdrops. `motion_scale < 1` = farther
   away; `modulate` fades/tints them into atmosphere.
2. **tilemap `layers`** — the walkable ground and flat decor. Grids are
   palette-mapped rows of class letters (`g/p/w/s/b`). Think in
   *silhouettes*: paths that lead somewhere, water with a shore, blockers
   framing the space.
3. **`props[]`** — free-standing objects from the ledger, placed **by name
   at their FOOT position** (px). They y-sort with the player — walk above
   the foot line = pass behind, below = in front — and block only at their
   measured footprint (a trunk, not a canopy).
4. **`background`** — a single painted image, still available for
   one-image rooms; combines with props for interiors.

Plus the connective tissue:
- **`spawns[]`** — tagged entry points.
- **`teleports[]`** — **connect the graph both ways**: add this level's
  exits AND edit the neighbor's JSON to teleport back. The publisher errors
  on unknown targets and warns on missing spawn tags; reciprocity is on you.
- **`npc_slots[]`** — sockets where story could later live. Place them
  generously; they cost nothing. **A scene ships EMPTY of story** — slots
  yes, NPCs/dialogue no; population belongs to the StoryDirector.

For large grids, a throwaway zone-plan script beats hand-typing rows (paint
zones into a numpy char grid, compute prop feet from cells — see the
vaporis primer, stage 6). Validate before moving on:

```
.venv/bin/python -c "import json, platform_specs; platform_specs.validate(
    json.load(open('games/<game>/levels/<id>.json')), 'level', '2.0.0')"
```

*(Migrating an existing hand-made `.tscn` instead? `13_scene_director.py
transcribe <scene.tscn> …` reverse-engineers level docs from originals.)*

## 5. Publish + bake

```
.venv/bin/python scripts/13_scene_director.py bake --game entropy <id> [<id> …]
```

One command, three moves:
1. **Stage 12 publish** — validates every level against its schema, gates
   the teleport graph, hash-guard-copies props, packs per-family prop
   atlases, publishes palette/levels/tilesets/manifest into the game repo's
   `content/`.
2. **Headless reimport** — publish wipes Godot's `.import` cache; the baker
   loads through it, so it's refreshed first (a real bug class, now
   automatic).
3. **Bake** (`tools/bake_scene.gd`) — projects each tilemap level into an
   editor-editable scene under `content/scenes/`: ground TileMapLayers, one
   y-sorted TileMapLayer per prop family, texture origins / y-sort origins /
   collision ellipses all computed from the *measured* catalog metadata,
   multi-frame props wired as desynced tile animations.

Backdrop levels need no bake — the generic loader builds them at runtime.

## 6. Look at it, then iterate

Verdicts of taste (does the map *read*?) come from snapshots, not
imagination:

```
LEVEL=<id> SNAP_OUT=/abs/path/<id>.png \
    Godot --path ~/Cowork/entropy-remade \
    res://tests/level_snapshot.tscn --resolution 1152x648
```

Add `CAMERA_POS=x,y CAMERA_ZOOM=1.5` for zone close-ups. Read the PNG,
adjust the grid/props in the level JSON, re-run step 5. The loop is
seconds-to-minutes.

To walk it: baked scenes load through `Game.change_level` — enter via any
teleport from a connected level, or point a spawn at it.

## 7. Rules that bite

- **Never hand-edit `content/`** (published tree) — except sprite touch-ups,
  which the hash guard protects. **Never hand-write a `.tscn`** — it's baked.
- **Editor edits to baked scenes are legitimate** (that's the point of
  baking real scenes) **but die on re-bake** until the re-absorb slice
  lands. Warn before re-baking a scene anyone may have touched.
- **Reciprocal teleports are your job**; the publisher only checks that
  targets exist.
- Ground classes are a closed 5-vocabulary for now; mechanics overrides
  bend their behavior, not their identity.

---

## Routes through the flow

- **Reuse-only scene** (existing identity + assets): steps 1 → 4 → 5 → 6.
  The common case; lakeshore was built this way.
- **New-look scene**: the full chain 1–6; the Lyceum Vaporum is the worked
  example (new identity, new atlases, procedural + genlab assets).
- **Backdrop room**: steps 1, 4 (kind `backdrop`, `background` + optional
  props), then publish only — no bake.
- **Asset top-up only**: step 3 alone, then re-bake affected scenes.
- **Migrate a legacy scene**: `transcribe` → step 4's validation → 5 → 6.

## Worked examples (chronological)

| scene | proved |
|---|---|
| `meadow_test` | the baker + level@2.0, pixel-exact water blocking |
| `lakeshore` | first director-authored scene: prompt → reuse → grid → reciprocal graph edit → bake |
| `forest_glade` | layered scenes (level@2.2): parallax, y-sorted props, foot-line pass-in-front/behind |
| `vaporis_lyceum` / `vaporis_atrium` | full new-identity build: materials palette, genlab supply, per-family baked layers — see the vaporis primer |
