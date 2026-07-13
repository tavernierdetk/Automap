"""Facade/roof/road tile generators: deterministic, tileable, shareable."""
import numpy as np
import pytest

from automap.facades import (
    SIZE, WINDOW_STATES, pick_window_state, road_tile, roof_tile, wall_tile,
)

WALL = (0.42, 0.31, 0.25)
TRIM = (0.35, 0.32, 0.28)
SOOT = (0.12, 0.11, 0.10)


@pytest.mark.parametrize("style", ["brick", "siding", "concrete"])
@pytest.mark.parametrize("state", WINDOW_STATES)
def test_wall_tiles_render_for_every_style_and_state(style, state):
    img = wall_tile(style, WALL, TRIM, SOOT, state, 0)
    assert img.size == (SIZE, SIZE) and img.mode == "RGB"


def test_wall_tile_is_deterministic_and_cached():
    a = wall_tile("brick", WALL, TRIM, SOOT, "boarded", 2)
    b = wall_tile("brick", WALL, TRIM, SOOT, "boarded", 2)
    assert a is b                                   # lru cache shares the image
    fresh = wall_tile.__wrapped__("brick", WALL, TRIM, SOOT, "boarded", 2)
    assert np.array_equal(np.asarray(a), np.asarray(fresh))


def test_variants_differ():
    a = np.asarray(wall_tile("brick", WALL, TRIM, SOOT, "dark", 0))
    b = np.asarray(wall_tile("brick", WALL, TRIM, SOOT, "dark", 1))
    assert not np.array_equal(a, b)


@pytest.mark.parametrize("style", ["tin", "membrane", "shingle"])
def test_roof_tiles_are_near_neutral(style):
    # roofs get their color from baseColorFactor: the tile must stay bright
    arr = np.asarray(roof_tile(style, 0), dtype=float) / 255.0
    assert arr.mean() > 0.7, f"{style} tile too dark to tint ({arr.mean():.2f})"


def test_road_tile_neutral_with_dark_cracks():
    arr = np.asarray(road_tile(0), dtype=float) / 255.0
    assert arr.mean() > 0.75
    assert arr.min() < 0.6                          # cracks actually read


def test_pick_window_state_respects_weights():
    rng = np.random.default_rng(0)
    picks = {pick_window_state({"boarded": 1.0}, rng) for _ in range(10)}
    assert picks == {"boarded"}
    picks = [pick_window_state({"dark": 1, "lit": 1}, rng) for _ in range(50)]
    assert set(picks) <= {"dark", "lit"} and len(set(picks)) == 2
    # empty/zero weights never crash
    assert pick_window_state({}, rng) == "dark"
