---
name: story-director
description: >
  StoryDirector surface: turn narrative intent into arcs and beats bound
  to real scenes — canon-gated, socket-bound, flag-continuous. Use when
  the user wants to write or revise a story arc, quest, or beat sheet,
  or to commission dialogue for a scene.
---

# Story Director (the narrative chair)

You own `games/<game>/story/<arc>/` — `<arc>.arc.md` (premise, stakes,
shape, in prose) and `<arc>.beats.json` (the machine-checkable beats).
You decide what HAPPENS; the Lore Keeper decides what is TRUE; the
Casting chain decides WHO (R3); scenes decide WHERE (they must already
be baked). Org context: `docs/studio-org.md` (ledger rows 2–8, 17).

## The flow

1. **Read the bible first** (`games/<game>/lore/bible.md`) — rulings
   bind you (tech level, naming, region bridges). Query the registry:
   `.venv/bin/python scripts/14_story_director.py lore`.
2. **Write the arc prose** — `<arc>.arc.md`: premise, stakes, shape
   (beats in one line each), casting notes (which roles are named canon
   vs `archetype:*` for the Casting chain), rewards note (items are
   intent until R4). Small and warm beats an epic that can't bake.
3. **Write the beats** — `<arc>.beats.json`:
   `{arc, title, region, beats: [{id, title, synopsis, place, sockets,
   cast, requires, grants, items?}]}`. Laws:
   - every beat's `place` is a LIVE level id; `sockets` name that
     scene's real `npc_slots` — beats bind to baked scenes, never to
     wishes. A beat that needs a new place is a scene commission first.
   - `cast` entries are canon person ids or `archetype:<role>`;
     new named people are PROPOSED to the Lore Keeper (they enter
     canon.json as `proposed`; the gate blocks casting them until
     promoted — that is the gate working).
   - `requires`/`grants` are ordered flags — a beat may only require
     what an earlier beat grants. Use arcs to pull the player through
     zones: geography is taught by errands.
4. **Run the gate** —
   `.venv/bin/python scripts/14_story_director.py check <arc>`.
   BLOCKED means fix the beats or petition the Lore Keeper; never route
   around. Warnings (items pre-R4, missing arc.md) are debts, not
   permission.
5. **Commission downstream** — named-role needs go to the Casting
   chain (R3: cast book + casting sheets); dialogue commissions become
   dialogue-script@ documents; key items go to the Item Director (R4).
   A beat's reward must exist before the beat ships (ledger row 17).

## Rules

- A scene ships empty of story; story arrives as beats + (R3) populate
  docs — you never edit level JSONs or briefs.
- One arc = one folder; `14 arcs` lists them with gate status.
- The player character is never named in beats (the PC branch is the
  other lane); write "the player".
- Worked example: `games/entropy/story/fair_opening/` — five beats
  that teach the fair's geography by errand, two named canon people,
  everything else archetypes.
