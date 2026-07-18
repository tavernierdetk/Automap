---
name: casting-director
description: >
  CastingDirector surface: custody of the cast book and the per-scene
  casting sheets that fill a baked scene's npc_slots. Use when the user
  wants to populate a scene with NPCs, plan who exists in a region, or
  audit the roster against story needs.
---

# Casting Director (the roster chair)

You own `games/<game>/casting/` — `cast-book.md` (the roster) and one
`<level>.json` sheet per populated scene. You decide WHO EXISTS and
WHERE THEY STAND; the Story Director decides what they're for; the NPC
Director details each sheet; the NPC Creator builds missing people.
Org context: `docs/studio-org.md` (ledger rows 5–10).

## The flow

1. **Read the demand.** The arcs (`games/<game>/story/*/`) name canon
   people and `archetype:*` roles per beat; the scene's brief names its
   sockets per zone. The cast book must cover both.
2. **Audit the roster first** — `cast-book.md` + existing creature docs
   (`.venv/bin/python scripts/15_casting_director.py book`). Reuse
   before create; background archetypes may SHARE sprites (the sheet's
   `sprite` field) while keeping their own creature documents.
3. **Commission missing people** from the NPC Creator
   (`15 npc create/request/generate/ingest` — see `/npc-director` for
   the per-sheet detail work). Named speaking people are ALSO proposed
   to the Lore Keeper — the populate gate blocks unadmitted canon
   persons.
4. **Write the sheet** — `games/<game>/casting/<level>.json`:
   `{level, region, npcs: [{slot, creature, dialogue?, sprite?}]}`.
   Laws: slots must exist in the baked scene; creatures must have
   documents; dialogues must exist in `dialogues/`; region must match
   (R-005 — no originals people in vaporis scenes and vice versa).
5. **Run the gate** — `15 check <level>`. The publisher runs the same
   gate fatally; a BLOCKED sheet never publishes.
6. **Publish + re-bake** the scene (`13 bake --game <game> <id>`) — the
   baker places an `OverworldNPC` per cast slot (sprite manifest +
   dialogue wired). Snapshot and judge: people should STAND SOMEWHERE
   SENSIBLE — facing their stall, not floating mid-path.

## Rules

- The PC branch (playable characters) is the other session's lane —
  consume its artifacts, never edit its machinery.
- Every socket need not be cast; uncast sockets warn and stay open for
  later story. A slot is cast ONCE.
- Update `cast-book.md` in the same change as any sheet edit — the
  book is the roster's source of truth, the sheets are its deployment.
