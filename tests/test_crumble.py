"""Crumble engine: deterministic patterns, bounded erosion, walls never vanish."""
import numpy as np
import pytest

from automap.crumble import crumble_profile, fbm1d


def test_fbm_is_deterministic_and_bounded():
    a = fbm1d(200, np.random.default_rng(7))
    b = fbm1d(200, np.random.default_rng(7))
    assert np.array_equal(a, b)
    assert a.min() >= 0.0 and a.max() <= 1.0
    assert a.std() > 0.05                      # actually noisy, not flat


def test_profile_is_deterministic():
    a = crumble_profile(20.0, 10.0, 0.7, np.random.default_rng(3))
    b = crumble_profile(20.0, 10.0, 0.7, np.random.default_rng(3))
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])


@pytest.mark.parametrize("severity", [0.2, 0.5, 0.9])
def test_walls_crumble_but_never_vanish(severity):
    for seed in range(12):
        _, top = crumble_profile(18.0, 9.0, severity, np.random.default_rng(seed))
        assert top.min() >= 1.5                # the module's core guarantee
        assert top.max() <= 9.0 + 1e-9


def test_severity_scales_erosion():
    def eroded(sev):
        tops = [crumble_profile(18.0, 9.0, sev, np.random.default_rng(s))[1]
                for s in range(10)]
        return float(np.mean([9.0 - t.mean() for t in tops]))
    assert eroded(0.9) > eroded(0.4) > eroded(0.1)
    # severity 0 = pristine parapet
    _, top = crumble_profile(18.0, 9.0, 0.0, np.random.default_rng(0),
                             breach_chance=0.0)
    assert np.allclose(top, 9.0)


def test_positions_span_the_wall():
    s, top = crumble_profile(14.0, 6.0, 0.5, np.random.default_rng(1))
    assert s[0] == 0.0 and abs(s[-1] - 14.0) < 1e-9
    assert len(s) == len(top) >= 4
