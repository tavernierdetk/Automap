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
   band (25–27 total); `persona.region` feeds the R-005 gate
   (creature@1.1).
2. **The body — ULPC channel (DEFAULT: composed, fully animated).**
   `visual.family: "ulpc"`. Author the committed build spec at
   `games/<game>/casting/builds/<slug>.ulpc.json` (ulpc.build/1.0),
   then `15 npc compose <slug>` → walk/idle/run in four facings staged
   + registered with per-anim fps. The bridge contract
   (docs/explorations/ulpc-casting-integration.md):
   - categories are DISK layer paths from the vendor's spritesheets/
     tree (e.g. `torso/clothes/longsleeve/longsleeve/male`), variants
     are FILE STEMS (`forest_green`, not "forest green");
   - only `walk` is composed (every layer ships it — native idle/run
     strips clothing); `Idle_*` = stance frame, `Run_*` = cycle at 10
     fps, front/back swapped to engine facing — all by the bridge;
   - layers with `bg/fg` split sheets (braid, bunches hair) don't
     resolve — pick styles with per-animation dirs (bob, bangsshort,
     pigtails);
   - stature: LPC `child`/`teen` body types, never canvas headroom.
3. **The face — figure_px channel (one-off generated art).** For
   portraits and look development: `15 npc request/generate/ingest`
   (gpt-image-1 → figure quantizer at 64×96). Style law: one body
   family per scene — figure_px bodies never stand beside ULPC bodies;
   the fair's 16 generated faces are filed as future dialogue
   portraits (Interface chair, R5).
4. **Look at it** before casting — `15 library` renders the contact
   sheet; a bald or undressed compose means a layer silently dropped
   (check the compose WARNs, swap the layer).
5. **Behavior**: casting sheet entries take `behavior: "post"|"wander"`
   (+ `wander_radius` px). Wanderers stroll with facing-correct
   Walk/Idle animations and stop to talk.

## Rules

- Sprites may be shared across BACKGROUND members only (sheet `sprite`
  field); speaking parts get their own face.
- Never hand-write a manifest — the publisher builds them from staged
  frames. Never stage into `content/` (published tree).
- Balance is not optional: totals outside the band mean picking the
  right archetype, not editing numbers.
