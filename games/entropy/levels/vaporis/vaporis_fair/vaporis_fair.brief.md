# Scene brief — La Foire Vaporum (v5, the clean-slate rebuild)

**Status: source of intent, written before pixels.** The first scene of
the reorganized world (regional filing: `levels/vaporis/`), rebuilt from
nothing on the day the library, the figure-scale contract, the
three-quarter doctrine and silhouette shadows all became law. Its four
predecessors' verdict history lives in git and the campaign log
(rounds 4–12); this brief starts clean and owes them everything.

## The place

Once a year the Order opens the great lawn west of the campus and BUILDS
a fair on it — half carnival, half engineering exhibition, because the
Order has never known the difference. Apprentices rivet the rides
together as coursework; for one week the flagstone smells of oil, sugar
and cut grass, and the great wheel turns over everything from its
terrace.

A visitor walking in from the campus road reads, in order:
1. **the wheel** — front-on from its raised terrace, the fair's
   landmark, navigated by from every corner;
2. **the marquee** — the striped big-top anchoring the court's heart;
3. **a BUILT ground** — dressed flagstone underfoot, lawn only as
   curb-edged islands and the outer park;
4. **festival dress** — red pennant poles, bunting between stalls,
   striped canvas everywhere;
5. **the Order's hand** — columns at the gate, fountains at the food
   court, machines running hot on display.

## Light & air

Full daylight on pale stone — warm, festive; the pond corner cool and
quiet; the hedge garden shaded; the food court warmest (cooking fires).

## Zones, walked south to north

- **The gate (S):** flagstone apron off the campus road; regenerated
  columns flank the line, ticket house west, arch monument east,
  lantern pair, sign board. No world exits yet — the fair is the first
  scene of the rebuilt region (spawn-tagged for the lyceum's return).
  Sockets: ticket_taker, prefect.
- **The grand court (center):** the marquee at the heart; midway
  tent/booth rows flanking the axis with bunting, crates, barrels;
  high-strikers; curb-edged lawn islands with flower borders breathing
  between; pennant poles pacing the walks. Sockets: barker, vendor ×2,
  crowd ×3.
- **The wheel terrace (NE, raised):** the NEW front-facing ferris on
  lighter stone, ledge faces south, grand stair to the court; brazier +
  lanterns. Sockets: operator, queue ×2.
- **The carousel court (NW):** the carousel on its pad, kiosk, benches.
  Sockets: carousel_keeper, child.
- **The food court (W):** the regenerated fountain at center, picnic
  sets (front-facing, true shadows), cooking braziers, a vendor booth,
  pavilion at the rim. Sockets: cook, professor.
- **The machine show (SE):** gearstack + boiler on plinth lawns,
  running hot (alive), signs, clutter. Sockets: mechanicus, apprentice.
- **The pond (SW):** irregular, lawn-shored, one bench + picnic set.
  Socket: dreamer.
- **The hedge garden (E):** clipped walks, topiary, one statue.
  Sockets: gardener, stroller.
- **The perimeter:** canopy wall + fronting tree copses; south gate
  gap; west stub (future).

## Composition notes

Fresh concept views generated this rebuild (cap restored) — study for
density/clusters/axis; inherited law from the Millennial study stays:
paving-first, curbs not blends, clusters with satellites, lantern
rhythm ~8 cells, landmark visible from every gate.

## Register

**Terrain** (`games/entropy/atlases/vaporis_fair.spec.json`, v4 spec
reused — it already carries the full vocabulary): lawn, flag (curb),
terrace + stairs (ledge, blocks), midway, water (animated), hedge,
canopy, flowers, bush.
**Assets — all from the LIBRARY (`games/entropy/library.md`),
doctrine-clean:** marquee, tents, booths, high-strikers, bunting,
pennant flagpoles, sign; ferris (REGENERATED front-facing this
rebuild), carousel; buildings (ticket house, kiosks, pavilion);
machines (alive); fountain, benches + picnic sets, columns
(REGENERATED), statues, braziers, lanterns; clutter; portal arch;
topiary, trees, boulders.
**Regenerated for standards this rebuild:** bench marble, columns ×3,
ferris (was isometric-planed).

## Motion

Alive: fountain spray, pond shimmer, machine-show shimmer, brazier
flames, tree sway. Dead: rides (band space cannot rotate), stalls,
buildings.

## Acceptance reads

- The wheel reads FRONT-ON from its terrace — no isometric plane left
  anywhere in the scene.
- Every shadow follows its caster (picnic tables the tell).
- The ground reads BUILT; curbs at every lawn boundary; the ascent to
  the wheel terrace reads with its south ledge face and stair.
- Doors interior on every building; scale holds (doors ≥ the figure).
- Density per the concept: clusters with satellites, no floating props.
- ≥ 16 sockets across eight zones.

## Verdicts

(appended per snapshot run)

**2026-07-18 — v5 first bake (the clean-slate rebuild):**
- the wheel reads FRONT-ON from its terrace: PASS — the isometric plane
  is gone from the scene (the regenerated ferris_0's wheel is parallel
  to the frame; its red base mat reads as festival carpet — acceptable,
  noted for a later reference cull).
- shadows follow casters: PASS (picnic tables, bunting, barrels all
  shape-true).
- BUILT ground + curbs + ascent: PASS — inherited grammar intact.
- doors interior, scale holds: PASS (regenerated stock).
- density: PASS — marquee at the heart, satellites at every stall,
  pennant rhythm; hedge garden + pond soften the east and southwest.
- regenerated columns flank the gate in clean stone (substyle-scoped
  materials keep marble out of the bronze ramp).
- sockets: 20 across eight zones.
- Graph note: the fair is the rebuilt region's first scene — no exits
  yet by design; the lyceum returns later with its own brief.

**2026-07-18 — v5 populated (R3: the casting chain's first deployment):**
- all 20 sockets cast (`games/entropy/casting/vaporis_fair.json`; 16
  generated figure sprites + 3 shared student faces; populate gate
  clean). Zone reads at play zoom:
- gate: PASS — Cassia mid-gate, Felix at the ticket house with his
  ledger; both read as posted, not parked.
- grand court: PASS — Vox mid-shout under his own bunting; Prisca and
  Naso each AT a stall; crowd students break up the flagstone.
- wheel terrace: PASS — Druso at the wheel's base, queue students on
  the grand stair.
- carousel court: PASS with a note — Pippa reads properly CHILD-short
  (canvas-headroom stature works); Mirella overlaps the carousel pad by
  a few px — nudge her slot west a cell on the next grid pass.
- food court: PASS — Bassa behind the picnic table (reads as serving),
  Gaius by the fountain doing nothing, correctly.
- pond/hedge: PASS — Naia and Silvo/stroller give the quiet corners
  their one person each.
- dialogue: all five arc posts + nine flavor lines wired (ui_accept in
  trigger radius); arc flags mirror fair_opening beats.

**2026-07-18 — the game shell (R4 + R5-interface;
docs/explorations/game-shell-round.md):**
- the fair is now a GAME: brass tokens earned along the arc, Naso's
  salvage and Prisca's sweets are real shops (browse via dialogue),
  the bronze valve is a real key item (given at the stall, consumed at
  the wheel, +30 tokens gratitude), pause menus with items/equipment/
  status/save, dialogue boxes themed vaporis with the figure_px
  portraits, battle with data skills + consumables.
- `test_shell_loop` plays the arc's economy end to end headless: PASS.
- story gate `14 check fair_opening`: CLEAN (the R2 item warnings
  resolved by canon-admitting the valve).

**2026-07-18 — the sparring ring (battle module):**
- an encounter zone on the machine-show lawn (rect center 2144,1440 —
  seed 88, alpha+bravo as "coursework constructs on a field test"):
  step in and the battle system answers. Proven headless in
  test_shell_loop (fires once, right roster, right seed). Invisible by
  design for now — a painted ring/rope prop marking it is an Asset
  Director commission for the next fair pass.
