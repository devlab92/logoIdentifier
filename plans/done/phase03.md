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
- [x] `pytest` green (multi-scale synthetic cases pass) — 122 passed.
- [x] BENCHMARKS has `sift` and `ocr+sift` rows on the real labeled set (100/158).
- [x] Missing `logo/` degrades gracefully (warning once, signal scores 0, scan continues).

## Verify
```powershell
python -m logoscanner benchmark --labeled data\labeled --signals ocr,sift
pytest -q
```

## Out of scope
- Embeddings, detectors, threshold calibration.

## Progress Log
- `logoscanner/keypoints.py` written: `SiftSignal` + `Template`, per-directory template cache,
  alpha-aware grayscale (transparent pixels filled opposite to the mark's brightness, so a
  white-on-transparent variant survives), tiny variants upscaled to `SIFT_MIN_SIDE`.
- **Failure found while probing the real logos:** with a plain Lowe ratio test, RANSAC returned
  homographies with 40+ "inliers" that folded the whole logo onto a single point - many template
  descriptors were matching the *same* image keypoint. Fixed by keeping one match per image
  location, plus `plausible_box` (convex, real area, sane edges/aspect, centred in frame). D-017.
- **The phase01 dummy logo turned out to be invisible to SIFT** (flat silhouette, six-fold
  symmetry): every synthetic case scored 0 at any threshold. `tools/make_dummy_logo.py` now draws
  interior detail on a 720x240 canvas; worst synthetic case clears 10 inliers vs the floor of 8,
  backgrounds still score 0. D-018.
- Config: `LOGO_DIR` + `SIFT_*` knobs; `ENABLED_SIGNALS = ("ocr", "sift")`.
- `benchmark` gained the naive-OR row (D-019) so `--signals ocr,sift` reports what the pipeline
  would actually ship; `PHASE` constant stamps the BENCHMARKS rows.
- Tests: `tests/test_keypoints.py` (21 cases) + two CLI cases; autouse fixture points
  `config.LOGO_DIR` at an empty temp folder so no test can read the real `logo/` (D-020).

## Completion Report

**Done 2026-09-04.**

**What shipped:** `logoscanner/keypoints.py` (`SiftSignal`), the `SIFT_*` tunables and `LOGO_DIR`
in `config`, a naive-OR row in `benchmark`, a regenerated fake test mark, 25 new tests.

**Numbers (100 positive / 158 negative, real set):**

| signal | precision | catch-recall | review | img/s |
|---|---|---|---|---|
| ocr | 0.875 | 0.930 | 8.5% | 0.73 |
| sift | 1.000 | 0.550 | 14.3% | 3.97 |
| ocr+sift | 0.875 | **0.940** | 8.9% | 0.62 (~4.5 h for 10k) |

**The honest result:** SIFT is *precise* — 55 of 100 positives, and only 2 of 158 negatives ever
score above zero — but it rescued only **1 of the 7 OCR-blind positives** (an AUSNOG banner, 17
inliers). The remaining 6 (`fgJCL84Y.jpg`, `Networking-Field-Day-9123_400x250.jpg`,
`NSCP-CE-Diagram.png`, `Screen-Shot-2020-09-23-at-8.33.59-PM.jpg`, `Untitled-1-1-1.png`,
`ZPE-Systems-Frank-Basso.webp`) have neither readable brand text nor matchable symbol geometry at
the resolution they survive at. Catch-recall moved 0.930 -> 0.940; the phase04 gate now has a real
decision to make, and the two logo variants in `logo/` are both full wordmarks — a symbol-only
mark would be the cheapest next lever.

**Surprises worth remembering:** RANSAC will "verify" a homography that folds the logo onto a
single point when many template descriptors match one image keypoint (D-017), and the phase01
dummy logo was too flat and too symmetric for SIFT to see at all, so the synthetic tests were
silently unable to exercise the signal until the mark was redrawn (D-018).

**Deviations from the plan:** none in scope. `tools/make_dummy_logo.py` and its committed asset
had to be regenerated (D-018), and `benchmark` gained the combined row the plan asked for in its
docs step (D-019).
