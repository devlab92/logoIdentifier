# Changelog

> Newest first. One dated block per working session that changed the repo.

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
