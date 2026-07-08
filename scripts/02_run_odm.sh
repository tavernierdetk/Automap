#!/usr/bin/env bash
# Stage 2 - OpenDroneMap photogrammetry (thin Docker wrapper). THE SWAPPABLE BOX.
#
# Reads a frames folder, produces a textured .obj in work/odm/. ODM quality knobs
# come from config.toml [odm]; defaults were proven viable on this M4 by ADR 0001
# (32 imgs -> textured .obj in 8m30s, peak 2.81 GiB of a 12 GiB Docker VM).
#
#   scripts/02_run_odm.sh                          # work/frames -> work/odm
#   scripts/02_run_odm.sh --frames samples/frames  # smoke-test on the sample set
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRAMES_DIR="$ROOT/work/frames"
OUT_DIR="$ROOT/work/odm"
CONFIG="$ROOT/config.toml"
IMAGE="opendronemap/odm:latest"
TERRAIN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --frames) FRAMES_DIR="$2"; shift 2;;
    --output) OUT_DIR="$2"; shift 2;;
    --config) CONFIG="$2"; shift 2;;
    --terrain) TERRAIN=1; shift;;   # also produce DSM/DTM + orthophoto for terrain-first
    -h|--help) sed -n '2,12p' "$0"; exit 0;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

# --- ODM knobs from config.toml [odm] (tomllib needs python 3.11+) ---
eval "$(python3 - "$CONFIG" <<'PY'
import tomllib, sys, shlex
d = tomllib.load(open(sys.argv[1], "rb")).get("odm", {})
def emit(k, default): print(f'{k.upper()}={shlex.quote(str(d.get(k, default)))}')
emit("feature_quality", "medium")
emit("pc_quality", "low")
emit("max_concurrency", 4)
emit("end_with", "mvs_texturing")
emit("dem_resolution", 5)
emit("orthophoto_resolution", 8)
emit("auto_boundary", True)
PY
)"

# Crop to the camera footprint (drops far-away sea/horizon outliers).
boundary_arg=()
if [[ "$AUTO_BOUNDARY" == "True" ]]; then
  boundary_arg=(--auto-boundary)
fi

# Terrain-first also needs the elevation model + orthophoto; run through to it.
terrain_arg=()
if [[ "$TERRAIN" == "1" ]]; then
  END_WITH="odm_orthophoto"
  terrain_arg=(--dsm --dtm --dem-resolution "$DEM_RESOLUTION" --orthophoto-resolution "$ORTHOPHOTO_RESOLUTION")
fi

# --- assemble an ODM project: <OUT_DIR>/images/ + optional geo.txt ---
shopt -s nullglob
frames=("$FRAMES_DIR"/*.jpg "$FRAMES_DIR"/*.JPG)
if [[ ${#frames[@]} -eq 0 ]]; then
  echo "stage 2: no .jpg frames in $FRAMES_DIR (run stage 1 first?)" >&2
  exit 1
fi

echo "[stage 2] frames: ${#frames[@]} from $FRAMES_DIR"
echo "[stage 2] knobs: feature-quality=$FEATURE_QUALITY pc-quality=$PC_QUALITY max-concurrency=$MAX_CONCURRENCY end-with=$END_WITH"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR/images"
cp "${frames[@]}" "$OUT_DIR/images/"

geo_arg=()
if [[ -f "$FRAMES_DIR/geo.txt" ]]; then
  cp "$FRAMES_DIR/geo.txt" "$OUT_DIR/geo.txt"
  geo_arg=(--geo /datasets/code/geo.txt)
  echo "[stage 2] georeferencing with geo.txt"
else
  echo "[stage 2] no geo.txt - ODM solves blind"
fi

# --- run ODM (amd64 via Rosetta on Apple Silicon) ---
SECONDS=0
docker run -i --rm --platform linux/amd64 \
  -v "$OUT_DIR":/datasets/code \
  "$IMAGE" \
  --project-path /datasets \
  --feature-quality "$FEATURE_QUALITY" \
  --pc-quality "$PC_QUALITY" \
  --max-concurrency "$MAX_CONCURRENCY" \
  --end-with "$END_WITH" \
  ${geo_arg[@]+"${geo_arg[@]}"} \
  ${terrain_arg[@]+"${terrain_arg[@]}"} \
  ${boundary_arg[@]+"${boundary_arg[@]}"} \
  code

# --- report outputs ---
echo "[stage 2] done in ${SECONDS}s ($((SECONDS/60))m$((SECONDS%60))s)"
obj="$(find "$OUT_DIR/odm_texturing" -maxdepth 1 -iname '*.obj' 2>/dev/null | head -1 || true)"
if [[ -n "$obj" ]]; then
  echo "[stage 2] textured mesh: $obj"
else
  echo "[stage 2] WARNING: no textured .obj found under $OUT_DIR/odm_texturing" >&2
  exit 1
fi
if [[ "$TERRAIN" == "1" ]]; then
  for f in odm_dem/dtm.tif odm_dem/dsm.tif odm_orthophoto/odm_orthophoto.tif; do
    [[ -f "$OUT_DIR/$f" ]] && echo "[stage 2] terrain: $OUT_DIR/$f" \
      || echo "[stage 2] WARNING: expected $f missing" >&2
  done
fi
