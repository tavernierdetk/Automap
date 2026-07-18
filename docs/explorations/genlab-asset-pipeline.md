# GenLab — the image-model top of the Asset Creator (2026-07-16)

## What it is

An alternative generation backend for the Asset Creator. Instead of painting
procedurally (`automap/trees_px.py`), we ask an image-generation model for a
very rich reference close to the end result, then recreate it as proper
pixel art. Everything below the generation step is SHARED with the
procedural backend: the family-agnostic QC gate (`asset_qc`), the
`props/1.1` catalog, the hash-guarded publish (touch-ups survive), the tree
tileset atlas, and the y-sort baking.

```
assets request  ->  PromptComposer (automap/genlab.py)
                    ONE rich prompt: master-palette hexes, 3/4 perspective,
                    canvas density, top-left key light, hard don'ts
                ->  work/game/<game>/genlab/<req_id>/prompt.md + incoming/
     [cloud image tool: paste prompt, save PNGs to incoming/]
assets ingest   ->  IntentQC (stub, records "skipped")
                ->  RePixel (automap/repixel.py)
                ->  measured meta (trees_px.measure_tree_meta — trunk pixels)
                ->  asset_qc gate (fail = not staged)
                ->  staged sprite, style token "gen1", + provenance sidecar
```

## RePixel: recreate as pixel art (ONE component)

Ordered passes: subject mask (alpha or dominant-border keying) →
dominant-color BOX downscale onto the family canvas → **palettize to
(material, band) indices** via nearest master-palette color in CIELAB →
majority-smooth material regions → per-material luminance re-banding (5
crisp bands) → sel-out outline + dithered ground shadow → resolve through
`pixelart.resolve`.

We deliberately did NOT split "palette identity" / "pixel fidelity" into
separate components. The separation that matters is **transform vs
validate**: one transformer, and the existing `asset_qc` as the single gate
both backends pass. Palette membership and crisp alpha hold BY CONSTRUCTION
because RePixel outputs index maps — the same representation the procedural
painters use — and are checked again by the shared QC.

## The swappable ImageGen box

Like ODM in the mesh pipeline: `drop` mode works today (prompt.md +
incoming/); `api` mode (`genlab.generate_via_api`, wired 2026-07-17 for
the quality campaign) fills incoming/ from a configured provider — first
provider is OpenAI `gpt-image-1` (canvas sized to the sprite's aspect,
quality from config, generation.json archived beside the request). Key
resolution: `IMAGEGEN_API_KEY`/`OPENAI_API_KEY` env, else
`~/.automap/imagegen.json` (`{"provider": "openai", "api_key": "..."}`,
chmod 600 — never in the repo). CLI: `13 assets generate [--req <id>]`
(no --req = every request with an empty incoming/). Either mode, the
contract is the same: PNGs land in incoming/, and preview/ingest neither
know nor care who made them. Reference images stay gitignored
intermediates — the published sprite is the durable artifact;
`assets replay` skips a genlab recipe whose references are gone.

## Animation-ready tilesets (frames)

- The family registry (`asset_creator.FAMILIES`) gained
  `animation: {kind, frames, mutable}` — the conceptual contract: which
  materials may move. For trees: foliage sways, trunk/outline/silhouette/
  footprint are LOCKED per frame.
- `automap/animate_px.py` generates frames in INDEX SPACE (band edits only,
  material untouched → identical alpha and collision by construction):
  highlights drift 1px + clump twinkles = leaves rustling. Works identically
  on procedural and genlab assets because both produce (material, band)
  maps. Dead trees have no mutable pixels and stay static.
- Files: `<name>.png` + `<name>.f1.png` … — each hash-guarded (touch up any
  frame). Catalog entries carry `frames: N`.
- `pack_tree_atlas` (schema `trees-tileset/1.1`) packs frames side by side;
  the baker sets Godot tile animation (0.6 s/frame,
  RANDOM_START_TIMES so a forest never pulses in sync).
- `asset_qc.qc_frames`: silhouette locked, palette membership, changed
  fraction in [2%, 15%] — a rustle, not a different asset.

## Verification

- Hermetic pytest (`tests/test_genlab.py`, `tests/test_animate_px.py`):
  the reference is SELF-GENERATED (a smooth, anti-aliased gradient tree —
  everything pixel art is not) and must pass the full QC gate after
  repixelization. No network, nothing binary committed.
- entropy-remade `tests/test_baked_scene.gd` asserts ≥9 animated tiles with
  random start times and static dead trees on the baked TileSet.

## Second family: rocks (2026-07-16) — the family-agnostic proof

`FAMILIES["rock"]` (substyles boulder/rock) is **genlab-only**: no
procedural painter — `ensure()` reports the gap and points to
request/ingest. What onboarding it forced out of the tree code:
per-family `sizes` on the registry, prompt subjects per substyle, and
`blocking: "base"` — the footprint measured from the WHOLE mass's contact
rows (`pixelart.measure_prop_meta`, center = pixel CENTROID of the base:
the midpoint of extremes lands in the valley of a multi-lobe slab). QC
gained the matching `base` branch (circle spans the base: neither wider
than the mass nor a token dot). Rocks don't animate (no `animation` key
→ frames stay 1) and place as Sprite2D props (the blob path), superseding
legacy `rock_*` blobs by variant numbering. The set-level distinctness
gate earned its keep immediately: it rejected three near-clone synthetic
references before better ones shipped.

## Per-family paintable tilesets + the last blobs retired (2026-07-16)

`pack_prop_atlas` (schema `props-tileset/2.0`) packs every tileset-flagged
family into its own editor-paintable atlas (`<game>_<family>s.png` +
`.tiles.json`); the baker builds one TileSet + y-sorted TileMapLayer per
family (TreesLayer, RocksLayer, StumpsLayer) — schema-guarded so ground
tilesets sharing the suffix are skipped. Third family **stump**
(stump/log, wood-only palette, base blocking) retired the last legacy
blobs: `rock_0-2`/`stump_0-1` pruned; every prop in every scene is now a
painted, hash-guarded, QC-gated tile. `props2d.py` + the `13 props` CLI
action are legacy from here. (Publish-order bug fixed on the way: the
tilesets block ran before the atlas pack, so published atlases trailed
the catalog by one publish.)

## Later (named, not built)

- IntentQC: a VLM judging the reference against the request intent
  (interface + provenance slot already exist).
- Additional API providers (Gemini / Stability) behind the same
  `imagegen.json` provider field (openai landed 2026-07-17).
- Sway kinds beyond foliage (water shimmer, grass ripple) — descriptor
  slots exist. Bush/grass-tuft families when a scene wants them.
