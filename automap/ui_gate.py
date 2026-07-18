"""Interface Director's gate: readability (studio-org ledger row 30).

``games/<g>/ui/ui.json`` (ui@1) carries theme + menus + hud. The gate is
mechanical: font floors at the reference resolution, WCAG-style contrast
between theme color pairs, required pause tabs present. Taste stays with
the Interface Director; this only proves a human can READ the result.
Floors mirror games/<g>/systems.md ("Interface floors").
"""
from __future__ import annotations

import json
from pathlib import Path

from automap.story import Finding

# rulers — mirror systems.md
FONT_FLOORS = {"default": 12, "small": 10, "title": 16}
CONTRAST_ERRORS = (("text", "panel_bg", 4.5), ("accent", "panel_bg", 3.0))
CONTRAST_WARNS = (("disabled", "panel_bg", 2.0),)
REQUIRED_TABS = ("items", "save", "quit")


def load_ui(game_dir: Path) -> dict:
    path = game_dir / "ui" / "ui.json"
    if not path.exists():
        raise FileNotFoundError(f"no ui document at {path}")
    return json.loads(path.read_text())


def _luminance(hex_color: str) -> float:
    rgb = [int(hex_color[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
           for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast_ratio(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def check_ui(game_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    err = lambda who, msg: findings.append(Finding("error", who, msg))
    warn = lambda who, msg: findings.append(Finding("warn", who, msg))

    try:
        ui = load_ui(game_dir)
    except FileNotFoundError:
        return findings  # no ui doc yet — engine falls back to defaults

    theme = ui.get("theme", {})
    for key, floor in FONT_FLOORS.items():
        size = theme.get("font_size", {}).get(key)
        if size is not None and size < floor:
            err(f"font_size.{key}",
                f"{size} px < floor {floor} px at 1152×648 (systems.md: "
                "Interface floors)")

    colors = theme.get("colors", {})

    def _pair(fg: str, bg: str, floor: float, sink) -> None:
        if fg in colors and bg in colors:
            ratio = contrast_ratio(colors[fg], colors[bg])
            if ratio < floor:
                sink(f"colors.{fg}",
                     f"contrast vs {bg} is {ratio:.2f} < {floor} — "
                     "unreadable on the panel")

    for fg, bg, floor in CONTRAST_ERRORS:
        _pair(fg, bg, floor, err)
    for fg, bg, floor in CONTRAST_WARNS:
        _pair(fg, bg, floor, warn)

    tabs = ui.get("menus", {}).get("pause_tabs", [])
    for required in REQUIRED_TABS:
        if required not in tabs:
            err("menus.pause_tabs",
                f"missing required tab {required!r} (a game you cannot "
                "save or quit is a trap)")
    return findings
