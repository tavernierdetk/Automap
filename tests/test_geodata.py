"""Geodata provider tests — pure logic + a local GeoTIFF standing in for the
remote COG (rasterio opens paths and URLs identically), so no network."""
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from automap.geodata import candidates, fetch_dem, has_coverage, utm_epsg


def test_utm_epsg():
    assert utm_epsg(-61.835, 47.237) == "EPSG:32620"   # Îles-de-la-Madeleine
    assert utm_epsg(-73.6, 45.5) == "EPSG:32618"       # Montréal
    assert utm_epsg(147.0, -42.9) == "EPSG:32755"      # southern hemisphere


def _item(id_, dt=None, assets=("dtm", "dsm")):
    return {"id": id_, "collection": "x",
            "properties": {"datetime": dt},
            "assets": {a: {"href": f"https://x/{id_}-{a}.tif"} for a in assets}}


def test_candidates_order_newest_lidar_then_mosaic():
    lidar = [_item("QC-old_2016-1m", "2016-08-01T00:00:00Z"),
             _item("QC-new_2019-1m", "2019-08-01T00:00:00Z"),
             _item("dtm-only", assets=("dtm",))]      # incomplete: dropped
    mosaic = [_item("10_3-mosaic-1m")]
    ids = [c["id"] for c in candidates(lidar, mosaic)]
    assert ids == ["QC-new_2019-1m", "QC-old_2016-1m", "10_3-mosaic-1m"]
    assert candidates([], []) == []


@pytest.fixture()
def fake_cog(tmp_path):
    """A small 'national mosaic' in EPSG:3979 with a known ramp surface."""
    H = W = 400
    x = np.linspace(0.0, 20.0, W, dtype=np.float32)
    data = np.tile(x, (H, 1))                       # east-west ramp 0..20 m
    # anchor roughly at the Magdalen Islands in EPSG:3979
    transform = from_origin(2_204_000, 1_035_000, 5.0, 5.0)
    p = tmp_path / "mosaic.tif"
    with rasterio.open(p, "w", driver="GTiff", count=1, dtype="float32",
                       width=W, height=H, crs="EPSG:3979",
                       transform=transform, nodata=-32767.0) as ds:
        ds.write(data, 1)
    return p


def test_fetch_dem_windows_and_reprojects(fake_cog, tmp_path):
    # a bbox inside the fake raster (found by inverse-projecting its center)
    from rasterio.warp import transform_bounds
    with rasterio.open(fake_cog) as ds:
        w, s, e, n = transform_bounds(ds.crs, "EPSG:4326", *ds.bounds)
    cx, cy = (w + e) / 2, (s + n) / 2
    bbox = (cx - (e - w) / 6, cy - (n - s) / 6, cx + (e - w) / 6, cy + (n - s) / 6)

    assert has_coverage(str(fake_cog), bbox)
    # a bbox far outside the raster has pixels nowhere
    assert not has_coverage(str(fake_cog), (w + 5.0, s + 5.0, e + 5.0, n + 5.0))

    out = fetch_dem(str(fake_cog), bbox, tmp_path / "dtm.tif", resolution=5.0)
    with rasterio.open(out) as ds:
        assert ds.crs.to_string() == utm_epsg(cx, cy)   # reprojected to UTM
        arr = ds.read(1)
        valid = arr != ds.nodata
        assert valid.mean() > 0.8                       # window mostly covered
        vals = arr[valid]
        assert 0.0 <= vals.min() and vals.max() <= 20.0  # ramp values preserved
        assert vals.std() > 1.0                          # it's still a ramp
        assert abs(ds.transform.a) == 5.0                # requested resolution


# --- GeoJSON intake (the neighbourhood-polygon front door) ---------------------

def test_geojson_bounds_walks_any_nesting():
    from automap.geodata import geojson_bounds
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {},
         "geometry": {"type": "Polygon",
                      "coordinates": [[[-73.58, 45.51], [-73.56, 45.51],
                                       [-73.56, 45.52], [-73.58, 45.52], [-73.58, 45.51]]]}},
        {"type": "Feature", "properties": {},
         "geometry": {"type": "Point", "coordinates": [-73.59, 45.515]}},
    ]}
    assert geojson_bounds(fc) == (-73.59, 45.51, -73.56, 45.52)
    # a bare geometry works too
    assert geojson_bounds({"type": "Point", "coordinates": [1.0, 2.0]}) == (1.0, 2.0, 1.0, 2.0)


def test_geojson_bounds_rejects_empty():
    import pytest
    from automap.geodata import geojson_bounds
    with pytest.raises(ValueError):
        geojson_bounds({"type": "FeatureCollection", "features": []})


# --- LiDAR building heights (the MTL eval's #1 gap) ----------------------------

def test_building_heights_from_dems(tmp_path):
    import numpy as np
    from automap.geodata import building_heights_from_dems

    # 60x60 grid at 1 m, centered frame: dtm flat 100, dsm adds a 12 m block
    # at scene coords x,z in [-10,0] and a 4 m one in [10,20]x[10,20]
    H = W = 60
    dtm = np.full((H, W), 100.0, dtype="float32")
    dsm = dtm.copy()

    def cell(x, z):  # scene xz -> row/col (px=1)
        return int(round(z + (H - 1) / 2)), int(round(x + (W - 1) / 2))

    r0, c0 = cell(-10, -10); r1, c1 = cell(0, 0)
    dsm[r0:r1, c0:c1] += 12.0
    r0, c0 = cell(10, 10); r1, c1 = cell(20, 20)
    dsm[r0:r1, c0:c1] += 4.0

    t = from_origin(500000, 5000000, 1, 1)
    for name, arr in (("dtm.tif", dtm), ("dsm.tif", dsm)):
        with rasterio.open(tmp_path / name, "w", driver="GTiff", count=1,
                           dtype="float32", width=W, height=H,
                           crs="EPSG:32618", transform=t, nodata=-9999) as ds:
            ds.write(arr, 1)

    fps = [
        [[-9, -9], [-1, -9], [-1, -1], [-9, -1]],     # inside the 12 m block
        [[11, 11], [19, 11], [19, 19], [11, 19]],     # inside the 4 m block
        [[-25, 20], [-18, 20], [-18, 27], [-25, 27]], # empty ground -> None
    ]
    hs = building_heights_from_dems(tmp_path / "dtm.tif", tmp_path / "dsm.tif", fps)
    assert abs(hs[0]["height"] - 12.0) < 0.5 and abs(hs[0]["ridge"] - 12.0) < 0.5
    assert abs(hs[1]["height"] - 4.0) < 0.5
    assert hs[2] is None
