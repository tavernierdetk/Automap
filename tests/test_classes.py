"""The class stat-budget gate (automap/classes.py) — NS2."""
import json
from pathlib import Path

from automap import classes

GAME = Path(__file__).resolve().parent.parent / "games" / "entropy"


def _errs(findings):
    return [f.message for f in findings if f.severity == "error"]


def _write(base: Path, cid: str, doc: dict):
    d = base / "classes"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{cid}.json").write_text(json.dumps({"id": cid, **doc}))


def test_committed_disciplines_pass():
    findings = classes.check_classes(GAME)
    assert _errs(findings) == []
    assert set(classes.load_classes(GAME)) == classes.ENTROPY_DISCIPLINES


def test_disciplines_map_to_the_five_stats():
    by_stat = {c["primary_stat"] for c in classes.load_classes(GAME).values()}
    assert by_stat == classes.STATS  # each stat has exactly its discipline
    assert classes.load_classes(GAME)["weaver"]["primary_stat"] == "chaos_mastery"


def test_over_budget_bonus_is_blocked(tmp_path):
    # borrow real skills so only the budget fails
    import shutil
    shutil.copytree(GAME / "skills", tmp_path / "skills")
    _write(tmp_path, "titan", {"name": "Titan", "primary_stat": "kinesthetic",
        "attribute_bonus": {"kinesthetic": 3, "terrain_control": 2},  # 5 > 3
        "ability_pool": ["attack"]})
    assert any("budget" in m for m in _errs(classes.check_classes(tmp_path)))


def test_phantom_ability_is_blocked(tmp_path):
    _write(tmp_path, "ghost", {"name": "Ghost", "primary_stat": "lucidity",
        "attribute_bonus": {"lucidity": 2},
        "ability_pool": ["attack", "necromancy"]})
    assert any("necromancy" in m for m in _errs(classes.check_classes(tmp_path)))


def test_bad_primary_stat_is_blocked(tmp_path):
    import shutil
    shutil.copytree(GAME / "skills", tmp_path / "skills")
    _write(tmp_path, "odd", {"name": "Odd", "primary_stat": "charisma",
        "attribute_bonus": {}, "ability_pool": ["attack"]})
    assert any("not a stat" in m for m in _errs(classes.check_classes(tmp_path)))
