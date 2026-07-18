"""The game-shell gates (S1) — stat budget, economy sim, readability.

Contract from docs/studio-org.md rows 20/22-25/30 and the rulers in
games/entropy/systems.md: over-budget items, capped skills, unpriced
items, uncast keepers, dead shops, and unreadable themes are BLOCKED.
"""
import json
import shutil
from pathlib import Path

import pytest

from automap import economy, items, ui_gate

GAME = Path(__file__).resolve().parent.parent / "games" / "entropy"


def _errors(findings):
    return [f.message for f in findings if f.severity == "error"]


def _write(base: Path, rel: str, doc: dict) -> None:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc))


# --- stat-budget gate --------------------------------------------------------

def test_over_budget_equipment_is_blocked(tmp_path):
    _write(tmp_path, "items/big_ring.json",
           {"id": "big_ring", "kind": "accessory", "slot": "charm",
            "tier": 1, "modifiers": {"kinesthetic": 3}})  # budget t1 = 2
    assert any("budget" in m for m in _errors(items.check_items(tmp_path)))


def test_on_budget_equipment_passes(tmp_path):
    _write(tmp_path, "items/oak_charm.json",
           {"id": "oak_charm", "kind": "accessory", "slot": "charm",
            "tier": 1, "modifiers": {"kinesthetic": 2}})
    assert _errors(items.check_items(tmp_path)) == []


def test_consumable_with_modifiers_is_blocked(tmp_path):
    _write(tmp_path, "items/weird_tonic.json",
           {"id": "weird_tonic", "kind": "consumable",
            "use": {"effect": "heal", "amount": 10},
            "modifiers": {"lucidity": 1}})
    assert any("no modifiers" in m for m in _errors(items.check_items(tmp_path)))


def test_skill_over_cap_is_blocked(tmp_path):
    _write(tmp_path, "skills/nuke.json",
           {"id": "nuke", "name": "Nuke",
            "formula": {"atk_stat": "chaos_mastery", "atk_mult": 12.0}})
    assert any("cap" in m for m in _errors(items.check_skills(tmp_path)))


def test_skill_at_cap_passes(tmp_path):
    _write(tmp_path, "skills/surge.json",
           {"id": "surge", "name": "Surge",
            "formula": {"atk_stat": "chaos_mastery", "atk_mult": 8.0}})
    assert _errors(items.check_skills(tmp_path)) == []


# --- economy sim gate --------------------------------------------------------

def _economy_fixture(tmp_path, price_book, shops, rewards, gold=20):
    # levels + casting borrowed from the real fair (a real cast keeper)
    shutil.copytree(GAME / "levels" / "vaporis",
                    tmp_path / "levels" / "vaporis")
    shutil.copytree(GAME / "casting", tmp_path / "casting",
                    ignore=shutil.ignore_patterns("builds", "*.md"))
    shutil.copytree(GAME / "lore", tmp_path / "lore")
    _write(tmp_path, "design.json",
           {"id": "t", "starting_loadout": {"gold": gold}})
    _write(tmp_path, "items/tonic.json",
           {"id": "tonic", "kind": "consumable",
            "use": {"effect": "heal", "amount": 10}})
    _write(tmp_path, "economy/economy.json",
           {"currency": {"id": "brass_token", "name": "Brass Tokens"},
            "price_book": price_book, "shops": shops, "rewards": rewards})


def test_unpriced_item_is_blocked(tmp_path):
    _economy_fixture(tmp_path, {}, [], [])
    assert any("unpriced" in m for m in _errors(economy.check_economy(tmp_path)))


def test_uncast_keeper_is_blocked(tmp_path):
    _economy_fixture(tmp_path, {"tonic": 10},
                     [{"id": "ghost_shop", "level": "vaporis_fair",
                       "keeper": "duke_ferrando", "inventory": ["tonic"]}],
                     [{"source": "b1_porta", "amount": 5}])
    assert any("keeper" in m for m in _errors(economy.check_economy(tmp_path)))


def test_dead_shop_is_blocked(tmp_path):
    _economy_fixture(tmp_path, {"tonic": 999},
                     [{"id": "naso_salvage", "level": "vaporis_fair",
                       "keeper": "vendor_naso", "inventory": ["tonic"]}],
                     [], gold=20)
    assert any("affordable" in m for m in _errors(economy.check_economy(tmp_path)))


def test_healthy_economy_passes(tmp_path):
    _economy_fixture(tmp_path, {"tonic": 10},
                     [{"id": "naso_salvage", "level": "vaporis_fair",
                       "keeper": "vendor_naso", "inventory": ["tonic"]}],
                     [{"source": "b1_porta", "amount": 15}])
    assert _errors(economy.check_economy(tmp_path)) == []


def test_key_items_are_never_priced(tmp_path):
    _economy_fixture(tmp_path, {"valve": 50}, [], [])
    _write(tmp_path, "items/valve.json", {"id": "valve", "kind": "key"})
    msgs = _errors(economy.check_economy(tmp_path))
    assert any("never priced" in m for m in msgs)


# --- readability gate --------------------------------------------------------

def _ui_fixture(tmp_path, theme_over=None, tabs=("items", "save", "quit")):
    theme = {"font_size": {"default": 16},
             "colors": {"text": "#e8e0d0", "panel_bg": "#1b1a24",
                        "accent": "#ffd980"}}
    if theme_over:
        for k, v in theme_over.items():
            theme[k] = {**theme.get(k, {}), **v}
    _write(tmp_path, "ui/ui.json",
           {"theme": theme, "menus": {"pause_tabs": list(tabs)}})


def test_tiny_font_is_blocked(tmp_path):
    _ui_fixture(tmp_path, {"font_size": {"default": 9}})
    assert any("floor" in m for m in _errors(ui_gate.check_ui(tmp_path)))


def test_low_contrast_is_blocked(tmp_path):
    _ui_fixture(tmp_path, {"colors": {"text": "#3a3a44"}})  # ~dark on dark
    assert any("contrast" in m for m in _errors(ui_gate.check_ui(tmp_path)))


def test_missing_save_tab_is_blocked(tmp_path):
    _ui_fixture(tmp_path, tabs=("items", "quit"))
    assert any("save" in m for m in _errors(ui_gate.check_ui(tmp_path)))


def test_readable_ui_passes(tmp_path):
    _ui_fixture(tmp_path)
    assert _errors(ui_gate.check_ui(tmp_path)) == []


def test_contrast_ratio_sane():
    assert ui_gate.contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0)
    assert ui_gate.contrast_ratio("#777777", "#777777") == pytest.approx(1.0)
