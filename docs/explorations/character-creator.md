# Character creator — conversation → admitted character (brief §9 step 4)

**Status: built (v1), 2026-07-12.** The platform's first LLM-fills-spec flow
and its first asset↔mechanics mapping in anger: a conversation produces a
`CharacterProfile v2`, an autosim validates its stat block, and only then does
the character enter the game — as the player, walking the B-world.

## The chain

```
conversation (Claude Code session, /create-character skill)
      │  fills, never renders
      ▼
godot/characters/<slug>.json          character-profile@2.0.0 — committed
      │                               source of truth (name/role/personality/
      ▼                               backstory + appearance + stats + seed)
scripts/10_create_character.py        the admission gate
      ├── schema check                platform-specs (bounds, shape)
      ├── autosim check               automap/balance.py — batch duels vs the
      │                               reference cast; win rates must land in
      │                               the difficulty envelope. REJECT = exit 1
      │                               + per-matchup evidence for the revise loop
      ▼
godot/profiles/<slug>.tres            the 1.0.0 appearance projection — the
      │                               same .tres a photo (stage C) or a hand
      ▼                               edit produces; stage A renders it unchanged
--play → game.tscn Body override      every published scene inherits the shell,
                                      so one edit survives every re-publish
```

## Decisions taken here

- **The v1 conversation surface is a Claude Code session** (the
  `/create-character` project skill), not an API CLI or a local model. Zero
  new infra; the LLM-boundary rule holds because the session can only produce
  the JSON and invoke the gate. The API-backed CLI arrives when asset-factory
  extracts.
- **The autosim is a mini-sim, not a port.** Per the reuse ledger: the AutoSim
  *pattern* rebuilt small (`automap/balance.py`), Entropy's ATB/status fidelity
  deferred to the combat module's own slice. Seeded named-stream chaos RNG
  (centered Azzalini skew-normal — alpha shapes the tail, never the mean),
  five attributes → hp/speed/attack/defense by flat linear formulas, short
  duels (~5–8 hits) so mismatches read as win-rate drift rather than 0/1.
- **Chaos mastery is variance + crit reach + a small explicit attack term.**
  First calibration had the skew silently buying mean damage (a hidden flat
  buff); centering fixed that, then chaos was worthless; a crit rule (far-tail
  roll ignores defense) plus 0.3 attack/point makes it a real, priced stat.
- **The balance surface is deliberately flat.** Big bases, small per-point
  terms: one attribute point moves overall win rate a few percent. A steep
  surface makes the propose→revise loop thrash (first calibration: 2 points
  swung 0.77→0.15).
- **The cast self-admits — and that is a test.** Every reference archetype
  (deckhand/brawler/trickster/warden), evaluated against the cast, lands in
  the envelope across seeds (`test_reference_cast_self_admits`). If a formula
  change breaks an archetype, calibration regressed.
- **The difficulty envelope lives in `balance.Envelope` for now** — overall
  win rate 0.35–0.65, no matchup outside 0.10–0.90, 60 bouts/opponent. It
  graduates into the game spec when that schema earns its version (the brief's
  gspec box).

## Proven on

**Marguerite à Théodore** (retired lighthouse keeper of La Grave): interview →
26-point block admitted at 0.42 overall (her 28-point draft rejected at 0.70 —
the revise loop working as designed) → `marguerite_a_theodore.tres` → lagrave's
player Body, verified headless (profile resource + traits on the instantiated
scene; game-layer test suite still ALL PASS). She walks the harbour she has
watched for thirty-one years.

## Follow-ups

- **NPC placement**: admitted characters as `game.json` NPC spawns (the world
  director already instances `character.tscn` figures — wire profiles/dialogue
  seeds through `npcs[]`).
- **Dialogue-tree generation** from personality/dialogue_seed — blocked on the
  dialogue-node schema (queued in platform-specs, extracted from
  entropy-integrated's de-facto format).
- **Stat block → Creature.tres** mapping for actual combat, when the combat
  module lands (the envelope/result pattern from entropy-integrated).
- **Party/cast admission**: evaluate a new character against the *game's* cast
  (other admitted characters), not just the reference archetypes.
