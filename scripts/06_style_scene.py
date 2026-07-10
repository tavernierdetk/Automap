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
from dataclasses import replace
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automap.presentation import VisualIdentity, style_scene  # noqa: E402

app = typer.Typer(add_completion=False)

# Named identities live here for now (data, not code). Real art styles get added
# as more entries; transformers stay the same.
IDENTITIES = {
    "placeholder": VisualIdentity(name="placeholder"),
    # Madelinot postcard: site-true Iles-de-la-Madeleine — bright painted
    # houses, golden-green grass, pale sand cliffs, teal sea.
    "madelinot": VisualIdentity(
        name="madelinot",
        transformers=["style_terrain", "instance_trees", "instance_buildings",
                      "instance_roads", "instance_water"],
        tree_kit="varied",
        trunk_color=(0.36, 0.27, 0.18),
        canopy_color=(0.23, 0.37, 0.20),          # wind-bent dark spruce green
        building_details=True,
        wall_color=(0.95, 0.93, 0.87),            # bright white-cream siding
        trim_color=(0.98, 0.97, 0.94),
        roof_saturation=1.6,                      # postcard-boost detected roofs
        roof_palette=((0.78, 0.21, 0.18),         # painted red
                      (0.18, 0.49, 0.28),         # painted green
                      (0.89, 0.73, 0.24),         # painted yellow
                      (0.20, 0.37, 0.64)),        # painted blue
        road_color=(0.72, 0.69, 0.63),            # pale gravel
        path_color=(0.62, 0.52, 0.38),
        water_color=(0.18, 0.49, 0.55),           # teal
        grass_color=(0.50, 0.64, 0.30),           # golden-green
        cliff_color=(0.79, 0.66, 0.48),           # pale sand cliffs
        sand_color=(0.87, 0.78, 0.60),
        seafloor_color=(0.10, 0.30, 0.36),
    ),
}


@app.command()
def main(
    source: Path = typer.Option(..., "--source", help="Source glb (terrain or mesh)"),
    features: Path = typer.Option(..., "--features", help="features.json"),
    output: Path = typer.Option(..., "--output", help="Styled glb"),
    identity: str = typer.Option("placeholder", "--identity", help=f"one of {list(IDENTITIES)}"),
    restyle_assets: bool = typer.Option(
        False, "--restyle/--keep-authored",
        help="Repaint dropped-in IFC buildings in the identity (default: keep authored materials)"),
):
    if not source.exists():
        raise typer.BadParameter(f"source glb not found: {source}")
    if identity not in IDENTITIES:
        raise typer.BadParameter(f"unknown identity {identity!r}; have {list(IDENTITIES)}")
    feats = json.loads(features.read_text()).get("features", []) if features.exists() else []

    ident = replace(IDENTITIES[identity], restyle_assets=restyle_assets)
    log = lambda m: typer.echo(f"[stage 6] {m}")
    log(f"identity '{identity}', {len(feats)} features, source {source.name}")
    scene = style_scene(source, feats, ident, on_log=log, scene_dir=features.parent)

    output.parent.mkdir(parents=True, exist_ok=True)
    scene.export(output)
    log(f"wrote {output} ({output.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    app()
