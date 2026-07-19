"""Autosim balance gate: LLM proposes stats, simulation validates them.

The admission pattern from Entropy (the brief's §3.2 force multiplier): a
character's five-attribute stat block (character-profile@2.0.0 `stats`) is
accepted only if it *plays* acceptably — a batch of seeded duels against a
reference cast must land its win rates inside a difficulty envelope. Schema
validation checks bounds; this module checks balance. That is what makes
LLM-generated stats trustworthy enough to admit.

Rebuilt small from EntropySnapShot's design (per the reuse ledger: the AutoSim
harness is a pattern to rebuild, the ATB/status fidelity is a future slice):

- **Chaos RNG** — seeded *named* streams (one per concern, so adding a stream
  never perturbs another) sampling an Azzalini skew-normal with hard clips.
  Chaos mastery literally widens and skews a fighter's damage distribution:
  "luck" is a stat surface, and it is reproducible.
- **Derived stats** — the five attributes map to hp/speed/attack/defense by
  fixed linear formulas below. The mapping is this module's *design opinion*;
  the contract (the five attributes) lives in platform-specs.
- **ATB duel** — gauges fill by speed each tick, an act fires at full gauge.
  Basic strikes only; statuses/skills stay in Entropy's design spec until the
  combat module earns its slice.

Everything is deterministic given (stats, opponent, seed): a verdict is
re-derivable evidence, never stored state. No numpy — stdlib math only.
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field

ATTRIBUTES = (
    "creature_affinity", "chaos_mastery", "kinesthetic", "lucidity", "terrain_control",
)

# --- derived-stat formulas (the balance designer's dials, all in one place) ---
# Two deliberate properties: duels are SHORT (~5-8 hits — few rolls keep
# single-bout variance high, so mismatches show as win-rate drift rather than
# 0/1 certainties), and every derived stat has a large BASE relative to its
# per-point terms (so one attribute point moves win rate a few percent, not
# tens — a steep surface makes the propose→revise loop thrash).
BASE_HP = 45.0
HP_PER_KINESTHETIC = 2.0
HP_PER_TERRAIN = 1.5
BASE_SPEED = 8.0
SPEED_PER_KINESTHETIC = 0.25
SPEED_PER_LUCIDITY = 0.25
BASE_ATTACK = 8.0
ATTACK_PER_AFFINITY = 0.8
ATTACK_PER_KINESTHETIC = 0.5
ATTACK_PER_CHAOS = 0.3      # chaos is mostly variance+crit reach, but not free
DEFENSE_PER_TERRAIN = 0.8
DEFENSE_PER_LUCIDITY = 0.4
DEFENSE_SOAK = 0.5          # fraction of defense subtracted from each hit
GAUGE_FULL = 100.0
TICK_CAP = 600              # a duel that outlives this is a draw

# Chaos: the damage roll is a centered skew-normal around 1.0. More
# chaos_mastery widens the spread and skews the tail right — and a roll in the
# far tail is a CRIT that ignores defense. Chaos buys no average damage; it
# buys reach into the crit region. Luck as a stat surface, reproducibly.
ROLL_SCALE_BASE = 0.18
ROLL_SCALE_PER_CHAOS = 0.04
ROLL_CLIP = (0.25, 2.5)
CRIT_THRESHOLD = 1.75       # roll at/above this bypasses defense entirely


def _skew_normal(rng: random.Random, alpha: float) -> float:
    """One CENTERED Azzalini skew-normal sample (mean 0, scale 1, shape alpha).

    Centered on the distribution mean (delta*sqrt(2/pi)), not the location
    parameter — otherwise alpha silently shifts average damage and chaos
    mastery becomes a hidden flat attack buff instead of a variance/tail dial.
    """
    delta = alpha / math.sqrt(1.0 + alpha * alpha)
    u0 = rng.gauss(0.0, 1.0)
    v = rng.gauss(0.0, 1.0)
    return delta * abs(u0) + math.sqrt(1.0 - delta * delta) * v - delta * math.sqrt(2.0 / math.pi)


class ChaosRng:
    """Seeded named streams over a skew-normal — Entropy's chaos RNG, reduced.

    Streams are independent by construction (each is its own Random seeded by
    a hash of (seed, name)), so consuming one never shifts another.
    """

    def __init__(self, seed: int):
        self.seed = seed
        self._streams: dict[str, random.Random] = {}

    def _stream(self, name: str) -> random.Random:
        s = self._streams.get(name)
        if s is None:
            digest = hashlib.sha256(f"{self.seed}:{name}".encode()).digest()
            s = self._streams[name] = random.Random(int.from_bytes(digest[:8], "big"))
        return s

    def roll(self, name: str, *, loc: float, scale: float, alpha: float,
             clip: tuple[float, float]) -> float:
        x = loc + scale * _skew_normal(self._stream(name), alpha)
        return max(clip[0], min(clip[1], x))

    def uniform(self, name: str, lo: float, hi: float) -> float:
        return self._stream(name).uniform(lo, hi)


@dataclass
class Fighter:
    """Derived combat state for one five-attribute stat block."""
    name: str
    stats: dict[str, int]
    hp: float = field(init=False)
    speed: float = field(init=False)
    attack: float = field(init=False)
    defense: float = field(init=False)
    gauge: float = field(default=0.0, init=False)

    def __post_init__(self):
        missing = [a for a in ATTRIBUTES if a not in self.stats]
        if missing:
            raise ValueError(f"stat block for {self.name!r} is missing {missing}")
        s = self.stats
        self.hp = BASE_HP + HP_PER_KINESTHETIC * s["kinesthetic"] + HP_PER_TERRAIN * s["terrain_control"]
        self.speed = BASE_SPEED + SPEED_PER_KINESTHETIC * s["kinesthetic"] + SPEED_PER_LUCIDITY * s["lucidity"]
        self.attack = (BASE_ATTACK + ATTACK_PER_AFFINITY * s["creature_affinity"]
                       + ATTACK_PER_KINESTHETIC * s["kinesthetic"] + ATTACK_PER_CHAOS * s["chaos_mastery"])
        self.defense = DEFENSE_PER_TERRAIN * s["terrain_control"] + DEFENSE_PER_LUCIDITY * s["lucidity"]

    def strike(self, other: "Fighter", rng: ChaosRng) -> float:
        chaos = self.stats["chaos_mastery"]
        roll = rng.roll(
            f"dmg:{self.name}",
            loc=1.0,
            scale=ROLL_SCALE_BASE + ROLL_SCALE_PER_CHAOS * chaos,
            alpha=float(chaos - 5),
            clip=ROLL_CLIP,
        )
        soak = 0.0 if roll >= CRIT_THRESHOLD else other.defense * DEFENSE_SOAK
        dmg = max(1.0, self.attack * roll - soak)
        other.hp -= dmg
        return dmg


def duel(stats_a: dict[str, int], stats_b: dict[str, int], *, seed: int) -> str:
    """One seeded ATB duel. Returns 'a', 'b', or 'draw'."""
    rng = ChaosRng(seed)
    a, b = Fighter("a", stats_a), Fighter("b", stats_b)
    # initiative: a random head start keeps identical rematches from replaying
    a.gauge = rng.uniform("init:a", 0.0, GAUGE_FULL)
    b.gauge = rng.uniform("init:b", 0.0, GAUGE_FULL)
    for _ in range(TICK_CAP):
        a.gauge += a.speed
        b.gauge += b.speed
        # faster gauge acts first on simultaneous fills; ties break by stream
        order = sorted((a, b), key=lambda f: (-f.gauge, f.name))
        for f in order:
            if f.gauge < GAUGE_FULL:
                continue
            f.gauge -= GAUGE_FULL
            other = b if f is a else a
            f.strike(other, rng)
            if other.hp <= 0:
                return f.name
    return "draw"


# --- movement derivation (stats -> locomotion params) ------------------------
# The same opinion-in-one-place pattern as the Fighter formulas: mechanics owns
# how the five attributes become locomotion. Stage 10 projects the result into
# the CharacterProfile .tres beside the appearance fields; the Godot Locomotion
# component reads them at runtime. Movement params are DERIVED, never hand-set.
# Calibration anchor: the all-5 "deckhand" lands exactly on the engine's
# historical constants (walk 6.0, jump 6.0, turn 12.0), so average characters
# leave the game feel untouched.
BASE_WALK_SPEED = 5.0
WALK_PER_KINESTHETIC = 0.15
WALK_PER_LUCIDITY = 0.05
BASE_JUMP_VELOCITY = 5.5
JUMP_PER_KINESTHETIC = 0.1
BASE_TURN_SPEED = 10.0
TURN_PER_KINESTHETIC = 0.25
TURN_PER_LUCIDITY = 0.15


def derive_movement(stats: dict[str, int]) -> dict[str, float]:
    """Locomotion params for a stat block. Kinesthetic carries speed and jump;
    lucidity adds composure (a little top speed, most of the turn agility).
    Chaos/affinity/terrain stay priced in combat and (later) traversal rules."""
    missing = [a for a in ATTRIBUTES if a not in stats]
    if missing:
        raise ValueError(f"stat block is missing {missing}")
    k, lu = stats["kinesthetic"], stats["lucidity"]
    return {
        "walk_speed": round(BASE_WALK_SPEED + WALK_PER_KINESTHETIC * k + WALK_PER_LUCIDITY * lu, 2),
        "jump_velocity": round(BASE_JUMP_VELOCITY + JUMP_PER_KINESTHETIC * k, 2),
        "turn_speed": round(BASE_TURN_SPEED + TURN_PER_KINESTHETIC * k + TURN_PER_LUCIDITY * lu, 2),
    }


# --- the reference cast: archetypes spanning the envelope, totals near 25 ----
REFERENCE_CAST: dict[str, dict[str, int]] = {
    "deckhand":  # the all-average baseline
        {"creature_affinity": 5, "chaos_mastery": 5, "kinesthetic": 5, "lucidity": 5, "terrain_control": 5},
    "brawler":  # physical spike, no guile
        {"creature_affinity": 4, "chaos_mastery": 4, "kinesthetic": 7, "lucidity": 4, "terrain_control": 5},
    "trickster":  # lives on the chaos tail
        {"creature_affinity": 6, "chaos_mastery": 8, "kinesthetic": 4, "lucidity": 5, "terrain_control": 3},
    "warden":  # defensive wall with a real bite
        {"creature_affinity": 5, "chaos_mastery": 3, "kinesthetic": 4, "lucidity": 5, "terrain_control": 8},
}


@dataclass
class Envelope:
    """The difficulty envelope — the game spec's balance section in miniature.

    Graduates into the game schema when the game spec earns its version; until
    then these defaults are the platform's only balance policy.
    """
    overall: tuple[float, float] = (0.35, 0.65)   # mean win rate across the cast
    matchup: tuple[float, float] = (0.10, 0.90)   # no single matchup may leave this
    bouts_per_opponent: int = 60


@dataclass
class Verdict:
    admitted: bool
    overall_win_rate: float
    win_rates: dict[str, float]
    reasons: list[str]
    seed: int

    def summary(self) -> str:
        lines = [f"{'ADMITTED' if self.admitted else 'REJECTED'} — overall win rate {self.overall_win_rate:.2f} (seed {self.seed})"]
        lines += [f"  vs {n:<10} {r:.2f}" for n, r in self.win_rates.items()]
        lines += [f"  ! {r}" for r in self.reasons]
        return "\n".join(lines)


def evaluate(stats: dict[str, int], *, seed: int = 0, envelope: Envelope | None = None,
             cast: dict[str, dict[str, int]] | None = None) -> Verdict:
    """Batch-simulate the stat block against the cast and judge it."""
    env = envelope or Envelope()
    cast = cast or REFERENCE_CAST
    win_rates: dict[str, float] = {}
    for name, opp in cast.items():
        wins = 0.0
        for i in range(env.bouts_per_opponent):
            bout_seed = int.from_bytes(
                hashlib.sha256(f"{seed}:{name}:{i}".encode()).digest()[:8], "big")
            result = duel(stats, opp, seed=bout_seed)
            wins += 1.0 if result == "a" else (0.5 if result == "draw" else 0.0)
        win_rates[name] = wins / env.bouts_per_opponent

    overall = sum(win_rates.values()) / len(win_rates)
    reasons: list[str] = []
    lo, hi = env.overall
    if overall < lo:
        reasons.append(f"too weak: overall win rate {overall:.2f} < {lo:.2f}")
    if overall > hi:
        reasons.append(f"too strong: overall win rate {overall:.2f} > {hi:.2f}")
    mlo, mhi = env.matchup
    for name, r in win_rates.items():
        if r < mlo:
            reasons.append(f"hopeless matchup vs {name}: {r:.2f} < {mlo:.2f}")
        if r > mhi:
            reasons.append(f"free win vs {name}: {r:.2f} > {mhi:.2f}")

    return Verdict(admitted=not reasons, overall_win_rate=overall,
                   win_rates=win_rates, reasons=reasons, seed=seed)
