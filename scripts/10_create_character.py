#!/usr/bin/env python
"""Stage 10 (character admission) - validate a CharacterProfile v2 and let it in.

The gate of the Claude character creator (brief §3.2): a conversation (or a
photo, or a hand edit) produces a character-profile@2.0.0 JSON; nothing enters
the game until it passes BOTH checks here:

    python scripts/10_create_character.py --character godot/characters/marguerite.json

1. **Schema** — the document conforms to character-profile@2.0.0 (bounds,
   required fields, the five-attribute stat block).
2. **Balance** — the autosim (automap/balance.py) batch-duels the stat block
   against the reference cast; win rates must land inside the difficulty
   envelope. LLM proposes, simulation validates.

On admission the appearance section is projected to the parametric rig's
contract: godot/profiles/<slug>.tres (the same .tres a photo or a hand edit
produces — stage A renders it unchanged). The JSON stays the committed source
of truth; the verdict is printed and saved to work/characters/ as re-derivable
evidence, never as state.

On rejection the exit code is 1 and the verdict says WHY (too strong/too weak
and against whom) — that text is the revise loop's feedback.

--play additionally makes them THE player: game.tscn's Body profile is the
one seam every published scene inherits (and no stage regenerates), so one
edit there survives every re-publish of every scene.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automap import balance, character  # noqa: E402

app = typer.Typer(add_completion=False)

SPEC = ("character-profile", "2.0.0")


def _validate_schema(doc: dict, log) -> None:
    """character-profile@2.0.0 conformance; auto-detect / no-op on the lib."""
    try:
        import platform_specs
    except ImportError:
        log("WARNING: platform-specs not installed - schema check SKIPPED "
            "(pip install -e ../platform-specs)")
        return
    platform_specs.validate(doc, *SPEC)
    log(f"schema ok ({SPEC[0]}@{SPEC[1]})")


def _set_player_profile(root: Path, res_path: str) -> None:
    """Point game.tscn's player Body at a profile (the inherited-shell seam)."""
    game = root / "godot" / "scenes" / "game.tscn"
    text = game.read_text()
    new, n = re.subn(
        r'(\[ext_resource type="Resource" )path="res://profiles/[^"]+"( id="5_profile"\])',
        rf'\1path="{res_path}"\2', text)
    if n != 1:
        raise RuntimeError(f"expected exactly one 5_profile ext_resource in {game}, found {n}")
    game.write_text(new)


@app.command()
def main(
    character_json: Path = typer.Option(..., "--character", help="CharacterProfile v2 JSON"),
    seed: int = typer.Option(0, "--seed", help="Autosim seed (verdicts are re-derivable)"),
    play: bool = typer.Option(False, "--play",
                              help="Make them the player in every published scene (edits game.tscn)"),
    profiles_dir: Path = typer.Option(None, "--profiles-dir",
                                      help="Where the .tres lands (default godot/profiles)"),
    root: Path = typer.Option(Path(__file__).resolve().parent.parent, "--root"),
):
    log = lambda m: typer.echo(f"[stage 10] {m}")
    if not character_json.exists():
        raise typer.BadParameter(f"character not found: {character_json}")

    doc = json.loads(character_json.read_text())
    _validate_schema(doc, log)

    verdict = balance.evaluate(doc["stats"], seed=seed)
    typer.echo(verdict.summary())

    slug = character.slugify(doc["name"])
    evidence = root / "work" / "characters" / f"{slug}.verdict.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(
        {"name": doc["name"], "stats": doc["stats"], "seed": verdict.seed,
         "admitted": verdict.admitted, "overall_win_rate": verdict.overall_win_rate,
         "win_rates": verdict.win_rates, "reasons": verdict.reasons}, indent=2) + "\n")

    if not verdict.admitted:
        log(f"rejected - revise the stats and re-run (evidence: {evidence})")
        raise typer.Exit(code=1)

    attrs = character.appearance_to_attributes(doc["appearance"])
    movement = balance.derive_movement(doc["stats"])
    out_dir = profiles_dir or root / "godot" / "profiles"
    out = out_dir / f"{slug}.tres"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(character.attributes_to_tres(attrs, movement=movement))
    log(f"admitted - wrote {out}")
    log("movement (derived from stats): " + ", ".join(
        f"{k}={v:g}" for k, v in movement.items()))
    if play:
        _set_player_profile(root, f"res://profiles/{slug}.tres")
        log(f"game.tscn player Body -> {slug}.tres (every published scene inherits it)")
    else:
        log("walk as them: re-run with --play, or assign the profile on the "
            "player Body in godot/scenes/game.tscn")


if __name__ == "__main__":
    app()
