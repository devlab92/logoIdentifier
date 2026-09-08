# Changelog

> Newest first. One dated block per working session that changed the repo.

## 2026-09-08 - phase05
- **The gate PASSED (D-029): catch-recall 0.980, precision 0.873, review share 8.9%, 0.45 img/s
  on the corrected labeled set. phase06 (fine-tuned nano detector) is skipped.** Calibrated over
  three signals: emb 0.85/0.95, ocr 0.75/0.85, sift 0.45/0.45. Attainable recall ceiling 0.940 ->
  1.0. Misses 6 -> 2.
- **Two positives were mislabeled** (D-028): `ZPE-Systems-Frank-Basso.webp` and `fgJCL84Y.jpg`
  contain no logo at all - the user confirmed it after they had been used to justify phase05.
  Moved to `data/labeled/negative/`; the set is now **98/160**. Removing them improved precision,
  recall *and* review share simultaneously, because they were noise rather than difficulty.
- phase05 was still necessary: phase04's detector re-scored on the corrected labels reaches only
  catch-recall 0.959, short of the 0.97 target.
- Checked the cheap lever first: the symbol-only logo variant the user added to `logo/` is live
  (3 SIFT templates, 120 descriptors on the symbol) but changed nothing - byte-identical metrics.
- Diagnosed the six phase04 misses individually: two carry the product wordmark "Nodegrid" at
  0.98-1.00 OCR confidence (out of scope by user decision - ZPE marks only), one is a wordmark
  OCR garbles to two characters, two were the mislabeled photos above.
- New `logoscanner/proposals.py`: candidate regions from OCR line boxes, MSER blobs grouped into
  whole marks, caller-supplied boxes, and an always-kept 3x3 tile grid + full frame; padded,
  area-filtered, IoU-merged and budget-capped.
- New `logoscanner/embeddings.py`: `emb` signal - frozen DINOv2-small on CPU, each candidate crop
  embedded in one batch and scored by max cosine against every `logo/` variant (alpha variants
  composited on white *and* black). Degrades to "warn once, score 0" with no torch, no checkpoint
  or no `logo/`. Added to `ENABLED_SIGNALS`.
- Dependencies: `torch 2.14.0+cpu` + `timm 1.0.29` (~2 GB) plus an ~85 MB checkpoint fetched once
  (D-024). User-approved. Verified to load fully offline with `HF_HUB_OFFLINE=1`.
- Fixed: OpenCV 5's MSER silently returns nothing for single-channel input (D-025) - the obvious
  grayscale conversion would have disabled the source with no error.
- Fixed: MSER returns one blob per letter; `group_boxes` glues them into whole marks.
- Fixed: region proposals re-ran OCR, doubling scan cost. `ocr.read_text` is now memoised on a
  content hash (D-026): 4.13 s cold, 0.004 s warm, and a one-pixel change re-runs it.
- Fixed: `calibrate.search` stored its grid index as tuples - ~1 GB at three signals. The index is
  now decoded arithmetically and the metric vectors are float32 (D-027): 9.26 M combinations in
  ~12 s, ~110 MB.
- Fixed: a passing `calibrate` run now deletes a stale `output/gate_failures.txt` instead of
  leaving a file that still says FAILED.
- Fixed: `test_the_live_config_thresholds_are_used_by_default` assumed OCR keeps a review band. It
  now covers every calibrated signal and adapts to `weak == strong`.
- Tests: `tests/test_proposals.py` (26) and `tests/test_embeddings.py` (20, four marked `slow`),
  plus three-signal and stale-gate-file cases in `test_calibrate.py`. `pytest.ini` registers the
  `slow` marker; the fast suite is `pytest -m "not slow"`.
- Measured: embedding stage ~0.33 s/image steady-state.

## 2026-09-04 - phase04: decision engine, calibration & THE GATE
- `logoscanner/decision.py`: per-signal `(weak, strong)` thresholds, OR over the band each signal
  claims (not over raw scores), normalized confidence anchored on `REVIEW_THRESHOLD` /
  `POSITIVE_THRESHOLD`, `method` naming every winning signal (D-021). `pipeline.py` is now
  orchestration only and re-exports `decide` / `Decision`; the provisional phase02 rule is gone.
- `logoscanner/metrics.py`: `score_images` (one pass, per-file scores kept) + `evaluate`
  (precision, catch-recall, review share, confusion counts, per-signal wins, miss filenames).
  `benchmark.score_labeled` is now an adapter over it, so the repo has one loading loop.
- `logoscanner/calibrate.py` + `python -m logoscanner calibrate`: vectorised grid search over
  every signal's threshold pair (44,100 combinations), objective = max precision subject to
  catch-recall >= 0.97 and review <= 10%, relaxed to the attainable ceiling when unreachable
  (D-022). Writes `output/calibration.json`, rewrites the marked block in `config.py`, prints the
  gate verdict, and writes `output/gate_failures.txt` when it fails.
- Calibrated on the real set (100/158): OCR 0.60/0.95, SIFT 0.45/0.45 → precision **0.882**,
  catch-recall **0.940**, review share **7.0%**, 6 misses (D-023).
- **GATE FAILED** on catch-recall (0.940 < 0.97). The 6 misses score 0 on *both* signals - no
  threshold can recover them - so phase05 (region proposals + embeddings) runs; phase06 stays
  conditional on it.
- Tests: `test_decision.py`, `test_metrics.py`, `test_calibrate.py` + `calibrate` CLI coverage.
  Suite 122 -> 161 green.
- Docs: ARCHITECTURE (bands + calibration flow), CODEMAP, SETUP (command + outputs + phase04
  smoke test), BENCHMARKS (calibrated row + post-calibration sweep rows), D-021 / D-022 / D-023.
- Throughput this session is not comparable to phase03's: every phase04 run shared the CPU with
  the test suite (0.21-0.29 img/s vs 0.62). No performance work was done or intended.

## 2026-09-04 - phase03
- `logoscanner/keypoints.py`: `SiftSignal` (registered as `"sift"`). SIFT descriptors are computed
  once per variant in `logo/` (grayscale, alpha-aware, tiny variants upscaled to 300 px), matched
  per image with a Lowe ratio test, and verified by a RANSAC homography; score =
  `min(1, inliers / 25)`, bbox = the projected logo corners in the original image's coordinates.
- **Two failures found and fixed while probing the real logos (D-017):** a plain ratio test let
  many template descriptors match the *same* image keypoint, and RANSAC then "verified" the
  homography folding the logo onto that single point - 40+ inliers on an image containing nothing.
  Matches are now kept one per image location, and the projected quad must be convex, have real
  area, keep sane edges/aspect and be centred in the frame (`plausible_box`).
- **The phase01 dummy logo was invisible to SIFT (D-018):** a flat, six-fold-symmetric silhouette
  gives almost no usable descriptors, so every synthetic case scored 0 at any threshold and the
  signal could not be tested at all. `tools/make_dummy_logo.py` now draws interior detail on a
  720x240 canvas; `tests/assets/dummy_logo.png` regenerated.
- `logoscanner/config.py`: `LOGO_DIR` and the `SIFT_*` tunables (min side, Lowe ratio, min good
  matches / inliers, RANSAC reprojection, score norm, box-plausibility limits);
  `ENABLED_SIGNALS = ("ocr", "sift")`.
- `logoscanner/benchmark.py`: `combine()` adds a naive-OR row when several signals are requested,
  so `--signals ocr,sift` shows what a scan actually ships (D-019); rows are stamped `phase03`.
- Missing or empty `logo/` warns once and the signal scores 0 for every image - a scan still runs
  on OCR alone. Tests never read the real `logo/`: an autouse fixture points `config.LOGO_DIR` at
  an empty temp folder, and `fake_logo_dir` serves the committed fake mark (D-020).
- Tests: `tests/test_keypoints.py` (scale 0.4x/1.0x/1.5x, +/-10 degrees, bbox in original
  coordinates incl. images over `MAX_SIDE`, degenerate-homography rejection, template building,
  graceful skip) plus SIFT scan and combined-benchmark cases in `test_cli.py`. Suite 97 -> 122.
- Benchmark (100 positive / 158 negative): sift alone catch-recall **0.550** at precision
  **1.000** (only 2 negatives ever score above 0), 3.97 img/s. Combined `ocr+sift` catch-recall
  **0.940** / precision 0.875 / review 8.9%, 0.62 img/s (~4.5 h for 10k). SIFT rescues **1 of the
  7 OCR-blind positives**; the other 6 carry no readable text *and* no matchable symbol geometry,
  so they stay invisible to both signals - the case phase04's gate has to judge.

## 2026-09-04 - phase02
- Dependency: `rapidocr-onnxruntime==1.4.4` (+ its onnxruntime/pillow/shapely stack). The ONNX
  models ship inside the wheel, so the runtime stays offline; engine init ~2.3 s per process.
  D-015; `pillow` also listed explicitly because `io_utils` now imports it.
- `logoscanner/signals.py`: `SignalResult` (name, score clamped to [0,1], bbox, detail), the
  `Signal` protocol and a name registry, so `config.ENABLED_SIGNALS` and `--signals ocr,...`
  select detectors as plain strings.
- `logoscanner/ocr.py`: `OcrSignal`. RapidOCR reads the text lines, each is normalised twice
  (spaced "z p e" and compact "zpesystems") and fuzzy-matched against `BRAND_TERMS`;
  `score = fuzz/100 x ocr_confidence`, best line's box returned. `partial_ratio` is used only
  when the line is the longer string, otherwise a three-letter fragment would read as a brand
  hit (D-013). Engine failures become a 0.0 score, never an exception.
- `logoscanner/pipeline.py`: runs the enabled signals and applies the OR rule (strongest signal
  wins, silent ones cannot dilute it); `Decision.to_row` feeds the CSV. `scan` now emits real
  confidences, methods and boxes. Bands provisional at 0.85 / 0.60 until phase04.
- `logoscanner/benchmark.py` + `benchmark` subcommand: scores `positive/` + `negative/`, sweeps
  a 0.05-step (review, positive) grid, prints per-threshold recall/precision and the recall-first
  operating point (D-014), and appends a row to `docs/BENCHMARKS.md` (`--no-record` to skip).
- `tools/make_synthetic.py --with-text [RATIO]`: renders the first brand term on a contrasting
  plaque into that share of the positives (bare flag = 0.6), which makes the OCR path testable
  without company images.
- **AVIF gap found while benchmarking:** 11 of the 258 labeled files are AVIF, which the
  opencv-python wheels cannot decode - and the walker's extension filter was dropping them
  *silently*, 2 of them positives. `io_utils.load_image` now retries with Pillow and `.avif`
  joined `IMAGE_EXTS` (D-016). Genuinely broken files still surface as `decode failed`.
- Tests: `test_signals.py`, `test_ocr.py`, `test_pipeline.py`, `test_benchmark.py`, plus new
  AVIF and `--with-text` cases. Walk/load tests in `test_cli.py` pin `signals=()` so OCR
  hallucinations on procedural noise cannot make them flaky. Suite 34 -> 97 green.
- Benchmark (100 positive / 158 negative, OCR only): catch-recall **0.930**, precision **0.875**,
  review share **8.5%** at `t_rev=0.60 / t_pos=0.95`; 0.55 img/s, ~5.1 h for 10k. The 7 misses
  carry no readable brand text at all - that is SIFT's job in phase03.

## 2026-09-03 - side tool: WordPress image collection
- `tools/wp_collect.py`: walks a WordPress `uploads/<year>/<month>/` tree and copies one file per
  logical image to `input/wp_originals/<YYYY-MM>/<original filename>`, ignoring generated `-WxH`
  thumbnails, `.bak` optimizer backups and webp/avif conversions of an existing jpg/png.
- Filenames are preserved verbatim (needed later to map an image back to its post); the month
  folder disambiguates the 66 names that recur across months. One name of 3,494 was shortened to
  stay under the Windows 260-char path limit - the manifest keeps its `original_name`.
- Run against `Desktop/WP/wp-content/uploads`, years 2014-2026: 34,874 files -> 3,494 images
  (0.34 GB) over 120 month folders. Manifest at `input/wp_originals_manifest.csv`
  (source, dest_relpath, original_name, reason, variants_ignored, note).
- Tests: `tests/test_wp_collect.py` (11 tests, fake filenames). Suite now 34 green.
- Docs: SETUP command row, CODEMAP entries, D-010 / D-011 / D-012. `.gitignore` entry for the
  collected folder and its manifest (already covered by `input/`, now explicit).

## 2026-09-03 - phase01
- Environment: `.venv` + `requirements.txt` (opencv-python, numpy, rapidfuzz, tqdm, pytest); exact versions in SETUP.
- Package `logoscanner/`: `__init__`, `__main__`, `cli` (subcommands `scan`, `version`), `config` (tunables + band mapping), `io_utils` (safe walk + load), `results` (ResultRow, CSV/JSON writers).
- `scan` v0: walks a folder, loads every image, writes `results.csv` + `summary.json`, prints throughput and ETA for 10,000 images. No detection yet - every image is scored 0.0 / negative.
- Tools: `make_dummy_logo.py` (committable fake mark), `make_synthetic.py` (synthetic labeled set), `check_dataset.py` (dataset stats).
- Tests: 23 tests over walker, loader, schema round-trip, synthetic generator, and end-to-end scan.
- Docs: SETUP filled in for real, CODEMAP populated, ARCHITECTURE current state updated, D-007/D-008 added.
- Measured baseline (no detection): 42 img/s on 800x600 PNGs -> ~4 min for 10k. All later budget is detection cost.

## 2026-09-03 - phase00
- Bootstrap: directory structure, CLAUDE.md, docs system, plan system with 8 phase files.
