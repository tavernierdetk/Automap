"""Crumble — procedural decay patterns. The context→visuals engine.

The platform link this module embodies: a game's *context* (post-apocalyptic,
weather-worn, war-torn — carried by the visual identity's decay dials) turns
into *visuals* through deterministic noisy patterns, never through deleting
geometry. A damaged wall keeps standing with crumbled sections; it does not
vanish.

Deliberately geometry-free and dependency-light (numpy only): this module
emits PATTERNS — 1D erosion profiles today, 2D masks when a consumer arrives —
and renderers (automap.presentation, later terrain erosion, road cracking,
coastline nibbling) turn them into meshes or texels. That boundary is what
makes it a platform module: it incubates here per the module-boundary rule
and earns its own repo when a second consumer shows up.

Everything is deterministic for a given rng — same scene, same ruins.
"""
from __future__ import annotations

import numpy as np


def fbm1d(n: int, rng: np.random.Generator, *, octaves: int = 4,
          persistence: float = 0.55, base_freq: int = 4) -> np.ndarray:
    """Fractional Brownian value noise, n samples in [0, 1].

    Smoothstep-interpolated random lattices, halved amplitude per octave —
    the classic recipe, small enough to own rather than import.
    """
    out = np.zeros(n)
    amp, total, freq = 1.0, 0.0, base_freq
    for _ in range(max(octaves, 1)):
        lattice = rng.random(freq + 1)
        x = np.linspace(0.0, freq, n, endpoint=False)
        i = np.minimum(x.astype(int), freq - 1)
        t = x - i
        t = t * t * (3.0 - 2.0 * t)
        out += amp * (lattice[i] * (1.0 - t) + lattice[i + 1] * t)
        total += amp
        amp *= persistence
        freq *= 2
    return out / total


def crumble_profile(length_m: float, height_m: float, severity: float,
                    rng: np.random.Generator, *, segment_m: float = 1.2,
                    breach_chance: float | None = None,
                    min_height_m: float = 1.5) -> tuple[np.ndarray, np.ndarray]:
    """The eroded top edge of one wall: (positions 0..length, heights).

    Three superimposed patterns, all scaled by severity in [0, 1]:
    - a ragged fBm parapet (up to ~28% of the height gnawed off),
    - corner bites (walls crumble from their free ends first),
    - at most one breach — a deep gaussian notch, the collapsed section —
      whose chance grows with severity.

    Heights never drop below min_height_m: sections crumble, walls never
    disappear. That floor is the design decision this module exists for.
    """
    severity = float(np.clip(severity, 0.0, 1.0))
    n = max(int(np.ceil(length_m / max(segment_m, 0.2))) + 1, 4)
    s = np.linspace(0.0, float(length_m), n)

    top = np.full(n, float(height_m))
    top -= height_m * 0.28 * severity * fbm1d(n, rng)

    edge_frac = np.minimum(s, length_m - s) / max(length_m, 1e-9)
    top -= height_m * 0.22 * severity * np.exp(-edge_frac * 14.0) * (0.5 + rng.random(n))

    if breach_chance is None:
        breach_chance = min(0.85, 0.15 + 0.6 * severity)
    if length_m > 5.0 and float(rng.random()) < breach_chance:
        centre = float(rng.uniform(0.2, 0.8)) * length_m
        width = float(rng.uniform(1.2, 3.0))
        depth = height_m * float(rng.uniform(0.45, 0.72))
        top -= depth * np.exp(-(((s - centre) / width) ** 2))

    return s, np.maximum(top, min_height_m)
