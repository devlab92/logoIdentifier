# phase03 — SIFT Signal (symbol matching)

**Goal:** keypoint-matching signal that finds the logo symbol at any scale/rotation, with geometric verification for precision.
**Depends on:** phase02
**Conditional?** no

## Context to load
- `docs/CODEMAP.md`, `logoscanner/{config,signals,pipeline}.py`

## User prerequisites
- Real logo variants in `logo/` (tests fall back to `tests/assets/dummy_logo.png`; if `logo/` is empty at scan time, warn and skip the signal).

## Steps
1. `logoscanner/keypoints.py` — `SiftSignal`:
   - On init: load every image in `logo/` (grayscale; upscale tiny variants to ~300 px min side), compute SIFT descriptors once per variant.
   - Per image: downscale to `MAX_SIDE` (keep the scale factor), SIFT detect, `BFMatcher.knnMatch(k=2)`, Lowe ratio 0.75.
   - If good matches ≥ `SIFT_MIN_GOOD` (start 8): `cv2.findHomography(..., RANSAC)`; require inliers ≥ `SIFT_MIN_INLIERS` (start 8) **and** a sane projected box (convex, positive area, plausible size, inside image). Score `= min(1, inliers / SIFT_SCORE_NORM)` (start 25). Bbox = projected logo corners scaled back to original coordinates. Best across variants wins.
2. Config: `SIFT_MIN_GOOD`, `SIFT_MIN_INLIERS`, `SIFT_SCORE_NORM`, provisional strong/weak thresholds.
3. Register in the pipeline; `benchmark --signals sift` and `--signals ocr,sift` must work.
4. Tests (synthetic, dummy logo): pasted at 0.4×/1.0×/1.5× and ±10° → detected with valid bbox; pure-negative image → score ≈ 0; degenerate homography rejected.
5. Docs: CODEMAP, CHANGELOG, BENCHMARKS rows (sift alone; ocr+sift naive-OR).

## Acceptance criteria
- [ ] `pytest` green (multi-scale synthetic cases pass).
- [ ] BENCHMARKS has `sift` and `ocr,sift` rows on the labeled set (or flagged synthetic fallback).
- [ ] Missing `logo/` degrades gracefully (warning, signal skipped).

## Verify
```powershell
python -m logoscanner benchmark --labeled data\labeled --signals ocr,sift
pytest -q
```

## Out of scope
- Embeddings, detectors, threshold calibration.

## Progress Log

## Completion Report
