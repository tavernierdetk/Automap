#!/usr/bin/env python
"""Stage 6 (presentation) - apply a visual identity to a scene -> styled glb.

The abstraction where a visual identity + transformer chain turns the faithful
source (terrain/mesh glb) plus the semantic layer (features.json) into the game's
look. Non-destructive: writes a NEW glb, never touches the sources.

    python scripts/06_style_scene.py \
        --source work/<name>/mesh/<name>.glb \
        --features work/<name>/features.json \
        --output work/<name>/styled/<name>.glb [--identity placeholder]

The 'placeholder' identity swaps tree features for procedural stand-in trees so
the plumbing is provable before a real art style is dialed in.
See docs/explorations/dual-pipeline-styling.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automap.presentation import VisualIdentity, style_scene  # noqa: E402

app = typer.Typer(add_completion=False)

# Named identities live here for now (data, not code). Real art styles get added
# as more entries; transformers stay the same.
IDENTITIES = {
    "placeholder": VisualIdentity(name="placeholder"),
}


@app.command()
def main(
    source: Path = typer.Option(..., "--source", help="Source glb (terrain or mesh)"),
    features: Path = typer.Option(..., "--features", help="features.json"),
    output: Path = typer.Option(..., "--output", help="Styled glb"),
    identity: str = typer.Option("placeholder", "--identity", help=f"one of {list(IDENTITIES)}"),
):
    if not source.exists():
        raise typer.BadParameter(f"source glb not found: {source}")
    if identity not in IDENTITIES:
        raise typer.BadParameter(f"unknown identity {identity!r}; have {list(IDENTITIES)}")
    feats = json.loads(features.read_text()).get("features", []) if features.exists() else []

    log = lambda m: typer.echo(f"[stage 6] {m}")
    log(f"identity '{identity}', {len(feats)} features, source {source.name}")
    scene = style_scene(source, feats, IDENTITIES[identity], on_log=log)

    output.parent.mkdir(parents=True, exist_ok=True)
    scene.export(output)
    log(f"wrote {output} ({output.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    app()
