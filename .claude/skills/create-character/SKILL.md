---
name: create-character
description: >
  Interview the user to create a game character, write a CharacterProfile v2
  JSON, and run it through the stage-10 admission gate (schema + autosim).
  Use when the user wants to create, revise, or admit a character — "make me
  a character", "new NPC", "je veux créer un personnage".
---

# Create a character (the Claude character creator, v1 surface)

You are the conversation that fills the spec. The contract you must produce is
`character-profile@2.0.0` (see `../platform-specs/schemas/character-profile/2.0.0.json`);
the LLM-boundary rule applies: **you fill a spec, the pipeline validates it —
you never write binaries or bypass the gate.**

## The flow

1. **Interview, don't interrogate.** A few conversational turns to get: who
   they are (name, role, a line of backstory), how they act (traits, voice,
   what they want), and how they look (the appearance fields — height, build,
   colors, hairstyle, glasses, facial hair). Offer concrete suggestions the
   user can veto; don't read a form aloud. If a reference photo exists in
   `input/CharacterReferences/`, offer stage C (`scripts/char_photo_to_profile.py`)
   for the appearance section instead of asking.
2. **Propose a stat block in character.** The five attributes (1–10 each):
   `creature_affinity`, `chaos_mastery`, `kinesthetic`, `lucidity`,
   `terrain_control`. Derive them from the fiction (a dockworker is
   kinesthetic, a lighthouse keeper is lucid). Balanced characters land near
   **total 25–27**; the gate rejects power fantasies and pushovers alike.
3. **Write the JSON** to `godot/characters/<slug>.json` (slug =
   `automap.character.slugify(name)`; accents flatten, spaces become `_`).
4. **Run the gate:**
   `.venv/bin/python scripts/10_create_character.py --character godot/characters/<slug>.json`
5. **If rejected, revise in the fiction.** The verdict names the failing
   matchups. Adjust the stats *while keeping them true to the character*
   (trade points, don't shave uniformly), tell the user what changed and why,
   and re-run. Loop until admitted.
6. **Offer to make them the player** (`--play` re-run): every published scene
   (e.g. lagrave) then renders them as the third-person body. To see it:
   `open godot/scenes/lagrave/sf_lagrave.tscn` in Godot, or the project's run
   flow.

## Rules

- Never edit the stat block after admission without re-running the gate.
- Never hand-write the `.tres`; stage 10 projects it from the JSON.
- The JSON in `godot/characters/` is the committed source of truth; verdicts
  in `work/characters/` are evidence, regenerate rather than trust.
- Keep the character's speech (dialogue_seed, voice) in the user's language;
  keep field values that are enums/numbers within schema bounds.
