---
name: create-scene
description: >
  SceneCreationDirector surface: turn a prompt ("a rocky lakeshore east of
  the meadow") into a validated level@2 scene for a 2D game — brief first,
  then reusing the project's assets or generating new ones from its visual
  identity — then publish + bake it into an editor-editable Godot scene. Use
  when the user wants to create, extend, or restyle a 2D game scene/level/map.
---

# Create a scene (SceneCreationDirector, v1 surface)

You are the director: **you write the brief, fill `level@2.0.0`, the
pipeline validates it, the baker projects it.** Never write into the game's
`content/` tree (it is published), never hand-write a `.tscn` (it is baked).

## The flow

1. **Brief FIRST — intent before pixels.** Write (or load and revise)
   `games/<game>/levels/<id>/<id>.brief.md` (per-scene folder: the
   brief lives beside its level) with the user before any grid or
   asset work. The bake gate errors without it. A brief is never
   retro-authored (that inversion is what produced the mine_hall failures —
   finding F8). Sections, in order (mine_hall's brief is the worked
   example):
   - **The place** — the fiction, and the ordered "reads" a visitor gets
     (what they understand 1st, 2nd, 3rd). Vocabulary imports from other
     biomes (surface architecture underground, etc.) must be argued here,
     never inherited by default.
   - **Light & air** — palette mood; which corners are warm/cold/dark.
   - **Zones** — walked in order; each names its props and NPC sockets.
   - **Register** — three lists: terrain classes the ground needs (with
     mechanics + transition pairs), assets reused, assets to create.
     Asset requests are scoped as SYSTEMS (a track: rails + cart + spill),
     not isolated props.
   - **Motion** — what lives (flames, water) and what is explicitly dead.
   - **Acceptance reads** — the snapshot rubric, written before pixels.
2. **Concept — get a visual sense before authoring (default for new
   biomes).** `scripts/13_scene_director.py concept <id>` renders 1–2 wide
   views of the whole scene from the brief (ImageGen box; needs the brief —
   gated). Study them for COMPOSITION: density per zone, cluster shapes vs
   lone props, how paths breathe, where the eye rests. Write a
   `## Composition notes` section into the brief (concrete targets:
   "midway ≈ a stall every 6 cells", "trees in copses of 2–4"). Concepts
   are REFERENCE ONLY — never traced, never shipped (gitignored under
   `work/game/<game>/concepts/`); the notes are the durable artifact.
3. **Hand the Register to the Asset Director.** The brief's Register is
   a commission, not a to-do list you execute inline: invoke
   `/asset-director` (or follow `.claude/skills/asset-director/SKILL.md`
   when running solo) with the register. That chair audits the library
   (`13 library` — reuse before generate), fills genuine gaps liberally
   (atlas specs, `13 assets ensure/request/generate`), runs the preview
   bench, and holds doctrine custody (perspective, figure scale, shadows,
   lighting exemptions). You get back a filled register: every line
   mapped to a catalog entry. Quick orientation while writing the brief
   is still yours: `.venv/bin/python scripts/13_scene_director.py catalog
   --game <game>` shows atlases, families, and the level graph — use it
   to write an informed Register, not to bypass the audit.
4. **Verify the register is filled** before authoring the grid: rerun
   `13 catalog` and confirm each terrain class and prop the brief names
   now exists. A missing entry goes back to the Asset Director — never
   contort an existing class into meaning something else (grass is not
   moss; a bush is not fungus).
5. **Fill the level document** at `games/<game>/levels/<id>.json`. Its
   `intent` field summarizes the brief (the gate checks it exists).
   `kind: tilemap` for composable terrain, `backdrop` for a painted scene
   image from the background library. Layered scenes (level@2.2) compose
   depth back to front:
   - `parallax[]` — slow-scrolling backdrops (`motion_scale` < 1 = farther;
     `modulate` to fade/tint);
   - tilemap `layers` — the walkable ground (and flat decor);
   - `props[]` — free-standing catalog objects, placed by FOOT position,
     y-sorted with the player, blocking only at their footprint;
   - a backdrop `background` remains available for single-image rooms, and
     combines with props for interiors.
   Details:
   - grids are palette-mapped rows; think in silhouettes (paths that lead
     somewhere, water with a shore, blockers framing the space). Water
     bodies are painted as irregular blobs — never axis-aligned rectangles;
     vary the shoreline;
   - **connect the graph both ways**: add this level's teleports AND edit
     the neighbor level's JSON to teleport back (the publisher errors on
     unknown targets, warns on missing spawn tags);
   - place `npc_slots` wherever story could later live — generous, they
     cost nothing;
   - validate: `.venv/bin/python -c "import json,platform_specs;
     platform_specs.validate(json.load(open('games/<game>/levels/<id>/<id>.json')),
     'level','2.2.0')"` (2.2.0 for layered/props scenes; plain backdrops
     remain valid 2.0.0).
6. **Publish + bake:**
   `.venv/bin/python scripts/13_scene_director.py bake --game <game> <id>`
   (brief gate, then stage 12: schema + teleport-graph gates). Backdrop
   levels need no bake — the generic loader builds them.
7. **Look at it — and record the verdict.** Snapshot:
   `LEVEL=<id> SNAP_OUT=<abs>.png Godot --path <game-dir>
   res://tests/level_snapshot.tscn --resolution 1152x648`, read the PNG,
   and judge it against the brief's **acceptance reads** item by item.
   Then REVIEW ZONE BY ZONE at play zoom (CAMERA_POS on each zone,
   CAMERA_ZOOM 1.0): every prop must face or serve something — no
   floating benches, no orphan statues; fix placements before calling
   a read passed (the full-map view hides placement sins).
   Append a dated verdict block to the brief (`## Verdicts` — one line per
   read: pass/fail + what to change) so judgment accumulates instead of
   vibes. Iterate on the grid until the reads pass, then tell the user how
   to walk it (baked scenes load via Game.change_level automatically).

## Rules

- The committed sources of truth live in the scene's folder
  `games/<game>/levels/<id>/` — `<id>.brief.md` (intent) and `<id>.json`
  (spec); verdicts of taste come from snapshots
  judged against the brief's acceptance reads, not imagination.
- Re-baking a legacy scene that predates the brief gate means writing its
  brief first — that is the gate working, not an obstacle to route around.
- A scene ships EMPTY of story: npc_slots yes, NPCs/dialogue no —
  population belongs to the StoryDirector.
- Editor edits to baked scenes are legitimate (that's the point) but die on
  re-bake until the re-absorb slice lands — warn the user before re-baking
  a scene they may have touched.
