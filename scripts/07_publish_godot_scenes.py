#!/usr/bin/env python
"""Stage 7 - publish a generated scene into the Godot project as walkable .tscn.

The pipeline writes glbs to work/<name>/mesh/ (gitignored). To *test* them the
Godot engine needs them inside res://, wrapped in a scene it can play directly.
This copies the two representation glbs into godot/scenes/<name>/ and writes one
.tscn per glb, keeping the established nomenclature (sraw_<name>.tscn,
sf_<name>.tscn).

Each .tscn is an *inherited scene of game.tscn* (the walking explorer: player,
camera, light, environment) with map_loader's `map_scene` set to the glb. So it
plays straight from the editor's Play button (F6) — no launch arg needed — and is
still the game.tscn shell with this map dropped in.

    python scripts/07_publish_godot_scenes.py --name phare
    python scripts/07_publish_godot_scenes.py --name phare --no-import  # skip reimport

Only intermediates-free glbs cross into res://; odm/frames never do (see .gitignore).
Run the result with:  python scripts/04_prepare_godot.py <the .tscn>
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from automap.scenes import scene_paths  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GAME_TSCN = "res://scenes/game.tscn"
app = typer.Typer(add_completion=False)


def _game_uid(root: Path) -> Optional[str]:
    """Read game.tscn's stable uid so inherited scenes reference it robustly."""
    game = root / "godot" / "scenes" / "game.tscn"
    if not game.exists():
        return None
    m = re.search(r'uid="(uid://[^"]+)"', game.read_text().splitlines()[0])
    return m.group(1) if m else None


def _find_godot() -> Optional[str]:
    w = shutil.which("godot")
    if w:
        return w
    app_bin = Path("/Applications/Godot.app/Contents/MacOS/Godot")
    return str(app_bin) if app_bin.is_file() else None


def _tscn(res_glb: str, node_name: str, game_uid: Optional[str]) -> str:
    """A Godot 4 scene inheriting game.tscn with the glb assigned to map_scene.

    Inheriting the explorer (player/camera/light/env) makes the scene playable on
    its own; map_loader instantiates map_scene, adds collision, and places the
    player — no launch arg required.
    """
    uid_attr = f'uid="{game_uid}" ' if game_uid else ""
    return (
        "[gd_scene load_steps=3 format=3]\n\n"
        f'[ext_resource type="PackedScene" {uid_attr}path="{GAME_TSCN}" id="1_game"]\n'
        f'[ext_resource type="PackedScene" path="{res_glb}" id="2_map"]\n\n'
        f'[node name="{node_name}" instance=ExtResource("1_game")]\n'
        'map_scene = ExtResource("2_map")\n'
    )


def publish(root: Path, name: str, do_import: bool = True, on_log=print) -> list[str]:
    """Copy the scene's glbs into godot/scenes/<name>/ and emit a .tscn per glb.

    Returns the res:// paths of the written .tscn files.
    """
    sp = scene_paths(root, name)
    dest = root / "godot" / "scenes" / name
    dest.mkdir(parents=True, exist_ok=True)
    game_uid = _game_uid(root)

    # (glb source, representation) — publish only what generation produced.
    candidates = [sp.raw_glb, sp.styled_glb]
    written: list[Path] = []
    for glb in candidates:
        if not glb.exists():
            continue
        shutil.copy2(glb, dest / glb.name)
        res_glb = f"res://scenes/{name}/{glb.name}"
        tscn = dest / f"{glb.stem}.tscn"
        tscn.write_text(_tscn(res_glb, glb.stem, game_uid))
        written.append(tscn)
        on_log(f"published {glb.name} -> res://scenes/{name}/{tscn.name}")

    if not written:
        on_log(f"nothing to publish for {name!r} (no glbs in {sp.mesh_dir})")
        return []

    # Godot loads res:// resources from its import cache, so newly-copied glbs must
    # be imported before the engine can open the .tscn at runtime.
    if do_import:
        godot = _find_godot()
        if godot:
            on_log("importing new resources (headless)…")
            subprocess.run([godot, "--headless", "--path", str(root / "godot"), "--import"],
                           check=False, capture_output=True)
        else:
            on_log("Godot not found — skipped reimport; open the editor once to import")

    return [f"res://scenes/{name}/{t.name}" for t in written]


@app.command()
def main(
    name: str = typer.Option(..., "--name", help="Scene name (the ingest --name)"),
    do_import: bool = typer.Option(True, "--import/--no-import", help="Reimport res:// after copying"),
):
    res = publish(ROOT, name, do_import=do_import, on_log=lambda m: typer.echo(f"[stage 7] {m}"))
    if res:
        typer.echo("[stage 7] walk them with:")
        for r in res:
            typer.echo(f"    python scripts/04_prepare_godot.py {r}")


if __name__ == "__main__":
    app()
