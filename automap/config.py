"""Load pipeline tunables from config.toml into typed dataclasses.

Missing file or missing keys fall back to the defaults below, so the pipeline is
runnable before config.toml is customized.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass
class FramesConfig:
    fps: float = 1.0
    max_frames: int = 120
    sharpness_threshold: float = 80.0
    resize: int = 2048
    jpeg_quality: int = 90


@dataclass
class OdmConfig:
    feature_quality: str = "medium"
    pc_quality: str = "low"
    max_concurrency: int = 4
    end_with: str = "mvs_texturing"


@dataclass
class MeshConfig:
    decimate_ratio: float = 0.25


@dataclass
class Config:
    frames: FramesConfig
    odm: OdmConfig
    mesh: MeshConfig


def _build(cls, data: dict):
    """Construct a dataclass from a dict, ignoring unknown keys."""
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known})


def load_config(path: str | Path = "config.toml") -> Config:
    data: dict = {}
    p = Path(path)
    if p.exists():
        with open(p, "rb") as f:
            data = tomllib.load(f)
    return Config(
        frames=_build(FramesConfig, data.get("frames", {})),
        odm=_build(OdmConfig, data.get("odm", {})),
        mesh=_build(MeshConfig, data.get("mesh", {})),
    )
