# The game-shell round — items, abilities, economy, menus, saves (2026-07-18)

Org phases **R4 (Items + Economy) + R5-Interface** executed in six
slices (plan: the game-shell plan of 2026-07-18). Every mechanic landed
as the platform's house type: **a committed document, a gate that
judges it, a thin engine reader that executes it.** The reference game
had almost none of this (no menus, items, currency, save UI — its
skills were hardcoded and unused), so this round was greenfield, not
fidelity.

## What exists now

| Piece | Document | Gate | Engine reader |
|---|---|---|---|
| Items (11: weapons/charms/consumables/the valve) | `games/entropy/items/` (item@1) | stat budget (Σ\|mods\| ≤ tier+1) | GameDocs → menus/equipment/battle |
| Skills (8 across the five stats) | `games/entropy/skills/` (skill@1) | formula caps (mult ≤ 8, status ≤ 60) | the generic executor in battle.gd |
| Economy (brass tokens, price book, 2 stalls, beat rewards) | `games/entropy/economy/` (economy@1) | economy sim (coverage, cast keepers, no dead shops/wallets) | ShopSession + shop_ui |
| Interface (vaporis theme, menus, HUD) | `games/entropy/ui/ui.json` (ui@1) | readability (font floors, contrast, required tabs) | UiTheme + Menus/menu_root + hud |
| Rulers | `games/entropy/systems.md` + design.json 1.1 | (they ARE the gates' constants) | Design.progression/equipment_slots/starting_loadout |
| Saves | — (a save is serialization) | — | 3 slots + legacy slot 0, one defaulted loader |

- **Battle**: ATB unchanged and bit-deterministic (the attack's RNG
  stream name is preserved); skills/items are menu actions; themed
  HP/ATB bars; floating damage.
- **Menus**: pause stack (input lock, never tree-pause) — Items /
  Equipment / Status+Abilities / Save / Quit; `effective_stats()` is
  the ONE truth menus and battle share.
- **Dialogue**: themed, with figure_px PORTRAITS (the 16 faces,
  re-quantized 96×144 from archived refs, zero API); effects grew
  item/gold/shop (dialogue-script@1.1).
- **The arc closes**: Naso's trade GIVES `bronze_valve` (canon item),
  Druso consumes it and pays 30 tokens — `14 check fair_opening` is
  clean, no warnings left.
- **QA**: `test_shell_loop` plays the arc's economy end to end headless
  (reward → valve → buy → equip → battle-with-skill → save slot →
  load); ci.sh runs 11 suites, ALL PASS.

## Debts (named)

- Item ICONS: the menu renders names only; the `icon` field waits for
  an icon asset family + a menu that draws them (Interface polish).
- Battle sprite layout floats above the backdrop horizon (pre-existing).
- Encounters/bestiary = the other half of R5, untouched by design.
- Shop UI/menu screens have no visual snapshot harness yet (function is
  headless-proven; taste verdicts pending a windowed UI snapshot rig).
- Exported builds need import metadata for published PNGs (standing).
