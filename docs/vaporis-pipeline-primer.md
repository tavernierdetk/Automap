# Primer — how the Lyceum Vaporum was concretely built (2026-07-16)

Every stage below is reconstructed from CONSIGNED artifacts (nothing from
memory): committed JSON in `games/entropy/` + `identities/`, gitignored but
present request/provenance files under `work/game/entropy/genlab/`, and the
published game tree in `~/Cowork/entropy-remade/content/`. File paths are
given at each stage so the claims can be re-checked.

---

## Stage 0 — the contracts everything hangs on

| artifact | role |
|---|---|
| `identities/vaporis.json` | the style contract: 6 classic color attrs + (new, visual-identity **2.4**) a `materials` block: `bronze`, `verdigris` `{color, hue_span}`, `flame` |
| `automap/pixelart.master_palette()` | derives THE one palette: per material a 5-band ramp (V ×[0.42→1.55], S ×[1.20→0.60], shadow hues → 230°, highlights → 60°) + a hued outline dark + 2 neutrals |
| `automap/asset_creator.FAMILIES` | the family registry: per family a generator, substyles, accepted style tokens, allowed `materials`, per-size canvases, an `animation` spec, and the **descriptor** (`blocking`, `perspective`, `shadow`) that QC enforces against pixels |
| `content/props/props.json` (game repo) | the ledger: every asset with family/substyle/identity/style/provenance/frames/anchor/footprint |

Derived vaporis ramps (from the published `content/palette/palette.json`):
```
stone:     #423c39 #6c635c #9e988b #cac4b7 #f5f0e4  (outline #24211f)
bronze:    #330805 #531c05 #7a4f1f #9d743f #be9c68  (outline #1c0102)
verdigris: #1f3b32 #305f4d #548c73 #7ab495 #a5d9b9  (outline #10201c)
(+ foliage / foliage_dark / wood / water / earth from the classic attrs)
```

## Stage 1 — identity + ground atlases (instructions as run)

```
.venv/bin/python -c "…platform_specs.validate(identities/vaporis.json,
                     'visual-identity','2.4.0')"
.venv/bin/python scripts/13_scene_director.py atlas \
    --identity identities/vaporis.json                     # vaporis_terrain
.venv/bin/python scripts/13_scene_director.py atlas \
    --identity identities/vaporis.json --name vaporis_interior \
    --mechanics '{"stone": {"walkable": true}, "water": {"hazard": false}}'
```
The atlas generator (`automap/tiles2d.py`) renders 5 fixed classes
(grass/path/water/stone/bush) from identity colors, plus dual-grid
transition pieces; `--mechanics` overrides per-class walkable/hazard flags —
that's how the interior gets a WALKABLE marble floor and a harmless void.

## Stage 2 — procedural supply (trees: no prompts, pure code)

```
13 assets ensure --family tree --identity identities/vaporis.json \
    --substyle deciduous --min-variants 4        # → deciduous_7..10
13 assets ensure … --substyle pine --min-variants 2   # → pine_3..4
```
`ensure` = resolve fitness against the ledger (per family+identity+substyle;
manual touch-ups count) → paint only the gap with `trees_px` (sha-seeded
(material, band) index maps → `pixelart.resolve`) → automated QC → 2 sway
frames per leafy tree (`animate_px`) → stage + record the recipe in
`games/entropy/asset_requests.json` (committed, so `replay` regenerates
everything from text).

## Stage 3 — genlab supply (the image-model top): the ACTUAL instructions

One request per (family, substyle, size_class). For each:

**3a. request** — `13 assets request --family column --substyle piped
--size-class large --identity identities/vaporis.json` writes
`work/game/entropy/genlab/column_piped_large_r1/{request.json, prompt.md,
incoming/}`.

**3b. the prompt** (`prompt.md`, verbatim — this exact text is what a cloud
image model receives; its sha rides in provenance):

```
Traditional 16-bit pixel art sprite of a single Roman marble column
retrofitted with steampunk plumbing: a bronze pipe spiraling up the fluted
shaft with a small valve wheel, verdigris stains bleeding down the stone
from the fittings.

STYLE — strict traditional pixel art craft:
- crisp, deliberate pixel clusters; no anti-aliasing, no gradients, no noise
- banded shading: exactly 5 flat tones per material, hard steps between bands
- a dark, hue-shifted outline hugging the silhouette (sel-out), softened on
  the light-facing side
- texture built from small repeated shaded elements (leaf clumps, bark
  streaks), never airbrush

PERSPECTIVE: three-quarter top-down RPG view (a hybrid between top-down and
side view): the canopy mass is seen mostly from above, slightly squashed
vertically, while the trunk is clearly visible BELOW the canopy down to the
ground — the silhouette must read at a glance.

PALETTE — use ONLY these exact colors (identity "vaporis"):
- stone: #423c39 #6c635c #9e988b #cac4b7 #f5f0e4 (outline #24211f)
- bronze: #330805 #531c05 #7a4f1f #9d743f #be9c68 (outline #1c0102)
- verdigris: #1f3b32 #305f4d #548c73 #7ab495 #a5d9b9 (outline #10201c)

LIGHT: one fixed key light from the TOP-LEFT. Highlights face up-left,
shadow tones face down-right.

COMPOSITION:
- exactly ONE subject, centered, filling about 80% of the frame
- subject proportions close to 32:96 (it will be downscaled to a
  32x96 px sprite on a 32 px tile grid — keep forms chunky enough to
  survive that: trunk clearly wider than 3 px at final scale)
- plain solid background in a single flat color far from the palette
  (pure magenta #ff00ff), nothing else in frame
- NO ground/cast shadow (the game pipeline adds its own dithered shadow)
- no text, no watermark, no border, no photorealism, no 3D render look
```

Prompt anatomy (all machine-assembled by `genlab.compose_prompt`):
subject sentence per (family, substyle) from `genlab.SUBJECTS`; style block
fixed; perspective from the family descriptor via `PERSPECTIVE_TEXT`;
palette hexes from the live master palette restricted to the family's
`materials`; canvas + chunkiness from the family's `sizes`.

**Known prompt defects, visible above** (candidates for the improvement
round): the PERSPECTIVE paragraph is tree-worded ("canopy…trunk") for every
family; the STYLE texture line says "leaf clumps, bark streaks"
universally; "trunk clearly wider than Npx" leaks into non-tree prompts.

**3c. the references.** Since no image API is wired yet, the model was
stood in for by synthetic painters
(`<scratchpad>/ref_painters.py`): smooth anti-aliased gradient subjects on
flat magenta — deliberately everything pixel art is NOT. 16 refs for 12
requests. Real cloud references drop into the same `incoming/` folders and
supersede this quality level.

**3d. ingest** — `13 assets ingest [--req <id>] --identity …`. Per PNG:
1. IntentQC **stub** (recorded `{"status": "skipped"}` in provenance —
   the optional reference-vs-intent gate, deliberately not built yet);
2. **RePixel** (`automap/repixel.py`): subject mask (alpha or dominant
   border keying) → premultiplied BOX downscale to the family canvas →
   CIELAB nearest-palette palettize over the family's materials → 3×3
   majority material smoothing → per-material luminance re-band into the
   5 ramp bands → sel-out outline + dithered ground shadow → resolve;
3. **measurement** from pixels: anchor = lowest silhouette row; blocking
   footprint per descriptor (`trunk_base` = trunk mask; `base` = whole-mass
   contact rows, center = pixel CENTROID);
4. **QC gate** (`asset_qc.run_qc`, 8 checks): crisp_alpha,
   palette_membership, single_mass, outline, light_direction (bright
   quartile centroid up-left of dark), band_balance, grid_alignment,
   blocking_footprint. FAIL = not staged, reason logged;
5. animation frames if the family has them (band-drift on the mutable
   materials, silhouette/alpha locked) + `qc_frames`;
6. stage sprite + catalog entry + provenance sidecar + index-map archive
   (`provenance/<name>.npz` — the future re-animation substrate).

Catalog entry actually produced (verbatim, `piped_0`):
```json
{"file": "piped_0.png", "size": [32, 96], "frames": 1, "anchor_y": 92,
 "collision_r": 13.5, "footprint": {"center": [15.5, 92.0], "r": 13.5},
 "family": "column", "substyle": "piped", "identity_name": "vaporis",
 "style": "gen1", "generator": "genlab/1", "provenance": "generated"}
```

## Stage 4 — publish (stage 12) — what actually moves

Hash-guarded props copy (a published file whose hash differs from the
last-published manifest hash = hand-edited → preserved, provenance flips to
`manual`); catalog merge; then per tileset-flagged family
`pack_prop_atlas` shelf-packs published sprites (+ animation frames in the
columns right of each base tile) into `content/tilesets/<game>_<family>s.png`
+ `.tiles.json` (`props-tileset/2.0`); palette + levels + manifest last.
Order matters: atlases pack BEFORE the tilesets block publishes (a real
one-publish-behind bug found and fixed during this build).

## Stage 5 — bake (per-family painted layers)

`13 bake vaporis_lyceum vaporis_atrium` → publish → headless reimport →
`tools/bake_scene.gd`: one TileSet + y-sorted TileMapLayer per family
(TreesLayer, ColumnsLayer, …). Per tile, from measured meta only:
- `texture_origin = anchor_y − h/2 − 16` (anchor row lands on the painted
  cell's bottom edge — Godot draws multi-cell tiles centered on the cell,
  shifted by MINUS texture_origin);
- `y_sort_origin = 16 − FOOT_BIAS = −28` (sort_y = cell CENTER + origin =
  foot − 44, the character convention — both rules measured empirically);
- collision = 8-point ellipse at the measured footprint;
- `frames > 1` → Godot tile animation, 0.6 s/frame, RANDOM_START_TIMES.

## Stage 6 — the scene documents

`games/entropy/levels/vaporis_lyceum.json` (level@2.2, committed source of
truth): 64×40 ground grid as palette-mapped rows (g/p/w/s/b), 51 props BY
NAME at foot px, 2 parallax layers, 3 spawns, reciprocal teleports, 12
npc_slots. Authored via a zone-plan script
(`<scratchpad>/build_lyceum.py` — paints zones into a numpy char grid,
computes prop feet from cells; the "G5 helper" seed, not platform code).
Validated with `platform_specs.validate(..., 'level', '2.2.0')`; the
publisher additionally gates the teleport graph. Review:
`LEVEL=vaporis_lyceum CAMERA_POS=1024,640 CAMERA_ZOOM=0.5 SNAP_OUT=…
Godot --path <game> res://tests/level_snapshot.tscn` (+ zone close-ups at
zoom 1.4–1.6).

## Reproducibility map (what re-runs from what)

- **From committed text alone**: identity → palette → terrain atlases;
  procedural trees (recipes in `asset_requests.json`); level docs → bake.
- **Needs the reference images** (gitignored intermediates): genlab assets
  — `replay` re-ingests when `incoming/` still exists, else SKIPS and the
  published (hash-guarded) sprite remains the durable artifact.
- **Never regenerated over**: anything hand-edited in the game repo
  (hash guard → `provenance: manual`, and manual counts as fitting).

## QC rejection ledger from this run (every one a real catch)

| asset | check | root cause | fix applied |
|---|---|---|---|
| stump pair | set distinctness (IoU 0.94) | near-clone references | genuinely different 2nd stump (twin-trunk) |
| log | light_direction | pale sawn face on the away-from-light side | flip composition toward the key light |
| bench | blocking_footprint | two-legged base: centroid in mid-air between legs | `base` check = center within contact SPAN (+ measurement → centroid) |
| founder statue ×2 | light_direction | repixel re-bands PER MATERIAL: pale stone pedestal under dark bronze always reads bottom-lit | composition: all-bronze statue |
| boulder slab | light_direction | facet-tone lottery put a bright facet right | re-seed |
| first boulder set | set distinctness | same painter, same recipe | slab/monolith/cluster silhouettes |

## Known gaps carried forward (on top of the prompt defects above)

- IntentQC is a stub; API mode of the ImageGen box is a stub (drop-only).
- Ground classes are still a closed 5-vocabulary (steam vents deferred).
- Gear rotation can't be band-drift; machines shimmer instead of spin.
- Buildings are ground-tile pads + door teleports, not modeled structures.
- Early genlab recipe entries in `asset_requests.json` recorded
  `family: "tree"` for rock/stump requests (bug fixed mid-run; stale
  entries remain) and genlab recipes store absolute identity paths.
