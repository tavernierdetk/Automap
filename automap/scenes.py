"""Multi-scene namespacing + the scene manifest.

Each named scene gets its own folder under work/<name>/ so scenes never clobber
each other, and a small JSON manifest records name -> glb (the proposed hand-off
contract to the playback engine).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

MANIFEST_REL = "scenes/manifest.json"


@dataclass
class ScenePaths:
    name: str
    base: Path         # work/<name>
    frames: Path       # work/<name>/frames
    odm: Path          # work/<name>/odm
    mesh_dir: Path     # work/<name>/mesh
    raw_glb: Path      # work/<name>/mesh/sraw_<name>.glb  (faithful geometry)
    styled_glb: Path   # work/<name>/mesh/sf_<name>.glb    (styled + features)
    base_glb: Path     # work/<name>/mesh/_base_<name>.glb (terrain base for styling)
    features: Path     # work/<name>/features.json         (semantic layer)
    obj: Path          # ODM's textured mesh, mesh-first stage-3 input
    dsm: Path          # ODM's surface DEM (feature detection)
    dtm: Path          # ODM's bare-ground DEM, terrain-first + detection
    ortho: Path        # ODM's orthophoto, ground texture + detection


def scene_paths(root: str | Path, name: str) -> ScenePaths:
    base = Path(root) / "work" / name
    dem = base / "odm" / "odm_dem"
    return ScenePaths(
        name=name,
        base=base,
        frames=base / "frames",
        odm=base / "odm",
        mesh_dir=base / "mesh",
        raw_glb=base / "mesh" / f"sraw_{name}.glb",
        styled_glb=base / "mesh" / f"sf_{name}.glb",
        base_glb=base / "mesh" / f"_base_{name}.glb",
        features=base / "features.json",
        obj=base / "odm" / "odm_texturing" / "odm_textured_model_geo.obj",
        dsm=dem / "dsm.tif",
        dtm=dem / "dtm.tif",
        ortho=base / "odm" / "odm_orthophoto" / "odm_orthophoto.tif",
    )


def manifest_path(root: str | Path) -> Path:
    return Path(root) / MANIFEST_REL


def load_manifest(root: str | Path) -> dict:
    p = manifest_path(root)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    return {"scenes": {}}


def upsert_scene(root: str | Path, name: str, entry: dict) -> dict:
    """Add/replace a scene entry and write the manifest. Returns the full manifest.

    glb paths are stored repo-relative so the manifest is portable on this machine.
    """
    root = Path(root)
    data = load_manifest(root)
    data.setdefault("scenes", {})[name] = entry
    p = manifest_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return data
