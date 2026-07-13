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
from automap.presentation import VisualIdentity, identity_from_dict, style_scene  # noqa: E402

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
    # Plateau-Mont-Royal: brick row housing, silver tin and dark membrane
    # roofs, painted cornices, asphalt streets, park maples.
    "plateau": VisualIdentity(
        name="plateau",
        transformers=["style_terrain", "instance_trees", "instance_buildings",
                      "instance_roads", "instance_water"],
        tree_kit="varied",
        trunk_color=(0.30, 0.24, 0.18),
        canopy_color=(0.24, 0.38, 0.16),          # street maples
        building_details=True,
        wall_color=(0.47, 0.27, 0.20),            # red-brown brick
        trim_color=(0.92, 0.90, 0.84),            # painted wood cornices/balconies
        roof_saturation=1.0,                      # no postcard boost — city greys stay grey
        roof_palette=((0.72, 0.74, 0.76),         # silver tin (mansard/standing seam)
                      (0.25, 0.25, 0.27),         # dark membrane flat roof
                      (0.38, 0.52, 0.42),         # oxidized copper
                      (0.52, 0.30, 0.24)),        # brick-red sheet
        road_color=(0.29, 0.29, 0.31),            # asphalt
        path_color=(0.56, 0.56, 0.54),            # concrete sidewalk grey
        water_color=(0.20, 0.35, 0.45),
        grass_color=(0.36, 0.50, 0.26),           # park green (Square Saint-Louis)
        cliff_color=(0.55, 0.53, 0.50),           # greystone
        sand_color=(0.70, 0.65, 0.55),
        seafloor_color=(0.12, 0.25, 0.30),
        textures={
            "facade_style": "brick",
            "window_tile_m": 3.5,
            "storey_m": 3.0,
            "window_states": {"dark": 3, "lit": 1},
            "roof_style": "tin",
            "road_texture": True,
            "variants": 6,
        },
    ),
}


@app.command()
def main(
    source: Path = typer.Option(..., "--source", help="Source glb (terrain or mesh)"),
    features: Path = typer.Option(..., "--features", help="features.json"),
    output: Path = typer.Option(..., "--output", help="Styled glb"),
    identity: str = typer.Option(
        "placeholder", "--identity",
        help=f"one of {list(IDENTITIES)}, or a path to a visual-identity JSON file"),
    restyle_assets: bool = typer.Option(
        False, "--restyle/--keep-authored",
        help="Repaint dropped-in IFC buildings in the identity (default: keep authored materials)"),
):
    if not source.exists():
        raise typer.BadParameter(f"source glb not found: {source}")
    log = lambda m: typer.echo(f"[stage 6] {m}")

    if identity in IDENTITIES:
        ident = IDENTITIES[identity]
    elif identity.endswith(".json") and Path(identity).exists():
        # file-based identity (the visual-identity contract as data)
        doc = json.loads(Path(identity).read_text())
        try:
            import platform_specs
            platform_specs.validate(doc, "visual-identity", "2.2.0")
            log("identity file valid (visual-identity@2.2.0)")
        except ImportError:
            log("WARNING: platform-specs not installed - identity file NOT validated")
        ident = identity_from_dict(doc)
    else:
        raise typer.BadParameter(
            f"unknown identity {identity!r}; have {list(IDENTITIES)} or a .json path")
    feats = json.loads(features.read_text()).get("features", []) if features.exists() else []

    ident = replace(ident, restyle_assets=restyle_assets)
    log(f"identity '{ident.name}', {len(feats)} features, source {source.name}")
    scene = style_scene(source, feats, ident, on_log=log, scene_dir=features.parent)

    output.parent.mkdir(parents=True, exist_ok=True)
    scene.export(output)
    log(f"wrote {output} ({output.stat().st_size // 1024} KiB)")

    env_sidecar = output.parent / f"{output.stem}.env.json"
    if ident.environment:
        env_sidecar.write_text(json.dumps(
            {"identity": ident.name, **ident.environment}, indent=2) + "\n")
        log(f"wrote {env_sidecar.name} (atmosphere; published beside the scene)")
    elif env_sidecar.exists():
        env_sidecar.unlink()  # stale atmosphere from a previous identity must not survive
        log(f"removed stale {env_sidecar.name}")


if __name__ == "__main__":
    app()
