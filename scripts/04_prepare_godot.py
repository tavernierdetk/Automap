#!/usr/bin/env python
"""Stage 4 - launch the walking engine pointed at a pipeline-generated mesh.

The Godot project is a *standalone walking engine*: it loads any .glb at runtime
by path and never bakes a specific scene. So stage 4 does not copy or import
anything into the engine — it just points the engine at the mesh stage 3 produced.
Generation (stages 0-3) and playback stay fully decoupled.

    python scripts/04_prepare_godot.py                  # plays work/mesh/scene.glb
    python scripts/04_prepare_godot.py path/to/other.glb
    python scripts/04_prepare_godot.py res://scenes/phare/sf_phare.tscn        # a published scene
    python scripts/04_prepare_godot.py --game res://scenes/phare/sf_phare.tscn # third-person explorer
    python scripts/04_prepare_godot.py --print-only      # just print the command

Equivalent manual launch:
    /Applications/Godot.app/Contents/MacOS/Godot --path godot -- --scene <abs.glb>
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "godot"


def find_godot() -> str:
    w = shutil.which("godot")
    if w:
        return w
    app = Path("/Applications/Godot.app/Contents/MacOS/Godot")
    if app.is_file():
        return str(app)
    sys.exit("Godot not found. Install Godot 4.x (https://godotengine.org).")


def main(argv: list[str]) -> None:
    print_only = "--print-only" in argv
    # --game runs the third-person character explorer (game.tscn) instead of the
    # default first-person main scene; both are thin shells over map_loader.gd.
    use_game = "--game" in argv
    rest = [a for a in argv if a not in ("--print-only", "--game")]

    arg = rest[0] if rest else str(ROOT / "work" / "mesh" / "scene.glb")
    # A res:// path is a Godot-project resource (e.g. a published .tscn) — hand it
    # to the engine verbatim; only OS paths get resolved + existence-checked.
    if arg.startswith("res://"):
        scene = arg
        print(f"[stage 4] engine -> {scene}")
    else:
        p = Path(arg).resolve()
        if not p.exists():
            sys.exit(f"[stage 4] {p} missing — run stage 3 first (or pass a .glb/.tscn path).")
        scene = str(p)
        print(f"[stage 4] engine -> {scene} ({p.stat().st_size // 1024} KiB)")

    godot = find_godot()
    cmd = [godot, "--path", str(PROJECT)]
    if scene.lower().endswith((".tscn", ".scn")):
        # A published scene IS a runnable shell (inherited game.tscn with its map baked
        # in) — run it directly, like the editor's Play button. Passing it via --scene=
        # would make the shell's own loader re-load itself forever. OS paths inside the
        # project are rewritten to res:// (a positional scene must live in the project).
        if not scene.startswith("res://"):
            p = Path(scene)
            try:
                scene = "res://" + p.relative_to(PROJECT).as_posix()
            except ValueError:
                sys.exit(f"[stage 4] {p} is a .tscn outside the Godot project — "
                         "published scenes live under godot/ (res://scenes/...).")
        cmd.append(scene)  # --game is implied: the shell carries its own player
    else:
        if use_game:
            cmd.append("res://scenes/game.tscn")
        cmd += ["--", f"--scene={scene}"]
    print("    " + " ".join(cmd))
    if print_only:
        return
    # The engine loads the glb at runtime via GLTFDocument; nothing is written
    # back into the godot/ project, so scene generation is never touched.
    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main(sys.argv[1:])
