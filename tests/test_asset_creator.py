"""Asset Creator: variety-aware fitness, gap-only generation, touch-up guard."""
import importlib.util
import json
from pathlib import Path

from automap import asset_creator
from automap.trees_px import STYLE_TOKEN
from automap.pixelart import master_palette

IDENTITY = {"name": "t", "canopy_color": (0.22, 0.42, 0.2),
            "trunk_color": (0.34, 0.26, 0.18), "cliff_color": (0.47, 0.45, 0.43),
            "water_color": (0.16, 0.36, 0.44), "path_color": (0.56, 0.45, 0.31)}


def _game(tmp_path, catalog=None):
    game = tmp_path / "game"
    (game / "content" / "props").mkdir(parents=True)
    if catalog:
        (game / "content" / "props" / "props.json").write_text(json.dumps(catalog))
    (game / "project.godot").write_text("")
    return game


def test_empty_base_generates_full_request(tmp_path):
    game = _game(tmp_path)
    report = asset_creator.ensure(game, tmp_path / "staging", IDENTITY,
                                  "tree", "deciduous", 3, log=lambda m: None)
    assert len(report["generated"]) == 3
    staged = json.loads((tmp_path / "staging" / "props.json").read_text())
    e = staged["props"]["deciduous_0"]
    assert e["family"] == "tree" and e["style"] == STYLE_TOKEN and e["provenance"] == "generated"


def test_partial_base_generates_only_the_gap(tmp_path):
    have = {"props": {f"deciduous_{i}": {
        "family": "tree", "substyle": "deciduous", "identity_name": "t",
        "style": STYLE_TOKEN, "file": f"deciduous_{i}.png"} for i in range(2)}}
    game = _game(tmp_path, have)
    report = asset_creator.ensure(game, tmp_path / "staging", IDENTITY,
                                  "tree", "deciduous", 5, log=lambda m: None)
    assert len(report["generated"]) == 3          # 5 wanted - 2 have
    assert "deciduous_2" in report["generated"]   # indices continue


def test_fit_base_generates_nothing(tmp_path):
    have = {"props": {f"deciduous_{i}": {
        "family": "tree", "substyle": "deciduous", "identity_name": "t",
        "style": STYLE_TOKEN} for i in range(4)}}
    game = _game(tmp_path, have)
    report = asset_creator.ensure(game, tmp_path / "staging", IDENTITY,
                                  "tree", "deciduous", 4, log=lambda m: None)
    assert report["fit"] and "generated" not in report


def test_blobs_do_not_fit_but_manual_does(tmp_path):
    catalog = {"props": {
        "tree_0": {"file": "tree_0.png"},  # legacy blob: no family/style
        "deciduous_9": {"family": "tree", "substyle": "deciduous",
                        "identity_name": "t", "style": "OLDSTYLE",
                        "provenance": "manual"},  # artist touch-up: fits
    }}
    game = _game(tmp_path, catalog)
    r = asset_creator.resolve(game, "tree", "t", "deciduous", 2)
    assert r["have"] == ["deciduous_9"] and r["gap"] == 1


def test_publish_hash_guard_preserves_hand_edits(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "pg", Path(__file__).resolve().parent.parent / "scripts" / "12_publish_game.py")
    pg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pg)
    root = tmp_path / "root"
    (root / "games" / "g").mkdir(parents=True)
    staging = root / "work" / "game" / "g" / "props"
    staging.mkdir(parents=True)
    (staging / "a.png").write_bytes(b"GENERATED_V1")
    (staging / "props.json").write_text(json.dumps(
        {"props": {"a": {"file": "a.png", "family": "tree", "style": STYLE_TOKEN,
                          "provenance": "generated"}}}))
    game = tmp_path / "gd"
    game.mkdir()
    (game / "project.godot").write_text("")
    from typer.testing import CliRunner
    runner = CliRunner()
    r1 = runner.invoke(pg.app, ["--game", "g", "--game-dir", str(game), "--root", str(root)])
    assert r1.exit_code == 0, r1.output
    pub = game / "content" / "props" / "a.png"
    assert pub.read_bytes() == b"GENERATED_V1"
    # artist touches the published file
    pub.write_bytes(b"HAND_EDITED")
    r2 = runner.invoke(pg.app, ["--game", "g", "--game-dir", str(game), "--root", str(root)])
    assert r2.exit_code == 0, r2.output
    assert pub.read_bytes() == b"HAND_EDITED"          # survived republish
    assert "PRESERVED" in r2.output
    cat = json.loads((game / "content" / "props" / "props.json").read_text())
    assert cat["props"]["a"]["provenance"] == "manual"  # resolver counts it as fit


def test_animation_opt_out_per_substyle():
    """DEAD vs ALIVE is a substyle property (F6): a mine cart is cold metal
    everywhere — heat shimmer on it reads as haunting, not machinery."""
    from automap.asset_creator import animation_for
    assert animation_for("machine", "cart") is None
    assert animation_for("machine", "winch") is None
    assert animation_for("machine", "gearstack")["kind"] == "heat_shimmer"
    assert animation_for("tree", "deciduous")["kind"] == "foliage_sway"


def test_variant_counters_are_family_scoped_but_names_stay_unique():
    """The town-run collision: a shopsign named inn_2 must not advance the
    BUILDING inn counter (variant 0 = the prefab), yet no name may be
    minted twice across families."""
    from automap.asset_creator import next_variant_start
    live = {"props": {"inn_2": {"family": "shopsign"}}}
    # building inns start at 0 despite the foreign inn_2...
    assert next_variant_start(live, {}, "inn", "building", count=2) == 0
    # ...but a range that would collide with the foreign name bumps past it
    assert next_variant_start(live, {}, "inn", "building", count=3) == 3
    # same-family entries advance the counter normally
    live2 = {"props": {"inn_0": {"family": "building"},
                       "inn_2": {"family": "shopsign"}}}
    assert next_variant_start(live2, {}, "inn", "building", count=1) == 1
