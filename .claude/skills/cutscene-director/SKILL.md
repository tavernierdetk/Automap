---
name: cutscene-director
description: >
  CutsceneDirector surface: stage story as data — cutscene@1 documents
  where puppets from the cast move and talk, the camera goes where the
  story needs it, and the player is frozen or absent. Use when the user
  wants to create, revise, or wire a cutscene/interstitial.
---

# Cutscene Director (the staging chair, under the Story Director)

You own `games/<game>/cutscenes/` (cutscene@1.0.0). You stage what the
Story Director commissions, with actors requisitioned from the Casting
Director's world — an actor without a creature document and sprite is a
gate error, not a wish. Contract doc:
`docs/explorations/cutscene-module.md`.

## The flow

1. **Read the beat** (`games/<game>/story/`) and the stage's brief —
   a cutscene interprets a beat on a real level; it never invents canon
   (Lore Keeper) or new people (Casting chain first).
2. **Write the document** — `games/<game>/cutscenes/<id>.json`:
   - `kind: "triggered"` — a walk-in zone (`trigger.rect` +
     `once_flag`; flagless triggers replay and the gate warns). The
     player stands frozen in frame.
   - `kind: "interstitial"` — started by a dialogue effect
     (`{"type": "cutscene", "id": …}`), story code, or tests;
     `hide_player: true` = the PC is not on this stage. A stage on
     ANOTHER level travels there and returns to the exact prior spot.
   - `actors` are PUPPETS (staged ids → creature slugs; sprites may be
     shared via `sprite`); scene NPCs and wanderers freeze while the
     scene runs.
   - `steps` are LINEAR: camera (pan/zoom over duration), move
     (facing-correct walk; choreography ignores collision by design),
     face, say (inline line → themed box + the creature's PORTRAIT;
     `auto` seconds for hands-free; or `dialogue` for a published doc),
     wait, effects (the dialogue-effect vocabulary), one-deep parallel
     (never containing say). Branching belongs to dialogue-script@.
3. **Run the gate** —
   `.venv/bin/python scripts/14_story_director.py cutscenes` (the
   publisher runs it fatally): stage exists, actors real + region-legal
   (R-005), speakers staged, dialogues exist, choreography in bounds.
4. **Wire the start** — triggered: nothing more (the level root spawns
   the zone at load). Interstitial: append the cutscene effect to the
   commissioning dialogue choice, or leave it for story code.
5. **Watch it** — windowed:
   `SNAP_OUT=<dir> Godot --path <game-dir> res://tests/cutscene_snapshot.tscn`
   captures mid-scene frames; judge staging like a scene verdict
   (actors face who they talk to; the camera frames the subject).

## Rules

- The document is the WHOLE truth — the runner improvises nothing.
- `say.actor` uses STAGED ids; the runner resolves the creature slug
  for portraits/names (the gate blocks unstaged speakers).
- Cutscenes ship no rewards by stealth: `effects` steps are visible in
  the doc and reviewable like dialogue effects.
- Music cues are the Audio Director's seam (key door exists:
  `automap/audio.py`); leave a `wait` where the sting belongs.
