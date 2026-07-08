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
class TerrainConfig:
    grid_resolution: int = 256       # grid cells on the long edge
    z_exaggeration: float = 1.0      # vertical scale multiplier


@dataclass
class FeaturesConfig:
    min_height: float = 2.0          # min canopy height (m) to count as a tree
    max_height: float = 40.0         # taller than this = reconstruction junk
    exg_threshold: float = 0.05      # min excess-green index (vegetation)
    gob_threshold: float = 0.02      # min green-over-blue index (water veto)
    max_slope_deg: float = 30.0      # reject peaks on steeper bare ground (cliffs)
    edge_margin_m: float = 3.0       # distrust pixels this close to no-data (melt zone)
    min_spacing_m: float = 3.0       # min spacing between detected tree tops
    prominence_min: float = 2.0      # peak must stand this far above nearby low surface
    prominence_radius_m: float = 12.0  # neighbourhood for the prominence reference
    min_area_m2: float = 3.0         # smallest believable crown area
    max_radius_m: float = 8.0        # crown radius cap
    min_support_density: float = 1.0  # min reconstruction pts/m^2 under a crown
    # building detection (clusters of building-classified cloud points)
    bld_min_points: int = 25         # min points in a cluster
    bld_min_height: float = 2.0      # cluster's p75 height-above-ground must reach this
    bld_max_height: float = 25.0     # ridge taller than this = reconstruction junk
    bld_min_area_m2: float = 12.0    # smallest believable footprint
    bld_max_area_m2: float = 1500.0  # larger than this = melt sheet
    bld_min_fill: float = 0.35       # cluster area / bounding-rect area (streak filter)
    bld_min_side_m: float = 2.5      # bounding rect's short side (streak filter)
    bld_max_blueness: float = 15.0   # median B-R above this = sea surface, not a roof
    gable_delta: float = 1.0         # ridge - wall height (m) to call a roof gabled
    # OSM overlay (buildings cross-check/backfill; needs network once, then cached)
    osm_match_dist_m: float = 12.0   # centroid distance to pair a detection with OSM
    osm_default_wall: float = 3.0    # wall height for untagged OSM-only buildings
    osm_default_ridge: float = 5.0   # ridge height for untagged OSM-only buildings
    osm_level_m: float = 3.0         # meters per building:levels tag level


@dataclass
class Config:
    frames: FramesConfig
    odm: OdmConfig
    mesh: MeshConfig
    terrain: TerrainConfig
    features: FeaturesConfig


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
        terrain=_build(TerrainConfig, data.get("terrain", {})),
        features=_build(FeaturesConfig, data.get("features", {})),
    )
