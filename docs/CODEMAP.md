# Code Map

> One entry per source file. **Update in the same session as any change.** Keep alphabetical within each section. This file exists so the AI never has to scan the repo.

**Entry format:**
`path` — Purpose. | Key functions/classes. | Depends on. | When to modify.

## logoscanner/ (package)
`logoscanner/__init__.py` — Package marker + version string. | `__version__`. | — | On release bumps.

`logoscanner/__main__.py` — Entry point for `python -m logoscanner`. | delegates to `cli.main()`. | `cli`. | Almost never.

`logoscanner/benchmark.py` — Per-signal quality on a labeled folder: sweep the (review, positive) threshold grid, print, append a BENCHMARKS row. Several signals also get a naive-OR row (D-019). Scoring is delegated to `metrics.score_images`. | `run_benchmark()`, `score_labeled()` (adapter over `metrics.score_images`), `evaluate()`, `sweep()`, `best_point()`, `combine()`, `format_report()`, `benchmark_row()`, `append_rows()`, `SignalScores`, `Point`, `GRID`, `PHASE`. | `config`, `metrics`, `signals`. | Adding a metric or changing the grid. The thresholds the scanner ships with come from `calibrate`, not from here.

`logoscanner/calibrate.py` — Grid-searches the per-signal `(weak, strong)` thresholds on the labeled set, writes `output/calibration.json`, rewrites the marked block in `config.py`, and renders the phase04 gate verdict (D-021, D-022). | `run_calibration()`, `search()` (vectorised band matrices), `pair_grid()`, `Candidate`, `SearchResult`, `render_thresholds_block()`, `apply_to_config()`, `gate_verdict()`, `miss_reason()`, `write_gate_failures()`, `BLOCK_START`/`BLOCK_END`. | `config`, `metrics`, numpy. | Changing the objective, the grid, the gate targets, or the shape of the config block it writes.

`logoscanner/cli.py` — Argparse CLI: the scan driver plus the benchmark and calibrate entries. | `main(argv)`, `build_parser()`, `run_scan(input_dir, output_dir, limit, progress, signals)`, `print_report()`, `_parse_signals()`, `_format_duration()`. Subcommands: `scan`, `benchmark`, `calibrate`, `version`. | `config`, `signals`, `pipeline`, `benchmark`, `calibrate`, `io_utils`, `results`, `tqdm`. | Adding a subcommand or a scan-level flag.

`logoscanner/config.py` — Single source of tunables. | `BRAND_TERMS`, `IMAGE_EXTS`, `MAX_SIDE`, `ENABLED_SIGNALS`, `OCR_MIN_FUZZ`/`OCR_MIN_TEXT_LEN`, `LOGO_DIR` + the `SIFT_*` knobs (min side, Lowe ratio, min good/inliers, RANSAC reprojection, score norm, box-plausibility limits), band names, the confidence-scale anchors `POSITIVE_THRESHOLD`/`REVIEW_THRESHOLD` + `band_for(confidence)`, the calibrated `SIGNAL_THRESHOLDS` block (between the markers `calibrate` rewrites) + `FALLBACK_THRESHOLDS`, gate targets `TARGET_CATCH_RECALL`/`TARGET_REVIEW_SHARE`, `CALIBRATION_GRID`. | stdlib only. | Any tunable change; `calibrate` rewrites the thresholds block in place, so keep its markers intact.

`logoscanner/decision.py` — Decision engine: per-signal `(weak, strong)` thresholds -> band, normalized confidence, winning signal(s), box (D-021). | `Decision` (`contains_logo`, `to_row`), `decide(results, thresholds=None)`, `decide_scores(scores, thresholds=None)`, `band_of()`, `normalize()`, `thresholds_for()`, `Thresholds`. | `config`, `results`, `signals`. | Changing how signals combine, how confidence is scaled, or what a decision carries into the CSV.

`logoscanner/keypoints.py` — SIFT signal: match the logo symbol by keypoints at any scale/rotation, verified by a homography. | `SiftSignal` (registered as `"sift"`), `Template`, `build_templates()`/`get_templates()`/`clear_cache()`, `load_variant()`, `to_gray()` (alpha-aware), `good_matches()` (Lowe ratio, one match per image location), `plausible_box()`, `make_detector()`. Score = `min(1, inliers / SIFT_SCORE_NORM)`; see D-017. | `config`, `signals`, cv2, numpy. | Tuning the match/verification rules, or when `logo/` gains variants.

`logoscanner/metrics.py` — Labeled-set scoring and decision quality. Scoring and judging are separate so calibration pays for the signals once. | `score_images(labeled_dir, signal_names, limit, progress)` -> `(list[ScoredImage], meta)`, `evaluate(records, thresholds)` -> `Metrics` (precision, catch-recall, review share, confusion counts, per-signal wins, false negative/positive filenames), `format_metrics()`, `ScoredImage`, `CLASS_DIRS`. | `config`, `decision`, `io_utils`, `signals`, `tqdm`. | Adding a metric, or changing the labeled-set layout.

`logoscanner/ocr.py` — OCR signal: read text with RapidOCR, fuzzy-match it to `BRAND_TERMS`. | `OcrSignal` (registered as `"ocr"`), `get_engine()` (one lazy engine per process), `read_text(image)`, `match_text(text, terms)`, `normalize()`, `compact()`, `_pair_ratio()`. Score = `fuzz/100 x ocr_confidence`; see D-013. | `config`, `signals`, rapidfuzz, rapidocr-onnxruntime, numpy. | Tuning the match rules, adding brand-term spellings, swapping the OCR engine.

`logoscanner/pipeline.py` — Holds the instantiated signals so their engines load once per process, and hands their results to `decision.decide`. | `Pipeline` (`run`, `names`), `build_pipeline(names)`; re-exports `decide`/`Decision`. | `config`, `decision`, `signals`. | Adding per-image orchestration (batching, early exit). Banding rules live in `decision.py`.

`logoscanner/signals.py` — Signal contract + name registry the pipeline and CLI select from. | `SignalResult` (name/score/bbox/detail, score clamped to [0,1]), `Signal` protocol, `register(name)`, `build(name)`, `build_all(names_or_instances)`, `available()`. | numpy. | Adding a signal (register it, import it in `_load_builtins`, then list it in `config.ENABLED_SIGNALS`).

`logoscanner/io_utils.py` — Filesystem walk and crash-proof image loading. | `iter_images(root)` (recursive, sorted, extension-filtered, skips junk/dot-files), `load_image(path, max_side)` -> `(bgr_array, None)` or `(None, "reason")`, `downscale(image, max_side)`. | `config`, cv2, numpy. | Changing accepted formats, resize policy, or error reporting.

`logoscanner/results.py` — Result schema and report writers (stdlib csv/json). | `ResultRow` dataclass, `CSV_COLUMNS`, `write_csv`/`read_csv`, `summarize(rows, seconds)`, `write_json`, `CSV_NAME`/`JSON_NAME`. | `config`. | Adding a CSV column (update `CSV_COLUMNS` + dataclass together; an assert guards drift) or a summary field.

## tools/
`tools/check_dataset.py` — Prints counts and file-size stats for `data/labeled/positive|negative`. | `main(argv)`, `_stats()`. | `logoscanner.io_utils`. | Changing the dataset layout or the stats reported.

`tools/make_dummy_logo.py` — Generates the committable fake mark `tests/assets/dummy_logo.png` (720x240 RGBA: hexagon with interior detail + "ACME" + tagline). The interior detail exists so the SIFT signal is testable at production thresholds (D-018). | `make_logo()`, `main(argv)`. | cv2, numpy. | If tests need a different fake logo. Never put the real logo here.

`tools/wp_collect.py` — Collects the original images out of a WordPress `uploads/` tree (ignores the generated `-WxH` thumbnails, `.bak` optimizer backups and webp/avif conversions) into one flat folder for scanning. | `main(argv)`, `scan(source, first, last)`, `classify(path)`, `Candidate.rank()`, `fit_name()`, `long_path()`, `sha1()`. Writes `<dest>/<YYYY-MM>/<original filename>`, never renaming. | stdlib only. | Changing the variant-detection rules, the destination layout, or the year range.

`tools/make_synthetic.py` — Generates a synthetic labeled dataset for tests and pre-real-data benchmarks. | `generate(out_dir, count, positive_ratio, logo_path, size, seed, text_ratio)`, `make_background()`, `paste_logo()`, `draw_brand_text()` (brand name on a contrasting plaque, `--with-text`), `_rotate_rgba()`, background kinds solid/gradient/noise/shapes/text. | `logoscanner.config`, cv2, numpy. | Adding harder augmentations (blur, JPEG artifacts, occlusion) for later phases.

## tests/
`tests/conftest.py` — Puts repo root and `tools/` on `sys.path`; `dummy_logo_path` and `fake_logo_dir` session fixtures, plus the autouse `isolate_logo_dir` that points `config.LOGO_DIR` at an empty folder so no test reads the real `logo/` (D-020). | — | pytest. | New shared fixtures.

`tests/test_benchmark.py` — Sweep metrics (precision / catch-recall / review share / misses), grid shape, recall-first ranking, BENCHMARKS row format, append-only writing, `score_labeled` over both classes with a stub signal, and the naive-OR `combine` + combined row.

`tests/test_calibrate.py` — Threshold search on hand-built score sets: pair grid shape, a feasible separable set, precision maximised under the constraints, the relaxation when the recall target is unreachable, empty input, the gate verdict, `config.py` block round-trip (rendered block re-executes to the same dict) + refusal without markers, miss-reason categories, the gate-failures file, and `run_calibration` end to end (JSON, config copy, gate file, `--no-apply`). | — | `logoscanner.benchmark`, `make_synthetic`. | When a metric or the row format changes.

`tests/test_cli.py` — End-to-end `scan` (CSV+JSON written, corrupt file recorded not crashed, `--limit`, report printed, missing input exits 2; walk-only tests pin `signals=()`), the real OCR path on `--with-text` positives, the SIFT path on pasted marks (`fake_logo_dir`), unknown-signal rejection, the `benchmark` subcommand (single signal and the `ocr,sift` combined report), and `calibrate` (JSON payload written, gate line printed, `--no-apply` leaves `config.py` byte-identical, missing folder exits 2). | — | `logoscanner.cli`, `make_synthetic`. | When `scan` or `benchmark` behaviour changes.

`tests/test_io_utils.py` — Walker (recursion, extension filter, junk/dot-file skip, missing root) and loader (ok / corrupt / empty / missing / downscale). | — | `logoscanner.io_utils`. | When walking or loading rules change.

`tests/test_keypoints.py` — SIFT detection of the fake mark at 0.4x/1.0x/1.5x and ±10°, bbox sanity in original coordinates (including an image larger than `MAX_SIDE`), zero on pure backgrounds, `plausible_box` rejections (collapsed/bow-tie/sliver/off-canvas/NaN), template building (empty folder, featureless variant dropped, tiny variant upscaled), alpha-aware `to_gray`, one-match-per-location, template caching, missing-`logo/` warning. | — | `logoscanner.keypoints`, `make_synthetic`, cv2. | When the matching or verification rules change.

`tests/test_ocr.py` — Brand-term matching (case, spacing, punctuation, glued, typo tolerance, fragment rejection, short-string guards, `OCR_MIN_FUZZ` boundary) plus an engine smoke test on rendered text and the failure-to-zero path. | — | `logoscanner.ocr`, cv2. | When the match rules or the engine change.

`tests/test_decision.py` — Per-signal truth table, the OR rule across signals on different scales, winner ordering and the `a+b` method string, fallback thresholds, the normalized confidence scale (anchors, monotonicity, degenerate spans, band/confidence agreement), box and `to_row` handling. | — | `logoscanner.decision`. | When the banding rules or the confidence scale change.

`tests/test_metrics.py` — A 10-image mini-set whose bands are hand-checked: precision / catch-recall / review share, confusion counts, per-signal wins, threshold sensitivity, empty input, `score_images` over both classes (filenames, per-signal seconds, unreadable files, `--limit`), `as_dict`, `format_metrics`. | — | `logoscanner.metrics`, `make_synthetic`. | When a metric or the scoring record changes.

`tests/test_pipeline.py` — Orchestration only: every signal runs, the decision comes back banded, an all-silent run is negative, default signal list, `decide` re-export. | — | `logoscanner.pipeline`. | When the pipeline gains orchestration behaviour; banding tests live in `test_decision.py`.

`tests/test_results.py` — CSV header, CSV round-trip, summary band/error/timing math, zero-elapsed case. | — | `logoscanner.results`. | When the schema or summary changes.

`tests/test_signals.py` — `SignalResult` clamping/bbox coercion, registry lookup, duplicate-name rejection, `build_all` passing instances through. | — | `logoscanner.signals`. | When the signal contract changes.

`tests/test_synthetic.py` — Generator split, loadability/size, all-negative needs no logo, missing-logo error, paste actually modifies the background, `--with-text` share and readability. | — | `make_synthetic`. | When the generator changes.

`tests/test_wp_collect.py` — Variant-selection rules: original beats thumbnails, `-scaled` fallback, largest-variant fallback, only the trailing `-WxH` is stripped, format preference, `.bak`/non-image skipping, per-month grouping, year range, `<YYYY-MM>/<original name>` layout, opt-in dedupe, `fit_name`. | — | `wp_collect`. | When the WordPress naming rules change.

`tests/assets/dummy_logo.png` — Committed fake logo (720x240 RGBA) produced by `tools/make_dummy_logo.py`. Public-safe.
