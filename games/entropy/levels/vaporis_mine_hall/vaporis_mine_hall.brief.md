# Scene brief — Puits Vaporum, the Central Hall

**Status: source of intent.** Retro-authored after the first run (2026-07-16,
finding F8 — the run went one-line-ask → grid with no brief), then revised
2026-07-17 through the correction plan
(docs/explorations/scene-generation-correction-plan.md): the mine now speaks
its own terrain vocabulary, and this brief is upstream of the second
generation, as a brief should be. The level JSON's `intent` summarizes it,
the zone plan implements it, and visual verdicts are judged against its
acceptance reads.

## The place

The mine the Lyceum Vaporum was built to serve — and then forgot. Two
generations ago the Order sank a shaft into the bronze-bearing rock west of
the campus and carved a central hall around it: half working pit, half
temple, because the Order has never known the difference. Then the vein
soured, the pumps were stopped, and the mountain began taking the hall back.

A visitor stepping off the adit stairs should read, in this order:
1. **carved space** — a room CUT from living rock, not built; raw stone
   walls pressing in on a packed-earth floor, roof props holding a ceiling
   we never see;
2. **the pit-head** — the hall's reason: a shaft mouth open in the floor,
   a winch straddling it, its cable dropping into real darkness;
3. **the track** — one straight cart run stitching shaft to entrance, the
   spine everything else hangs off; carts and ore stranded ON it;
4. **abandonment** — cold machines, ore nobody will ever smelt, water
   rising where pumps once held it back;
5. **the Order's hand** — confined to the founder's shrine: bronze, one
   column, a tended brazier. (Revision 2026-07-17: the nave's free-standing
   piped columns are CUT — surface-temple furniture scattered on a pit
   floor read as set dressing, not architecture. The Order's dignity lives
   in the shrine niche, and only there.)

## Light & air

Underground dark relieved by three warm pools: the entrance lanterns, the
shrine brazier, the pit-head lantern. Stone sits DARK and cool — wet grey
with warm lamplight falling across it. The sump corner reads cold: teal
water, saturated moss, no lamps. (Landed 2026-07-17: the mine's atlas spec
`games/entropy/atlases/vaporis_mine.spec.json` carries its own literal
colors — dark wall, black-green water, packed earth — instead of the
surface identity's sunlit terrain fields. No grass exists underground; the
word is not in this scene's vocabulary.)

## Register

**Terrain classes** (the atlas spec is the authority):
- `earth` — packed floor, walkable, the transition base for everything;
- `wall` — living rock, raised relief (footing shadow at every floor
  boundary), unwalkable;
- `water` — black-green, hazard, animated (3 phase frames);
- `moss` — walkable, slows slightly; rims the sump, creeps where damp;
- `rail_v`/`rail_h` — the track read, walkable, earth underlay.

**Assets reused:** boulders, ore heaps, founder statue, standing brazier,
gearstack, boiler, one intact column (shrine only), timber support frames,
standing lantern, winch, cart.
**To regenerate (requests staged, S4 prompts):** cart without its baked-in
track stub (`machine_cart_large_r2`), timber frame re-prompted without tree
anatomy (`support_timber_large_r2`).
**New family — portal:** `arch` (entrance), `bricked` (east gallery stub),
`shaftmouth` (the pit-head's anchor, missing since run 1) — requests
staged at `portal_*_large_r1`, 96px canvas.

## Zones, walked north to south

- **The shaft alcove (N):** the winch drum sits ON the open shaft mouth
  (the `shaftmouth` portal prop once its reference lands). Gearstack
  beside it, a lantern, timber portal frames at the alcove throat. The
  track begins here. NPC socket: foreman.
- **The nave (center):** the open carved hall — the track runs straight
  through it, shaft to entrance, visibly railed; carts and ore heaps sit
  ON the track line. No columns: the emptiness IS the read (a hall this
  size with nothing in it means everything was hauled away).
- **The cave-in (NW):** a corner the mountain already took: the wall
  BREAKS into the room (wall-class protrusion, ragged by transition),
  boulder pile and spilled ore at its toe.
- **The founder's shrine (W niche):** the founder in bronze, verdigris on
  his shoulders, ONE intact column, the brazier lit — the one tended
  corner, and the only Roman sentence in the room. NPC socket:
  shrine_keeper.
- **The flooded sump (SE):** black-green water risen over the low quarter
  — an IRREGULAR pool, the flood line following the floor's low points,
  never a drawn rectangle; moss thick at its rim and creeping toward the
  boiler; the cold boiler and its pump gear stranded at the waterline.
  Hazard: the water hurts. NPC sockets: engine_keeper, prospector.
- **The entrance (S):** a timber-framed corridor to the adit stairs,
  lantern-lit, teleport back to the lyceum's west path; the stone `arch`
  marks the threshold once its reference lands. NPC socket: drifter.
- **The east gallery stub:** a bricked-off continuation — one timber
  frame, one ore heap, a socket (surveyor) for whatever story wants a
  dead end; the `bricked` portal prop seals it once its reference lands.

## Motion

Living: lantern & brazier flames flicker; the sump water shimmers (landed:
3-frame tile animation, desynced starts). Dead: the winch and carts are
COLD by construction now (`static_substyles`, F6 closed for cart/winch).
Known gaps, named: the gearstack and boiler still inherit the machine
family's heat shimmer — a per-INSTANCE cold flag is a later seam (the
lyceum's live machines share these substyles); the water's transition rim
tiles don't animate (only full water cells do).

## Acceptance reads

- From the full-map view: the hall silhouette reads as carved; the
  pit-head as the focal point; the track as one continuous line shaft →
  entrance; the sump as a distinct cold corner with an irregular shore.
- Wall meets floor with a footing shadow everywhere — no straight
  atlas-grid cuts, no pale floating stone.
- Nothing green reads as lawn: moss hugs water and damp walls only.
- At play zoom: a player walking the track passes IN FRONT of north-side
  props and BEHIND south-side canopies/lintels (y-sort at the foot line).
- The cave-in reads as a MASS breaking the wall line, not decoration on
  the floor.

## Verdicts

(appended per snapshot run — one line per acceptance read: pass/fail +
what to change)

**2026-07-17 — first run through the new flow** (mine vocabulary atlas,
brief-gated bake):
- carved silhouette: PASS — footing shadows ground every wall run; the
  interior rock pillars read as left-standing masses, not floaters.
- pit-head focal: PARTIAL — winch + gearstack + lanterns anchor the
  alcove, but the shaft mouth itself is still absent (portal `shaftmouth`
  reference not yet dropped); the track just stops at the winch.
- track: PASS — one continuous read, shaft → entrance, carts and ore ON it.
- sump: PASS on shape (irregular shore, dark water, animated cells) /
  PARTIAL on rim — the moss reads brighter and wider than "black-green
  cold corner"; darken the moss color in the atlas spec and thin the ring
  on the sunless side.
- no lawn: PASS — green appears only at the sump rim and two creep dots.
- cave-in: PARTIAL — the wall protrusion breaks the line, but the boulder
  pile sits a half-cell shy of its toe; nudge boulders up-left so rubble
  touches rock.
- y-sort at play zoom: PASS at the entrance (player passes behind the
  south timber lintels).
- Regenerated-asset gaps: cart/timber/arch/shaftmouth/bricked prompts are
  staged (S4) but references not yet generated — current sprites are the
  r1 tree-templated ones; ore heaps read pale against the dark floor,
  revisit after the vaporis palette's stone ramp or a dirtier ore
  reference lands.

**2026-07-17, second bake (same session):** moss darkened in the atlas
spec ([0.13, 0.23, 0.11]) — the sump now reads as the cold corner; the
cave-in boulders nudged onto the wall toe — rubble meets rock. Both
PARTIALs above upgraded to PASS; remaining open items are the asset
references (shaft mouth, arch, re-prompted cart/timber) and the named
motion gaps.

**2026-07-17, third bake — genlab quality campaign assets landed:**
machines regenerated through the fixed repixel (rivets, gauge, spokes
survive; winch pylons read as stone), timber frames swapped to the
re-prompted variants (timber_2/3), and the pit-head is WHOLE: shaftmouth_0
under the winch at the track head (drum crests behind the rim, pit drops
black), bricked_0 seals the east gallery stub. Pit-head acceptance read
upgraded PARTIAL → PASS. Named gaps: the arch stays out of the scene —
portal props block at their base SPAN, so a doorway prop would wall off
the corridor it frames (pass-through blocking = engine seam); the
shaft-mouth ring reads pale against the dark hall (it is the focal point,
so arguably correct — revisit only if it fights the lamplight reads).
