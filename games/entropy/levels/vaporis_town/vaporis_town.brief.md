# Scene brief — Bourg-Vaporum, the market town

**Status: source of intent, written before pixels.** The buildings
module's acceptance scene: a small town, fair-sized (96×64), whose whole
point is READABLE SHOPFRONTS — you know the apothecary from the smith at
a glance, the way SNES-era towns taught you to. **Quality bar: SNES
Chrono Trigger** — named deliberately in the acceptance reads: varied
rooflines, textured walls, trade signs with icons, lived-in street
clutter. Where the procedural buildings fall short of that bar, the
verdicts must say so precisely (that's this scene's test function).

## The place

The town that grew at the lyceum's gate: Bourg-Vaporum, where the
Order's suppliers, graduates who never left, and everyone who feeds,
clothes and arms a campus full of apprentice engineers keep shop. Brass
fittings on medieval bones — the Order's steampunk dignity filtered down
to shopkeeper scale.

A visitor walking in from the campus road should read, in this order:
1. **the square** — a cobbled town square with the old well at its
   center, the town's crossroads; every street leads here;
2. **the trades** — shopfronts FACING the square and main street, each
   announced by a hanging sign with its icon: mortar-and-pestle
   (apothecary), garment (tailor), crossed blades (weaponsmith), tankard
   (inn), scales (general goods). You could navigate this town without
   reading a word;
3. **the homes** — smaller houses down the side lanes, laundry-line
   domesticity; the town is lived in, not staged;
4. **the edges** — kitchen gardens, a duck pond, the tree line; town
   softens into country.

## Light & air

Daylight, warmer and lower than the fair — late-afternoon market light.
Chimney smoke implied by hearth braziers; the smith's corner glows
warmest (forge brazier). The pond corner (NW) reads cool and quiet.

## Zones, walked south to north

- **The gate (S center):** the campus road arrives; a lantern pair and
  a sign board. Teleport to/from the lyceum (one-way until the lyceum
  brief lands; logged). NPC sockets: gatekeeper, carter.
- **The square (center):** cobbled, the well at its heart (the portal
  `shaftmouth` — a stone well ring is a stone well ring; the mine's
  vocabulary earns an honest reuse), market clutter (crates, barrels,
  a stall booth), benches. NPC sockets: crier, market_goer ×2, elder.
- **Main street (E–W through the square):** the trades face it:
  - **Apothecary** (E of square): shop building, mortar-and-pestle sign,
    herb clutter. Socket: apothecary.
  - **Tailor / garments** (W of square): shop building, garment sign,
    fabric-bolt clutter (crates). Socket: tailor.
  - **Weaponsmith** (NE, its own yard): shop with slate roof, crossed-
    blades sign, forge brazier + anvil-read clutter (crates/barrel),
    the warm corner. Socket: smith, apprentice.
  - **General goods** (SE corner of the square): shop, scales sign,
    crate stacks. Socket: shopkeep.
- **The inn (NW of square):** the town's tallest building — TWO
  storeys, hip roof, chimney — tankard sign, benches and a picnic
  table out front, lanterns. Sockets: innkeep, patron ×2.
- **The lanes (N and S of main street):** houses (1-storey, mixed
  plaster and TIMBERED walls, mixed rooftile/slate), kitchen-garden
  hedges, laundry propped by clutter. Sockets: resident ×3, child.
- **The pond (NW corner):** ducks implied, reeds read via lawn rim,
  one bench. Socket: fisher.
- **The perimeter:** tree copses + hedge runs, gaps at the gate and a
  north road stub (future exit, spawn-tagged).

## Register

**Terrain classes** (`games/entropy/atlases/vaporis_town.spec.json`):
- `lawn` — village green, walkable, THE transition base;
- `street` — grey cobble (square + main street), walkable 1.15;
- `lane` — packed dirt side lanes, walkable 1.1;
- `water` — pond, hazard, animated 3 frames;
- `hedge` — clipped garden walls (hedge painter, raised);
- Transitions: street/lane/water/hedge, all over lawn.

**Assets reused:** shaftmouth (the well), clutter crates/barrels,
picnic sets, marble bench, standing braziers + lantern posts, sign_0
(A-frame board), trees, bunting (market square festivity, sparing).

**Buildings (module extensions this scene forces):**
- `shop` prefab — storefront read: wide display window + canvas awning
  band over it, door beside; 4 cells wide;
- `inn` prefab — 2 STOREYS (per-storey window rows — currently the
  assembler only windows the ground floor), hip roof, chimney;
- `timbered` wall style — dark beams over plaster (the medieval read
  CT towns lean on);
- `roofslate` material — cool slate alongside terracotta so rooflines
  vary across the town.

**New family — `shopsign` (genlab):** hanging trade signs on a bracket
post, ICON-first (no readable text — icons are the language):
`apothecary` (mortar & pestle), `garments` (folded garment/shears),
`smith` (crossed blades), `inn` (tankard), `general` (hanging scales).
Small canvas (32×64), wood + bronze + canvas materials.

## Composition notes (from concept views, 2026-07-17 — reference only)

- **Buildings CROWD the square, facades toward it** — urban spacing of
  1–2 cells between buildings around the square; the town reads as
  blocks, not scattered farmhouses. Lanes thread BETWEEN buildings.
- **Roof variety is tri-color**: terracotta / slate / VERDIGRIS-copper
  (the Order's metal — adopt verdigris as a third roof material in
  variant jitter; it ties the town to the campus).
- **The well owns a cobble circle** at the square's exact center;
  radiating paving reads outward.
- **Signs hang high on facades** in the concept; our bracket-post signs
  stand BESIDE doors — acceptable variant, keep them tight to the wall.
- Domestic edges: fence-and-hedge garden frames, laundry-line clutter,
  ducks on the pond (implied by composition, not assets, this pass).

## Motion

Living: forge + hearth braziers flicker; pond shimmers; trees sway.
Dead: buildings, signs (sign sway would be lovely — named as a later
animation kind, not this scene).

## Acceptance reads

- From the full-map view: the square + well is the town's obvious
  heart; main street reads E–W through it; rooflines VARY (terracotta /
  slate, hip/gable, 1- and 2-storey); the inn is the tallest thing.
- **The CT bar, judged honestly at play zoom:** each shopfront is
  identifiable by its sign icon alone; walls read textured (timbered vs
  plaster distinguishable); the street feels inhabited (clutter at
  doors, lanterns, benches). Name every place the procedural buildings
  fall short of Chrono Trigger fidelity — that list is this scene's
  deliverable as much as the map.
- Houses differ from shops at a glance (no sign, no storefront).
- The pond is irregular; gardens read as tended (hedge-framed).
- Every zone ≥ 2 NPC sockets; ≥ 18 total.

## Verdicts

(appended per snapshot run)

**2026-07-17 — first bake (buildings-module acceptance run):**
- square + well as the heart: PASS — the shaftmouth reads as a town
  well on its cobble circle; market clutter, benches, bunting inhabit it.
- rooflines vary: PASS — terracotta/slate/verdigris across shops and
  houses; the 2-storey slate inn is the tallest silhouette in town.
- shops ≠ houses at a glance: PASS — awning + display window vs plain
  facade; the storefront read works.
- trade signs as language: **PARTIAL** — the sign PROPS read (bracket
  post, board) and the smith's verdigris-on-wood blades read perfectly;
  apothecary/inn/general icons smudge at play zoom. ROOT CAUSE
  identified: icon legibility is a MATERIAL-CONTRAST problem — icons
  survive recreation when they contrast the board (verdigris/cream on
  dark wood), mush when wood-carved-on-wood. Round 2: re-prompt icons
  as bright enamel on dark boards.
- **The CT-bar gap list (this scene's deliverable):**
  1. Sign icons need material contrast (above) — the one fix with the
     highest identity payoff.
  2. Plaster walls read flat vs CT: want corner quoins, stronger eave
     shading gradient, colored shutters. (Timbered variants already
     carry their weight.)
  3. Roof courses are clean bands; CT shingles have per-tile texture,
     ridge caps, dormers. A `roof_texture` pass on the painter is the
     next buildings-module slice.
  4. Doors are plain dark rectangles; want frames, steps, arched
     variants.
  5. Building spacing is suburban; CT towns crowd. Next town pass:
     1-cell gaps, shared garden walls.
- process notes: substyle names collide ACROSS families (`inn` the
  building vs `inn` the sign → sign staged as `inn_2`) — variant
  numbering is substyle-scoped, not family-scoped; works but fragile,
  queued as a naming finding. 32px sign canvases fail icon fidelity
  (mortar → smudge, thin brackets lose their posts to
  largest-component) — 64×96 is the sign floor.

**2026-07-17, CT fidelity round (same session):** the painter grew the
CT vocabulary and the whole building stock regenerated through it —
- roofs: SHINGLED (brick-offset cells, lit tops, course lines), ridge
  caps with shadow line, eave flare with hard under-shadow, dormers;
- walls: value structure (deep eave shade → light low), corner quoins,
  foundation block joints; timbered variants unchanged-good;
- windows: protruding stone sills + colored canvas shutters;
- doors: stone-framed ARCHED doors with two-step stoops.
Gap-list items 2/3/4 CLOSED; item 1 (sign-icon enamel contrast) and
item 5 (urban-tight spacing) remain open. QC note: buildings are now
family-`ambient` for light_direction — facades are AO-lit by design
(eave shade up, light low) and the up-left centroid check misreads
that; the painter enforces roof key-light by construction.
- **naming invariant fixed for real**: the sign's `inn_2` had pushed
  rebuilt inn buildings to `inn_3+`, so variant 0 — THE PREFAB — was
  never built. Variant counters are now family-scoped with a global
  name-uniqueness guard (`next_variant_start`); the prefab inn stands
  in town as inn_0.
