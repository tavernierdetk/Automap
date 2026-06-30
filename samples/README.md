# samples/

A tiny, **already-extracted** frame set so the pipeline can run green from stage 2
onward **before** any real footage exists (per design spec §5, §9).

- `frames/` — 32 JPEGs (`frame_00001.jpg` …), downscaled to 800px longest edge.
  These are *pre-extracted frames*, i.e. what stage 1 would normally produce. Point
  stage 2 (ODM) at this folder directly to smoke-test reconstruction:

  ```
  scripts/02_run_odm.sh --frames samples/frames        # (stage 2, built later)
  ```

These are **not** for testing stage 1 itself — that stage needs a *video*, and its
unit tests generate a synthetic clip on the fly (nothing binary is committed).

## Attribution

Derived (downscaled) from the **Sheffield Park 3** dataset by Piero Toffanin,
distributed under the BSD 2-Clause License. See `ATTRIBUTION.md`.
Source: https://github.com/pierotofy/drone_dataset_sheffield_park_3
