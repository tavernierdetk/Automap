#!/usr/bin/env python
"""Stage 3 - clean the ODM mesh and export a Godot-ready .glb (via Blender headless).

Owns the coordinate-system fix: ODM outputs real-world-scale, **Z-up** geometry;
Godot is **Y-up**, metric. We import Z-up into Blender, decimate, recenter to the
origin, and let the glTF exporter convert Z-up -> Y-up on the way out.

Run it directly - it re-executes itself inside Blender's bundled Python:

    python scripts/03_mesh_to_glb.py \
        --input work/odm/odm_texturing/odm_textured_model_geo.obj \
        --output work/mesh/scene.glb [--decimate 0.25]

(equivalently: blender --background --python scripts/03_mesh_to_glb.py -- <args>)
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# --- When run by a normal Python, re-exec inside Blender ---------------------
try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ModuleNotFoundError:
    IN_BLENDER = False


def _find_blender() -> str:
    cand = shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"
    if not Path(cand).exists() and not shutil.which("blender"):
        sys.exit("Blender not found. Install with: brew install --cask blender")
    return cand


if not IN_BLENDER:
    blender = _find_blender()
    os.execvp(blender, [blender, "--background", "--python", __file__, "--", *sys.argv[1:]])
    # execvp replaces the process; nothing below runs in this branch.


# --- From here on we are inside Blender --------------------------------------
import argparse  # noqa: E402
import math  # noqa: E402

import bpy  # noqa: E402,F811


def _parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description="ODM .obj -> Godot .glb")
    p.add_argument("--input", required=True, help="ODM textured .obj")
    p.add_argument("--output", default="work/mesh/scene.glb", help="output .glb")
    p.add_argument("--decimate", type=float, default=None, help="face keep-ratio (0-1)")
    p.add_argument("--up-axis", default="Z", help="OBJ up axis (ODM is Z)")
    p.add_argument("--forward-axis", default="Y", help="OBJ forward axis")
    p.add_argument("--flip-vertical", action=argparse.BooleanOptionalAction, default=True,
                   help="flip the scan upright (ODM's surface imports facing down)")
    return p.parse_args(argv)


def _decimate_default() -> float:
    """Read [mesh].decimate_ratio from config.toml if present, else 0.25."""
    try:
        import tomllib
        cfg = Path(__file__).resolve().parent.parent / "config.toml"
        if cfg.exists():
            with open(cfg, "rb") as f:
                return float(tomllib.load(f).get("mesh", {}).get("decimate_ratio", 0.25))
    except Exception:
        pass
    return 0.25


def _bounds(obj):
    """World-space (min, max) corners of an object's bounding box."""
    from mathutils import Vector
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    return lo, hi


def main() -> None:
    args = _parse_args()
    ratio = args.decimate if args.decimate is not None else _decimate_default()
    inp = Path(args.input).resolve()
    out = Path(args.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if not inp.exists():
        sys.exit(f"[stage 3] input not found: {inp}")

    # Empty scene (no default cube/camera/light).
    bpy.ops.wm.read_factory_settings(use_empty=True)

    print(f"[stage 3] importing {inp.name} (up={args.up_axis}, forward={args.forward_axis})")
    bpy.ops.wm.obj_import(
        filepath=str(inp), up_axis=args.up_axis, forward_axis=args.forward_axis,
    )
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        sys.exit("[stage 3] no mesh imported")

    # Join into one object so transforms/decimation are uniform.
    for o in bpy.context.scene.objects:
        o.select_set(o.type == "MESH")
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active

    # ODM's georeferenced .obj imports with the scanned surface facing -Z, so the
    # Y-up glb lands upside-down in Godot. A 180 deg rotation about X brings it
    # upright; being a proper rotation it preserves winding/normals (no mirror).
    if args.flip_vertical:
        obj.rotation_euler = (math.pi, 0.0, 0.0)
        bpy.ops.object.transform_apply(rotation=True)
        print("[stage 3] flipped vertical (ODM -Z surface -> up)")

    n_before = len(obj.data.polygons)

    # Decimate (collapse) to the target face ratio.
    if 0 < ratio < 1:
        mod = obj.modifiers.new("decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        bpy.ops.object.modifier_apply(modifier=mod.name)
    n_after = len(obj.data.polygons)

    # Recenter to the world origin, then sit the model on the ground (min Z -> 0).
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    obj.location = (0.0, 0.0, 0.0)
    lo, hi = _bounds(obj)
    obj.location.z -= lo.z
    bpy.context.view_layer.update()
    lo, hi = _bounds(obj)
    size = hi - lo

    # Export glb. Blender is Z-up; the glTF exporter converts to Y-up for Godot.
    print(f"[stage 3] exporting {out.name}")
    bpy.ops.export_scene.gltf(
        filepath=str(out),
        export_format="GLB",
        use_selection=False,
        export_yup=True,
        export_image_format="AUTO",
    )

    print(f"[stage 3] faces {n_before} -> {n_after} (ratio {ratio})")
    print(f"[stage 3] model size (m): X={size.x:.1f} Y={size.y:.1f} Z={size.z:.1f}")
    print(f"[stage 3] wrote {out} ({out.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
