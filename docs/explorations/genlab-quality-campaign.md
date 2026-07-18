# GenLab quality campaign — image→recreation, human-in-the-loop (2026-07-17)

**Goal:** raise the quality of the image-generation → repixel-recreation
method by exercising it deliberately across a wide array of asset types,
with a human judging at every stage. The bronze machinery was the weakest
tier — it has been **removed from the inventory** (staging catalog,
recipes, published content; the baked mine_hall shows missing machines
until replacements land and it re-bakes). Every round both enriches the
library and improves the process: what a round teaches goes into prompts
(`genlab.SUBJECTS` / descriptors), the repixel passes, or QC — then the
next round tests the fix.

## The test batch (9 requests, staged in work/game/entropy/genlab/)

| request | tests | materials | why it's in the batch |
|---|---|---|---|
| `machine_cart_large_r2` | solid mass + wheels | bronze/verdigris/stone | re-prompted WITHOUT baked-in track |
| `machine_winch_large_r2` | thin cable + drum between pylons | bronze/verdigris/stone | fine linear detail at 64px |
| `machine_gearstack_large_r2` | repeated circular forms | bronze/verdigris/stone | gear teeth surviving downscale |
| `machine_boiler_large_r2` | large smooth cylinder | bronze/verdigris/stone | banding on a big curved surface |
| `portal_arch_large_r1` | NEGATIVE SPACE opening | stone/wood/verdigris | new family, 96px; arch must stay open |
| `portal_bricked_large_r1` | sealed flat plane | stone/wood/verdigris | texture without silhouette interest |
| `portal_shaftmouth_large_r1` | ground feature + pure-black hole | stone/wood/verdigris | the mine's missing focal anchor |
| `support_timber_large_r2` | post-and-lintel frame | wood | re-prompted without tree anatomy |
| `tree_deciduous_large_r2` | organic control | foliage/wood | baseline vs procedural px3 trees |

Coverage: bronze machinery (4 shapes), stone architecture (3 reads),
wood structure, organic — every master-palette material family, solid
masses vs negative space vs ground features vs canopies.

## The protocol, stage by stage — what to expect at each

### Stage 1 — the prompt (`<req>/prompt.md`) [done]
Machine-generated, deterministic (sha in provenance). Expect: subject
sentence with the family's OWN anatomy (S4 — no tree language outside
trees), exact hex ramps from the vaporis master palette, three-quarter
perspective, top-left key light, magenta background, ~80% frame fill,
NO cast shadow.

### Stage 2 — reference generation [API, human-supervised]
`13 assets generate [--req <id>]` fills incoming/ via the configured
provider (gpt-image-1; key in `~/.automap/imagegen.json`, quality "high",
canvas matched to the sprite's aspect, generation.json archived). No
--req = sweep every request with an empty incoming/. Drop mode still
works for hand-picked references — the folders are the contract.
(2–4 candidates per request is ideal — the distinctness gate rejects
near-clones at ingest, and variety is the raw material.)
**What a keeper looks like:** one subject, centered, hard
magenta field around it; colors near the ramp (the palettizer snaps, but
far-off hues snap to the WRONG material); forms chunky enough to survive
the target size (read the COMPOSITION block); the family's read intact —
an arch you could walk through, a cart that would roll, gears that mesh.
**Discard on sight:** soft photographic light, 3D-render sheen, multiple
subjects, baked ground shadows, text/watermarks, filled-in negative space.

### Stage 3 — preview (`13 assets preview [--req <id>]`) [NEW this campaign]
Dry-run recreation: repixels every reference, runs the full QC gate,
writes `<req>/preview.png` — reference | recreated sprite (nearest-
neighbor, on dark ground) per row, QC verdict in the caption. **Stages
NOTHING** — judge freely, delete weak references, regenerate, re-preview.
**What to look for, in order:** (1) silhouette — does the subject still
read at a glance at sprite scale? (2) material mapping — bronze snapped
to bronze, not wood; verdigris only where the reference stained; (3)
outline — dark, hue-shifted, hugging the shape; (4) banding — flat tone
steps, not mush; (5) the family read — the arch's opening is alpha, the
shaft mouth's pit is black, wheels are round. QC FAIL lines name the
failed check (palette membership, footprint, silhouette) — a FAIL is a
reference problem more often than a pipeline problem; when it IS the
pipeline, that's a finding for the iteration log.

### Stage 4 — ingest (`13 assets ingest --req <id>`)
Commits what survived: repixel again through the SAME gate, stage to
work/game/entropy/props/, catalog entry (style `gen1`), provenance
(index maps + shas) archived in the request, recipe recorded. Animated
families grow `.f1.png` frames here — machines: gearstack/boiler only
(cart/winch are cold by construction, S5). Expect per-file lines:
staged as `<substyle>_<n>` or QC FAIL with the reason. Idempotent — a
reference ingests once.

### Stage 5 — see them in the world
`13 bake vaporis_mine_hall` (publishes, then bakes — machines return to
the mine), then snapshot per the create-scene skill and judge against
the scene brief's acceptance reads. The character gallery equivalent for
props is the preview sheet; the scene is the real test.

### Stage 6 — iteration log (append below, every round)
Findings by layer: PROMPT (wording → SUBJECTS/descriptors), REPIXEL
(palettize/band passes), QC (gate too loose/strict), SIZE (canvas
budget). Fix, then next round through the same stages.

## Iteration log

### Round 1 — (open) first full pass over the 9-request batch
- API mode landed and validated on `machine_cart_large_r2` (gpt-image-1,
  high, 1024x1024): references followed the S4 prompt faithfully — no
  track stub, magenta field, palette-near colors — and arrived ALREADY in
  pixel-art style at high res.
- **REPIXEL finding — re-quantize degrades pixel-art references:** the
  model returns crisp pixel clusters; our resample+palettize smears them
  (verdigris drips blur, wheel spokes thin). When a reference is already
  grid-aligned pixel art, recreation should approach a clean integer
  downsample + palette snap, not a full repaint. Candidate: detect the
  reference's pixel grid pitch and downsample by exact factor first.
- **REPIXEL finding — material assignment by luminance overexposes
  stone:** pale warm ore chunks snapped to the stone ramp's near-white
  top bands (reads as eggs). Consider hue-weighted material assignment
  or capping the top band's share per material.
- **QC finding — blocking_footprint on squarish masses:** cart gen_0
  failed with fitted r 24 vs base half-width 19; the radius fit
  overshoots compact square bases. Revisit `measure_prop_meta` r-fit vs
  the `base` blocking branch.
- Full-array verdicts (18 references, all 9 requests previewed):
  - **PROMPTS (S4) vindicated everywhere**: cart has no track stub, timber
    has no tree anatomy, the arch's opening survived as negative space,
    the shaft mouth reads as a curbed black pit, per-family motifs show.
    gpt-image-1 at high quality returns near-final pixel art — the image
    model is NOT the bottleneck.
  - **REPIXEL is the bottleneck**, failures ranked: (1) fine detail dies
    in resample (rivets, gear teeth, wheel spokes, gauge — the boiler's
    light_direction QC FAILs are banding collapse, QC judging correctly);
    (2) material mis-assignment — warm sandy stone lands in wood/bronze
    ramps (winch pylons), brightest bands overused (white blotches on
    stone, milky tree canopy); (3) reference baked shadows bleed through
    negative space (arch gen_0, timber gen_0 openings).
  - Family ranking, best→worst recreation: tree ≈ portal (96px budget
    pays) > timber > cart/winch > gearstack > boiler (curved bronze +
    fine detail = worst case).
  - QC: blocking_footprint r-fit overshoots square bases (cart gen_0);
    light_direction confirmed as a genuine banding-collapse detector.

### Round 2+3 — repixel + QC fixes, same references (landed 2026-07-17)

Implemented (all four planned fixes, plus one QC calibration found during
re-preview):
1. `downscale` → DOMINANT-color reduce (mode per cell, mean within the
   winning quantized bin) — mush fixed: rivets, gear teeth, spokes, the
   boiler gauge survive; verdigris drips keep structure.
2. `palettize` → hue-weighted ΔE (L×0.55) — winch pylons read as stone;
   side effect noted: desaturated bronze SHADOW pixels can speckle into
   stone (gearstack gen_1) — watch, don't fix yet.
3. `reband` → anchored to the observed band range — white blotches and
   milky canopies gone; trees keep honest mid-range banding.
4. `measure_prop_meta` base window aligned to QC's (7 rows) — cart gen_0
   footprint FAIL was an off-by-one between measure and check.
5. `check_light_direction` → judged within the DOMINANT material (pale
   stone footings no longer swamp the bronze body's read) + per-substyle
   descriptor resolution (`resolve_descriptor`) with
   `"lighting": {"shaftmouth": "ground_plane"}` — a radially-lit ground
   feature opts out of the up-left key-light rule.
6. Prompt hardened: background stays pure #ff00ff everywhere, including
   through openings (shadow keying heuristics were rejected — a neutral
   painted shadow is chromatically indistinguishable from stone; the
   human cull at stage 3 is the right defense).

Re-preview verdict (same 18 references): 17/18 QC PASS; the one FAIL
(gearstack gen_1, light low in its bronze mass) is a correct cull.
Benchmarks: boiler keeps copper banding + gauge; winch pylons are stone;
tree control unchanged-good. Recreation quality is now bounded by the
reference, not the pipeline.

**Round 1–3 close-out:** 17 assets ingested (machines ×7 rebuilt from
zero, portal family ×6 born, timber ×2, gen1 trees ×4), published, and
mine_hall rebaked with the pit-head finally whole (shaft mouth + winch
composition per the brief; bricked seal on the east stub). Soft findings
carried forward: gearstack_0 shimmer frame changed 19.7% of pixels (bound
15% — warned, attached); desaturated bronze shadows can speckle into
stone under hue-weighted palettize; portal props need pass-through
blocking before an arch can straddle a walkway (engine seam, not asset).
Next round when wanted: statue/brazier/fountain regeneration through the
same flow, ore re-reference (still reads pale), IntentQC as a VLM gate.

### Round 4 — new-biome stress test: the fair (2026-07-17, same day)

The whole corrected pipeline run end-to-end on an unseen biome
(vaporis_fair: 96×64, brief-first, new atlas vocabulary, new `canvas`
identity material, two new families ride/stall, 12 references → 10
assets, one bake). Findings:
- `grid_alignment` caught the DIRECTOR's own error (non-32px family
  canvases) — first time a gate fired on spec authoring, not pixels.
- gpt-image-1 ignored the magenta-background rule on most fair
  references (returned white); border-keying absorbed it silently —
  the mask path is provider-drift-proof.
- Human cull earned its keep once more: a tent reference with white
  gaps through the valance QC-PASSed but recreated fragmented — culled
  at preview, replacement generated for $0.25.
- NEW painter need: `hedge` — a connected leafy mass (rock's tiling
  behavior, clump's material); the clump painter renders hedge runs as
  dotted bush strings.
- The 160×224 ferris is the game's largest sprite; adaptive footprint
  r_max (target-width-scaled past 96px) worked first try.

### Round 5 — buildings, concept step, fair v2 (2026-07-17, same day)

- **Buildings module (bld1)** landed: `automap/buildings2d.py` assembles
  facade/cornice/roof pieces into whole multi-cell props (family
  `building`, prefab = variant 0); RECT footprints threaded through QC +
  both baker collision paths; procedural-generator dispatch in
  `ensure()`. First procedural family since trees — the dispatch seam
  held.
- **Concept step** landed and immediately earned its keep: the fair
  concept taught path-NETWORKS, cluster density, lantern rhythm, and
  perimeter belts — all encoded as brief Composition notes and visible
  in v2.
- **QC calibrations from the density batch**: light_direction gained a
  −3 tolerance band (centroid noise on small sprites is not
  bottom-light) and an `ambient` opt-out for albedo-striped substyles
  (bunting: cream-vs-red pennants are paint, not light). The sign's
  genuinely right-lit reference still culls — the check survives.
- **Sel-out wrap finding**: masks flush against the canvas bottom wrap
  their outline to row 0 via roll-based dilate; buildings keep a bottom
  margin now. Candidate generic QC: flag opaque row-0 pixels over
  non-contiguous masses.
- Next round candidates: column family regeneration (reads flat beside
  gen1 neighbors), statue/brazier/fountain refresh, ore re-reference,
  pass-through blocking for portals/door teleports, piece-atlas export
  for editor wall painting.

### Round 6 — the town: buildings-module acceptance vs the CT bar
(2026-07-17, same day)

Bourg-Vaporum (vaporis_town) built end-to-end: shop/inn prefabs
(storefront awning + display window; per-storey window rows), timbered
wall style, slate + verdigris roof variety, the `shopsign` genlab family
(5 trades, icon-first). Verdict vs SNES Chrono Trigger, recorded in the
brief: town STRUCTURE passes (square/well/shop-vs-house/roof variety);
the fidelity gaps are named — sign-icon material contrast (the one
high-payoff fix: bright enamel on dark boards recreates legibly,
wood-on-wood mushes), wall quoins/shutters, per-shingle roof texture,
door detailing, urban-tight spacing. Process findings: cross-family
substyle name collisions (`inn` building vs `inn` sign → `inn_2`);
32px sign canvases are below icon fidelity floor (64×96 minimum);
thin brackets lose their posts to largest-component masking.

**CT fidelity round (same day, round 6b):** the buildings painter
closed gap-list items 2–4 — shingled roofs (brick-offset cells, ridge
caps, eave flare, dormers), wall value structure + quoins + foundation
joints, stone sills + canvas shutters, stone-framed arched doors with
stoops — and the whole stock regenerated (fair + town rebaked). The
name-collision finding graduated to a fixed invariant:
`next_variant_start` (family-scoped counters, global name uniqueness)
after the sign's `inn_2` silently displaced the prefab inn to a jitter
variant. Buildings are family-`ambient` for light_direction (facades
are AO-lit by design; roof key-light is enforced by the painter).
Still open toward CT: sign-icon enamel contrast (round 2 of shopsign),
urban-tight town spacing, awning-roof texture for kiosks/pavilions.

### Round 7 — working FROM Chrono Trigger images: the Millennial Fair
(2026-07-17, same day)

First round grounded in the actual CT source (Leene Square map studied
as reference — scratchpad only, lessons extracted, zero pixels copied).
The study inverted our fairground model: CT fairs are BUILT — flagstone
floor, curb-edged lawn islands, canopy-wall enclosure, flower borders,
landmark tents, red pennant rhythm, terracing. Landed: `flagstone` /
`canopy` / `flowers` painters, the `curb` transition style (straight
architectural edging vs organic blends — noise amplitude drops with the
style), fair spec v3 + ground re-authored paving-first, arch monument
placed. Blocked mid-round: **OpenAI billing hard limit** — grand-marquee
and flagpole requests staged with prompts ready; re-add on unblock (also
blocks the shopsign enamel-contrast round). Named engine seam from the
study: ELEVATION — Leene Square is stepped (stairs, balustrades,
terraces) and our tile grammar has no vertical concept; a ledge/stairs
vocabulary is the next structural frontier, alongside urban-tight town
spacing.

### Round 8 — elevation v1 (2026-07-17, same day)

The seam the Millennial study named, closed as a tile-grammar
extension: `terrace` classes with relief `ledge` (masonry drop face,
foot shadow, lit lip), a `stairs` painter (aligned treads, no per-tile
phase), and **blocking transition pairs** — `blocks: true` rides
tiles.json and the baker walls those boundary tiles (masks 1–14) with
collision + walkable=false custom data; stairs cells interrupt the
pair's clean corners so no boundary tile spawns there and the cut
stays open. Collision still EMERGES from the atlas. The fair's wheel
court is the proof: raised terrace + grand south stair. Pending polish:
direction-aware ledge faces (tall south face, thin top rim);
multi-level stacking. Still blocked on billing: marquee, flagpoles,
sign-contrast round.

### Round 2 — original plan (for the record)
1. **Grid-pitch detection + integer downsample**: references arrive as
   pixel art at a coarse pitch; detect the pitch and box-downsample by
   the exact factor before palettizing — preserve the model's own crisp
   clusters instead of repainting them.
2. **Material assignment**: hue-weighted distance (not luminance-led),
   and cap the ramp's brightest band to a highlight-accent share.
3. **Shadow hygiene**: key out near-neutral darks touching the alpha
   boundary inside declared negative space (or harden the prompt's
   no-shadow rule with a red-flag line).
4. QC: fix blocking_footprint r-fit for compact square bases.
Success = same 18 references, preview sheets judged again; boiler and
gearstack are the benchmark cases.
