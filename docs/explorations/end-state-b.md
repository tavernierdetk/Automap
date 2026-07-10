# Exploration — End-state B: a walkable scene from public data only

**Status: BUILT (2026-07-10).** `lagrave` exists end-to-end from public data:
`02b_fetch_geodata.py` (HRDEM COG windowed fetch, coverage-probed — the STAC
search's first hit was a Nova Scotia survey whose footprint over-claims,
skipped by a 32×32-pixel probe) → 1216×1220 @ 1 m DTM/DSM in UTM 20N, 100%
valid → `03b` untextured terrain (81% flattened sea at −0.5 m — faithful:
La Grave is a spit, only 15% of the box sits above 1 m) → stage 5 in geodata
mode (no ortho → no scan detection; 126 OSM footprints + 57 roads + sea
through the fusion engine, doc validates against scene-features@2.0.0) →
madelinot styling (121 buildings, 56 roads placed) →
`res://scenes/lagrave/sf_lagrave.tscn`. **Zero drone footage involved.**
Brief §9 step 3 / §6 end-state B: pick a bbox with **no drone footage**,
build the same walkable styled scene from public elevation + OSM through
the same funnel. Proves "same funnel, different intake" with zero new
research.

## The bbox

**La Grave, Havre-Aubert, Îles-de-la-Madeleine** (47.2375, −61.8353,
geocoded via Nominatim) — a heritage site ~10 km from the existing drone
scenes (mountain_cross, phare), so the madelinot visual identity applies
unchanged and outputs are directly comparable. ~1.4 km box around it.

## Probe results (throwaway, 3 commands)

NRCan datacube STAC (`datacube.services.geo.ca/stac/api`) has collections
`hrdem-lidar` / `hrdem-mosaic-1m` / `hrdem-mosaic-2m` / `mrdem-30`; a STAC
bbox search over the islands returns a **dedicated 2019 LiDAR acquisition**:

    QC-600019_30_IlesDeLaMadeleine_MTM4_2019-1m   (collection hrdem-lidar)
    assets: dtm, dsm (COG GeoTIFFs on S3, ca-central-1), extent, coverage

- Mosaic is EPSG:3979 (NAD83-CSRS Canada Atlas Lambert), 1 m, nodata −32767,
  49880×94820 px total.
- **COG windowed reads over plain HTTPS work in rasterio**: our 1.4 km bbox
  reads as a 1375×1375 window, 99% valid, in seconds — no bulk download.
- Values are sane: DTM −0.9..16.7 m (sea ≈ 0, Butte Ronde ~17 m), DSM up to
  26.0 m — ~9 m of buildings/vegetation above ground. **DSM−DTM canopy is
  available from public data**, so LiDAR-only tree detection is a natural
  follow-up (needs a no-RGB mode in detect_trees; out of scope for slice 1).

## Design (v1 slice)

- `automap/geodata.py` — the `ingest-geodata` module of the diagram:
  STAC search → prefer the newest `hrdem-lidar` item covering the bbox
  (fall back to `hrdem-mosaic-1m`) → windowed read → **reproject to the
  bbox's UTM zone** (consistency with the drone path; EPSG:326xx) → write
  `work/<scene>/geodata/{dtm,dsm}.tif`. Network only in fetch functions;
  cache-if-exists like osm.json (re-runs offline).
- Stage 3b: `--ortho` becomes optional — no public orthophoto in slice 1;
  untextured terrain takes the identity's ground styling in stage 6.
- Stage 5: `--ortho` optional too — without RGB there is no scan detection;
  the OSM batch flows through the **fusion engine** alone (buildings
  backfilled with tag/default heights, roads, water). Second real provider
  through worldmodel v1, as designed.
- Stage 6/7 unchanged: madelinot identity, publish contract.

Licensing note (brief §7.6): HRDEM is Canada Open Government Licence
(attribution, no share-alike); OSM feature layer stays ODbL — same posture
as the drone scenes.

## Follow-ups surfaced

- LiDAR CHM tree detection (no-RGB gates) — would populate trees without
  a scan; the detector backend also maps to a genserver job later.
- Québec open orthophotos as ground texture (separate provider).
- Overture buildings as a second footprint source through the same fusion.
