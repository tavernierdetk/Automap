---
name: npc-director
description: >
  NPCDirector + NPCCreator surface: detail a scene's casting sheet
  (which archetype in which socket, with what dialogue) and build the
  missing people — creature docs with balanced stats + generated pixel
  figures. Use when the user wants to create an NPC, give one a sprite
  or dialogue, or work out who stands where in a scene.
---

# NPC Director (the sheet chair) + NPC Creator (the builder)

The NPC Director owns per-scene casting sheets under the Casting
Director's `games/<game>/casting/`; the NPC Creator builds the people
the sheet needs. Org context: `docs/studio-org.md` (ledger rows 7–10).
Door: `scripts/15_casting_director.py`.

## Detailing a sheet (NPC Director)

- Walk the scene brief zone by zone; every socket gets a PERSON WITH A
  REASON — the cook at the braziers, the dreamer at the pond. Arc
  beats' `archetype:*` roles bind first (they carry dialogue).
- Dialogue refs are optional; presence without conversation is fine
  for background life. Speaking parts get a dialogue-script@ doc in
  `games/<game>/dialogues/` and (if named) canon admission.

## Building a person (NPC Creator)

1. **Creature doc**: `15 npc create <slug> --name "…" --archetype
   <scholar|artisan|vendor|official|performer|laborer|child>` — stats
   are archetype-flavored, slug-jittered, and land in the admission
   band (25–27 total); `persona.region` feeds the R-005 gate;
   `visual.family` is `figure_px` (creature@1.1).
2. **Figure sprite** (the genlab twin for people — no shadow, no
   footprint, never in the props catalog):
   - `15 npc request <slug> --look "who this person is, visually"` —
     the look is SUBJECT text; write the composition into it for
     stubborn cases (children: state the shorter proportions).
   - `15 npc generate <slug>` (gpt-image-1) or drop a PNG into the
     request's `incoming/`.
   - `15 npc ingest <slug>` — repixel recreation at 64×96 (96 px figure
     contract), staged to `work/game/<game>/creatures_px/<slug>/Idle/`
     and registered in `assets.json` (`"local": true`); stage 12 builds
     the same manifest it builds for reference people.
3. **Look at the sprite** before casting it — read the staged PNG;
   doctrine applies (three-quarter top-down, front-facing, sel-out,
   palette-member). Regenerate with a sharper look line rather than
   shipping a mushy figure.

## Rules

- Sprites may be shared across BACKGROUND members only (sheet `sprite`
  field); speaking parts get their own face.
- Never hand-write a manifest — the publisher builds them from staged
  frames. Never stage into `content/` (published tree).
- Balance is not optional: totals outside the band mean picking the
  right archetype, not editing numbers.
