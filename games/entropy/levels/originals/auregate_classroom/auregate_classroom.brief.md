# Scene brief — The Auregate Classroom

A constructed interior (level@2.2 tilemap + props), not a painted backdrop.
The prologue's first playable segment: Caden (player) with Vec and Isaac at
the back of a lecture room as Professor Wren introduces the Auregate and the
Road. The two required conversations complete the segment; the room is also
where the incident interstitial (`the_weirgate`) later plays over the same
tiles.

## The place

A stone lecture hall inside the Auregate — the school that reads the Road
and drills its students never to break ranks. The fiction is *scholarly
order under stone*: rows of desks facing a teaching wall, knowledge shelved
along the sides, one slate board carrying the day's warning.

The reads, in order:
1. **A room built to face forward.** Desks in neat rows all point at the
   front — the eye is marched to the teaching wall before it wanders.
2. **This is a school of the arcane, not a barracks.** Bookcases of worn
   tomes and potion glass line the walls; a chalkboard carries diagrams.
   Stone, but lettered.
3. **Someone stands at the front, and you stand at the back.** The dais +
   lectern mark authority; the player spawns among the rear desks with the
   other two students — junior, listening.

## Light & air

Cool grey stone, warmed only where it must be: candle sconces down the side
walls throw small pools of amber onto the flags; the front dais is a warmer
oak tone than the cold floor. Corners are dark; the central aisle and the
dais are the lit path. No daylight — this is an inner hall.

## Zones (walked front to back)

- **The dais (front)** — a raised warm-oak platform the width of the
  teaching wall. Props: the **lectern** (Wren's, center), the **chalkboard**
  (behind/beside it). NPC socket: the professor, at the lectern.
- **The side walls** — **bookcases** (2–3 per side, against the wall) with
  **candle sconces** (braziers) between them. No sockets; texture + light.
- **The rows (middle→back)** — **desks** in two columns of three rows,
  facing the dais, a central aisle between the columns. NPC sockets: Vec and
  Isaac at rear desks (left and right of the aisle).
- **The back wall + door** — the aisle runs from the dais to a door at the
  back center (the teleport out, and where the player spawns).

## Register

- **Terrain classes** (new atlas `auregate_classroom`):
  - `flag` — cold stone flagstones, the walkable floor (mechanic: walkable,
    speed 1.0). Base of every transition.
  - `dais` — warm oak platform at the front (walkable, speed 1.0).
  - `aisle` — a runner down the center (walkable, speed 1.0) — a lit path
    read, tonal only.
  - `wall` — stone perimeter blocker (rock painter, relief raised; not
    walkable). Transition pair: base `flag`, overlay `wall`.
- **Assets to create** (new `furniture` family, genlab):
  - `desk` (wood, ×2 variants) — a sloped oak writing desk, wide-low.
  - `bookcase` (wood, ×2) — a tall shelf of tomes + potion glass.
  - `lectern` (wood, ×1) — a slanted reading stand with an open tome.
  - `chalkboard` (slate + wood, ×1) — a slate board on an A-frame.
- **Assets reused**: `brazier`/`standing` (wall candle sconces — generate if
  the entropy catalog lacks a variant).

## Motion

Alive: the candle sconces flicker (brazier flame frames). Dead: everything
else — desks, cases, board, lectern are still. This is a held, quiet room.

## Acceptance reads (rubric, written before pixels)

1. From the spawn (back door), the eye is pulled straight down the aisle to
   the lit dais — the room faces forward.
2. Two columns of desks, three rows each, all facing front, a clear central
   aisle between them — no desk floats, none blocks the aisle.
3. The dais reads as authority: warmer oak floor, lectern centered, slate
   board behind. The professor socket sits at the lectern.
4. Bookcases line the side walls with sconces between them; the corners are
   darker than the aisle.
5. The player collides with walls, desks, cases, lectern, board (footprint
   blocking) but walks the flags, dais, and aisle freely; the back door
   teleports out.
6. No seam of raw stone box: walls meet the floor with a footing shadow
   (raised relief), the room feels built, not tiled.

## Verdicts

### 2026-07-19 — rebuilt as a constructed tilemap scene (was a backdrop)
Full-room snapshot at 0.85 zoom, populated via the casting sheet:
1. Aisle→dais read — **pass**. The brown runner pulls the eye from the
   player at the back straight to the oak dais, board, and lectern.
2. Two columns × three desks, clear aisle — **pass**. No desk floats or
   blocks the aisle.
3. Dais authority — **pass**. Warm oak platform; chalkboard mounted at the
   front wall, lectern before it, the professor on the dais beside it.
4. Bookcases + sconces line the walls — **pass**. Two cases per side, a
   flaming sconce between; corners darker than the lit aisle.
5. Collision — **pass** (structural): walls are non-walkable tiles (auto
   polygons), furniture blocks at its footprint; flags/dais/aisle walkable.
6. Built, not boxed — **pass**. Raised-relief walls carry a footing shadow.

Cast (casting sheet, gated): professor→auregate_professor (instruction),
student_left→vec (peer banter), student_right→isaac. Story note: the brief
names the teacher "Professor Wren"; the wired teacher creature is the
generic `auregate_professor` (Wren, `professor_wren`, is the named figure
who intervenes in the incident) — a StoryDirector reconciliation for later.
New assets this pass: the `furniture` family (desk/bookcase/lectern/
chalkboard) + the `auregate_classroom` floor/wall atlas + a `slate` material.
