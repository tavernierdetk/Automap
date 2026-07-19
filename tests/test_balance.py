"""Autosim admission gate tests: determinism, the chaos RNG's contracts, and
the calibration invariants the gate's usefulness depends on — the reference
cast must self-admit (an average character passes) while degenerate stat
blocks reject in the right direction.

Everything is seeded; a failure here is a real regression, never flake.
"""
import pytest

from automap.balance import (
    ATTRIBUTES, REFERENCE_CAST, ROLL_CLIP, ChaosRng, Envelope, Fighter, duel, evaluate,
)


def _block(**overrides) -> dict[str, int]:
    stats = {a: 5 for a in ATTRIBUTES}
    stats.update(overrides)
    return stats


# --- chaos RNG ---------------------------------------------------------------

def test_named_streams_are_independent_and_reproducible():
    a = ChaosRng(seed=1)
    b = ChaosRng(seed=1)
    # consuming an unrelated stream must not shift another stream's sequence
    for _ in range(50):
        a.roll("noise", loc=1.0, scale=0.3, alpha=2.0, clip=ROLL_CLIP)
    seq_a = [a.roll("dmg", loc=1.0, scale=0.3, alpha=2.0, clip=ROLL_CLIP) for _ in range(20)]
    seq_b = [b.roll("dmg", loc=1.0, scale=0.3, alpha=2.0, clip=ROLL_CLIP) for _ in range(20)]
    assert seq_a == seq_b


def test_rolls_respect_the_clip():
    rng = ChaosRng(seed=2)
    rolls = [rng.roll("dmg", loc=1.0, scale=5.0, alpha=8.0, clip=(0.25, 2.5))
             for _ in range(500)]
    assert min(rolls) >= 0.25 and max(rolls) <= 2.5


def test_skew_is_centered():
    # alpha must shape the tail, not shift the mean (chaos is not a damage buff)
    rng = ChaosRng(seed=3)
    rolls = [rng.roll("dmg", loc=1.0, scale=0.2, alpha=6.0, clip=(-10, 10))
             for _ in range(4000)]
    assert abs(sum(rolls) / len(rolls) - 1.0) < 0.02


# --- duel --------------------------------------------------------------------

def test_duel_is_deterministic():
    a, b = _block(kinesthetic=7), _block(terrain_control=7)
    results = {duel(a, b, seed=99) for _ in range(5)}
    assert len(results) == 1


def test_missing_attribute_is_an_error():
    stats = _block()
    del stats["lucidity"]
    with pytest.raises(ValueError, match="lucidity"):
        Fighter("x", stats)


# --- the gate ----------------------------------------------------------------

def test_verdict_is_deterministic():
    v1 = evaluate(_block(), seed=0)
    v2 = evaluate(_block(), seed=0)
    assert v1.win_rates == v2.win_rates and v1.admitted == v2.admitted


@pytest.mark.parametrize("seed", [0, 7, 42])
@pytest.mark.parametrize("name", list(REFERENCE_CAST))
def test_reference_cast_self_admits(name, seed):
    # the calibration invariant: every archetype is itself an admissible character
    v = evaluate(REFERENCE_CAST[name], seed=seed)
    assert v.admitted, v.summary()


@pytest.mark.parametrize("seed", [0, 7])
def test_maxed_block_rejects_as_too_strong(seed):
    v = evaluate({a: 10 for a in ATTRIBUTES}, seed=seed)
    assert not v.admitted
    assert any("too strong" in r for r in v.reasons), v.summary()


@pytest.mark.parametrize("seed", [0, 7])
def test_minimal_block_rejects_as_too_weak(seed):
    v = evaluate({a: 1 for a in ATTRIBUTES}, seed=seed)
    assert not v.admitted
    assert any("too weak" in r for r in v.reasons), v.summary()


def test_envelope_is_adjustable():
    # a hard-mode envelope admits what the default calls too weak
    weak = _block(creature_affinity=4, kinesthetic=4, terrain_control=4)
    default = evaluate(weak, seed=0)
    generous = evaluate(weak, seed=0, envelope=Envelope(overall=(0.05, 0.95), matchup=(0.0, 1.0)))
    assert generous.admitted or not default.admitted  # loosening never flips admit -> reject
    assert generous.overall_win_rate == default.overall_win_rate  # same evidence, different judgment


def test_summary_mentions_every_opponent():
    text = evaluate(_block(), seed=0).summary()
    for name in REFERENCE_CAST:
        assert name in text


# --- movement derivation -------------------------------------------------------

def test_deckhand_movement_is_the_engine_baseline():
    # The all-average block must land exactly on the historical constants, so
    # admitting an average character leaves the game feel untouched.
    from automap.balance import derive_movement
    assert derive_movement(_block()) == {
        "walk_speed": 6.0, "jump_velocity": 6.0, "turn_speed": 12.0}


def test_movement_is_monotonic_in_kinesthetic():
    from automap.balance import derive_movement
    lo = derive_movement(_block(kinesthetic=1))
    hi = derive_movement(_block(kinesthetic=10))
    assert hi["walk_speed"] > lo["walk_speed"]
    assert hi["jump_velocity"] > lo["jump_velocity"]
    assert hi["turn_speed"] > lo["turn_speed"]


def test_movement_range_stays_sane():
    # Extremes must stay playable: no crawling statues, no superheroes.
    from automap.balance import derive_movement
    slow = derive_movement({a: 1 for a in ATTRIBUTES})
    fast = derive_movement({a: 10 for a in ATTRIBUTES})
    assert 5.0 <= slow["walk_speed"] < fast["walk_speed"] <= 7.0
    assert 5.5 <= slow["jump_velocity"] < fast["jump_velocity"] <= 6.5


def test_movement_requires_full_stat_block():
    from automap.balance import derive_movement
    import pytest as _pytest
    with _pytest.raises(ValueError):
        derive_movement({"kinesthetic": 5})
