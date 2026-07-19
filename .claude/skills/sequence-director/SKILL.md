---
name: sequence-director
description: >
  The Story Director's top tier: compose a narrative_sequence (sequence@1)
  — segments, a state ledger, a revelation plan — for prologue-scale arcs.
  Use when the user wants to author, transcribe, or revise a multi-segment
  sequence (a prologue, an act, a chapter that spans scenes and choices).
---

# Sequence Director (the Story Director's top tier)

You compose SEQUENCES — the tier above arcs. An arc's beats are one
segment's worth; a sequence stitches segments (playable exposition,
hubs, ritual choices, crises) into a prologue or act with a declared
STATE LEDGER (`persistent_outputs`/`hidden_outputs`) and a revelation
plan. Owned document: `games/<game>/story/sequences/<id>.json`
(sequence@1). Context: `docs/explorations/narrative-sequence-gap.md`.

## The governing principle — checklist, not wall

The sequence gate (`14 sequences`) distinguishes **"not built yet"
(warn)** from **"contradiction" (error)**:

- WARN — a scene, dialogue, or cast member that is declared-but-unbuilt
  (`to_author`, `unwritten`, `tbd`, `missing_core_design`). These are
  the LIVING CHECKLIST — the work remaining, routed to the right chair.
- ERROR — a genuine contradiction: a class outside the five
  disciplines, a segment producing an output the ledger never declares,
  a participant that is neither a declared character nor an existing
  creature nor a tbd placeholder.

A transcribed concept should pass (0 errors) while surfacing its whole
to-do list (many warnings). That is the point.

## The flow

1. **Read the source** and the canon (`14 lore`). Characters are cast
   from the Casting chain — a concrete participant with no creature and
   no `tbd` marker is an error.
2. **Write / transcribe** `sequence@1`:
   - `characters[]` — each maps to a creature slug (or `tbd: true`);
     `role` protagonist|major_npc|npc; `class` (fixed_choice for NPCs,
     allowed_choices for player-picked).
   - `disciplines` — the class vocabulary (shaper/steward/weaver/
     breaker/mentarch).
   - `state` — the LEDGER: `persistent_outputs` + `hidden_outputs`.
     Every segment's `produces`/`requires` must name declared outputs;
     every declared output should be produced by some segment (a
     warn-checklist until it is).
   - `segments[]` — `segment_type`, `status`, `location`
     (`level` when the scene exists — checked; `scene_role`/
     `location_id` only = a to-author warn), `participants`,
     `dialogue_refs`, `produces`/`requires`, `completion_trigger`,
     `next_segment`. Design prose (dramatic_function, exposition,
     character_beats…) rides along permissively — keep it, it is the
     brief for downstream chairs.
   - Design-prose blocks (`revelation_plan`, `continuity_rules`,
     `asset_requirements`, `dialogue_package`, `validation`) are
     faithful annotation, not machine-enforced — preserve them.
3. **Run the gate** — `14 sequences`. Fix ERRORS (contradictions);
   the WARNINGS are the commission list you route:
   - unbuilt scenes → Scene Director (a brief + bake);
   - unwritten dialogue → Dialogue Writer;
   - tbd cast → Casting chain;
   - design-blocked segments → the HUMAN (they are not build tasks).
4. **Hand off** — the sequence is the master checklist; work it down
   chair by chair. The runtime (SequenceRunner) arrives in NS1; until
   then a sequence is a validated design contract, not yet playable.

## Rules

- Never invent canon (Lore Keeper) or new people (Casting chain) — a
  sequence REFERENCES them.
- `status: missing_core_design`/`blocked` segments are the human's
  design decisions; the gate warns and moves on, never pretends to
  build them.
- The ledger is the spine — an output nobody produces, or a segment
  producing an undeclared output, is the sequence lying to itself; the
  gate catches both.
- Human-blocked design (the incident, the control model, naming, voice
  profiles) stays visible in `validation.completeness.blocked` — the
  document is the surface where those calls get made.
