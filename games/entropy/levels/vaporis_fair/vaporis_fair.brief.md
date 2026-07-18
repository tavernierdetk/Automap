# Scene brief — La Foire Vaporum, the Lyceum's School Fair

**Status: source of intent, written before pixels** (the first scene
born entirely inside the corrected flow — brief → register → generate →
grid). The scale test: a VERY expansive fairground, 96×64 cells (4× the
mine hall), the largest map in the game.

## The place

Once a year the Order opens the great lawn west of the campus and builds
a fair for its students — half carnival, half engineering exhibition,
because the Order has never known the difference. Apprentices rivet the
rides together as coursework; the faculty judge the gondola welds before
anyone is allowed to board. For one week the lawn smells of oil, sugar
and cut grass, and the great wheel turns over everything.

A visitor walking in from the campus should read, in this order:
1. **the wheel** — a bronze ferris wheel high over the northeast, the
   fair's landmark, visible from every corner of the map; you navigate
   BY it;
2. **the midway** — one broad gravel promenade running the map
   north–south, flanked by striped canvas stalls; the fair's spine;
3. **breadth** — side paths peeling off to lawns and attractions in
   every direction: this is a GROUNDS, not a room; edges feel far away;
4. **the Order's hand** — the same Roman-steampunk dignity as the
   campus: columns flanking the entrance, a tiered fountain at the food
   court, statues watching the lawns. (Vocabulary import from the campus
   is DELIBERATE here — the fair is the campus in festival dress; the
   argument the mine had to make against columns runs the other way on
   the Order's own lawn.)

## Light & air

Full daylight — the vaporis surface identity's warm sun, the brightest
scene in the game. Festival warmth: red-and-cream canvas, bronze trim,
lantern posts staged for evening but unlit by day. The pond corner (SW)
reads cooler and quieter; the hedge walks (SE garden) read shaded. No
dark corners — menace has no socket here.

## Zones, walked south to north

- **The entrance plaza (S center):** cobble apron where the campus path
  arrives; two intact columns flanking the gate line, benches, a
  lantern post. Teleport to/from the lyceum's west path (lyceum-side
  reciprocity waits on the lyceum's own brief — one-way until then,
  logged in verdicts). NPC sockets: ticket_taker, prefect.
- **The midway (center spine, S→N):** a broad gravel promenade, stalls
  in two facing rows — striped tents, game booths, a high-striker; ore
  carts repainted as vendor carts stay OUT (mine vocabulary, wrong
  biome). NPC sockets: barker, vendor_sweets, vendor_games, crowd ×3.
- **The wheel plaza (NE):** the ferris wheel on a wide gravel circle,
  queue ropes implied by lantern posts, a brazier for the evening
  lighting ceremony. The wheel is the tallest sprite in the game and
  y-sorts over everything behind it. NPC sockets: operator, queue ×2.
- **The carousel green (NW):** the carousel pavilion on trampled lawn,
  benches around it, topiary accents. NPC sockets: carousel_keeper,
  child.
- **The food court (W center):** the tiered fountain at its heart,
  benches, braziers (cooking fires — the only flames lit by day),
  stalls at its rim. NPC sockets: cook, professor_lunching.
- **The pond walk (SW):** an irregular pond with a mossy—no: a REEDY
  rim (lawn transition, not mine moss), quiet benches, one statue.
  Hazard: water. NPC sockets: student_reading, couple.
- **The hedge garden (SE):** clipped hedge walks with topiary spirals
  and statues — the faculty's corner. NPC sockets: professor_strolling,
  gardener.
- **The perimeter:** tree line + hedges all around; the lawn runs to it.
  Side gates read as gaps in the hedge (future exits, spawn-tagged).

## Register

**Terrain classes** (atlas spec `games/entropy/atlases/vaporis_fair.spec.json`):
- `lawn` — trampled festival grass, walkable 1.0; THE base; every
  transition grounds on it;
- `midway` — warm gravel, walkable 1.15 (the promenade and side paths);
- `plaza` — grey cobble, walkable 1.15 (entrance apron, wheel circle,
  food court floor);
- `water` — pond teal, hazard, animated (3 phase frames);
- `hedge` — clipped canopy mass on lawn (clump painter), unwalkable —
  perimeter and garden walls;
- Transitions: midway-over-lawn, plaza-over-lawn, water-over-lawn.

**Assets reused:** intact columns, statues (robed + founder), tiered
fountain, standing braziers + lantern posts, marble benches, topiary
(sphere + spiral), deciduous trees (gen1 + procedural), boulders (two,
as lawn character).

**New families (both genlab, canvas material joins the identity):**
- `ride` — the engineering exhibits: `ferris` (large 160×224 — the
  landmark; lattice wheel, canvas gondolas, bronze hub) and `carousel`
  (medium 112×112 — striped canopy pavilion, brass poles). Rotation is
  impossible in band space (documented engine limit) — both are STATIC;
  the fair's motion lives elsewhere.
- `stall` — the midway system, scoped as a system: `tent` (large 96×96
  striped canvas), `booth` (medium 64×72 game counter with prize
  shelves), `highstriker` (small 40×88 tower, bell on top).

## Composition notes (from concept views, 2026-07-17 — reference only)

Studied `work/game/entropy/concepts/vaporis_fair/`. Concrete targets:
- **Paths are a NETWORK, not a spine with stubs**: orthogonal walks
  connecting every zone in a loop; small plaza aprons at junctions;
  stalls sit AT junctions and along edges, never floating.
- **Clusters, not singles**: every stall gets 1–2 satellites (picnic
  table, crates/barrel, lantern); density ≈ one prop cluster per 5–7
  cells along walks; open lawn only BETWEEN zones, deliberately.
- **Lantern rhythm**: posts every ~8 cells along the main walks
  (≈ a dozen across the map, not five).
- **Perimeter belt**: 2–3 cells deep of layered trees + hedge, gaps only
  at gates; corners densest.
- **Hedges are WALLS**: solid clipped masses (the maze garden), which the
  `hedge` painter must deliver.
- **Picnic sets** near the food court and pond (table + benches as one
  prop).

## Composition notes v2 (Millennial Fair / Leene Square study, 2026-07-17)

Studied the CT source directly (reference images in scratchpad only —
lessons, never pixels). What Leene Square does that v2 didn't:
- **The fair floor is BUILT**: flagstone paving nearly everywhere;
  grass exists as curb-edged ISLANDS inside the paving. (Adopted in v3:
  `flag` class + `curb` transition style; ground re-authored
  paving-first.)
- **Boundaries are architectural**: crisp stone curbs, not organic
  blends, wherever hardscape meets green. (Adopted: `relief: "curb"`.)
- **Enclosure is a canopy WALL**: layered treetop mass with shadow
  holes, trees in front for silhouette. (Adopted: `canopy` class.)
- **Flower borders** line walks and island edges. (Adopted: `flowers`
  overlay class.)
- **Tents are landmarks** (star-topped grand marquees) and **red
  pennant poles pulse the accent everywhere**. (PENDING: marquee +
  flagpole assets blocked mid-round by the OpenAI billing hard limit —
  positions authored, props to re-add on unblock.)
- **Terracing**: Leene Square is stepped — stairs, balustrades, raised
  terraces. NAMED ENGINE SEAM: the tile grammar has no elevation
  concept; a ledge/stairs vocabulary is a future slice, not a painter
  tweak.

## Motion

Living: brazier flames flicker (food court + wheel plaza); pond water
shimmers (3 tile frames); trees sway (they already do). Dead by
declaration: the ferris wheel and carousel do NOT move (band-space
cannot rotate — honest limit, logged); stalls are static canvas.
Evening lantern lighting is a StoryDirector event, not an asset state.

## Acceptance reads

- From the full-map view: the wheel dominates the NE skyline; the
  midway reads as one continuous N–S spine; the map reads as GROUNDS —
  distinct zones with lawn breathing between them, edges tree-lined.
- The midway's stall rows FACE each other across the promenade; no
  stall floats mid-lawn.
- The pond is irregular with a soft lawn rim; nothing reads as the
  mine's cold sump.
- Canvas reads striped red-and-cream, distinct from bronze and stone at
  a glance.
- At play zoom: walking the midway, the player passes IN FRONT of
  north stalls and BEHIND south stall canopies; the wheel's lattice
  towers over a player standing at its base.
- Every zone has at least two NPC sockets; the fair is a stage waiting
  for a story.

## Verdicts

(appended per snapshot run)

**2026-07-17 — first bake (the whole scene born in one flow pass):**
- wheel dominates NE: PASS — landmark visible full-map; at play zoom the
  224px wheel towers over the player. (Taste note: at 160×224 it could
  stand one size class bigger someday; not a fail.)
- midway spine + facing stall rows: PASS — one continuous N–S read,
  tents/booths/high-strikers face each other, nothing floats.
- GROUNDS read: PASS — zones breathe on open lawn, side paths peel off,
  edges tree-lined.
- pond: PASS — irregular, soft lawn rim, nothing reads mine-sump.
- canvas distinct: PASS — red-and-cream pops against lawn/bronze/stone.
- y-sort at play zoom: PASS at the wheel plaza and midway.
- NPC sockets: PASS — 19 across all seven zones.
- **FINDING — hedge reads dotted, not clipped:** the `clump` painter
  centers one bush per cell, so hedge runs render as strings of bushes
  with lawn showing between. A fairground survives it (reads as planted
  borders); a maze garden wants a true `hedge` painter — a connected
  mass like `rock` but leafy, edge-aware. Queued for the painter library.
- Wheel-plaza bareness at play zoom: deliberate — queue furniture is
  StoryDirector/decor territory, the plaza is its stage.
- Graph: one-way (fair → lyceum `gate`); the lyceum-side return teleport
  waits on the lyceum's own brief (the gate working as intended —
  publisher orphan warning acknowledged).
- Process notes: my initial family canvases (112×112, 64×72) violated
  the 32px grid and `grid_alignment` caught them — the gate catching the
  DIRECTOR's error, exactly as designed; gpt-image-1 returned white
  backgrounds instead of magenta on several fair references and the
  border-keying absorbed it without a finding.

**2026-07-17 — v2 (concept-guided densify + buildings + hedge walls):**
- path NETWORK: PASS — loops join every zone; no dead-end stubs.
- hedges as walls: PASS — the `hedge` painter tiles as one clipped mass
  with footing shadow; lone bushes moved to the `bush` (clump) class
  where a lone bush is meant.
- density: PASS — 120 props (was 62): stall clusters with crates/
  barrels/bunting satellites, picnic sets, lantern rhythm (~14 posts),
  perimeter copses of 2–4. Placement audit: no floating benches; the
  mid-lawn sphere and carousel bench face their zones; two NPC slots
  that landed in the enlarged pond were moved ashore.
- buildings: PASS — ticket-office house at the gate, pavilion at the
  food court, kiosks at wheel plaza + carousel green; roofs y-sort over
  the player; rect footprints block the facades (bake verified;
  runtime walk pending a play session).
- FINDING (fixed same-day): a mask flush against the canvas bottom row
  wraps its sel-out outline to row 0 (roll-based dilate) — buildings
  now keep a 3px bottom margin. Candidate QC check: no opaque pixels on
  canvas row 0 unless the mass touches it contiguously.
- Taste: the old `intact_0/1` columns read flat beside the new assets —
  column family is a regeneration candidate next campaign round.

**2026-07-17 — v3 (the Millennial Fair round):**
- BUILT floor: PASS — the fairground reads as a paved square with the
  attractions standing on worked flagstone; lawn islands sit inside it.
- curbs: PASS — crisp stone edging runs every lawn/paving boundary; the
  organic blends remain for water/canopy where organic is right.
- canopy enclosure: PASS at full map (solid green wall + fronting
  trees); slightly flat up close — a second clump scale is a cheap
  later polish.
- flower borders: PASS on island edges; sparse elsewhere — extend along
  the promenade edges next pass.
- landmarks: PARTIAL — arch monument placed; the grand marquee and the
  red pennant-pole rhythm are authored but BLOCKED on the OpenAI
  billing hard limit (two requests staged, prompts ready).
- terracing: logged as the engine seam CT still holds over us.

**2026-07-17 — v4 (elevation v1):** the seam closed same-day. New tile
grammar: `terrace` (relief `ledge` — masonry drop face with joints,
foot shadow, lit lip) + `stairs` painter + BLOCKING transitions
(`blocks: true` pairs wall their boundary tiles; stairs cells interrupt
the pair and stay open — collision emerges from the atlas, still never
authored per scene). The wheel court is now a raised terrace with a
grand south stair to the promenade and a west cut — the Leene Square
composition. Verdict: PASS at play zoom (face reads, stair reads, the
wheel dominates from height). v1 limits, named: the ledge face rings
ALL sides equally (CT draws a tall south face and thin top rim —
direction-aware faces are the polish pass); single-level only (terrace
stacking untested). Process note: the baker reads PUBLISHED levels —
`--no-publish` rebakes serve stale grids; always publish after level
edits.
