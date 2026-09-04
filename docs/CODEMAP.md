# Code Map

> One entry per source file. **Update in the same session as any change.** Keep alphabetical within each section. This file exists so the AI never has to scan the repo.

**Entry format:**
`path` — Purpose. | Key functions/classes. | Depends on. | When to modify.

## logoscanner/ (package)
`logoscanner/__init__.py` — Package marker + version string. | `__version__`. | — | On release bumps.

`logoscanner/__main__.py` — Entry point for `python -m logoscanner`. | delegates to `cli.main()`. | `cli`. | Almost never.

`logoscanner/benchmark.py` — Per-signal quality on a labeled folder: score, sweep thresholds, print, append a BENCHMARKS row. | `run_benchmark()`, `score_labeled()`, `evaluate()`, `sweep()`, `best_point()`, `format_report()`, `benchmark_row()`, `append_rows()`, `SignalScores`, `Point`, `GRID`. | `config`, `io_utils`, `signals`, `tqdm`. | Adding a metric, changing the grid, or when phase04 turns the reported operating point into real calibration.

`logoscanner/cli.py` — Argparse CLI, the scan driver and the benchmark entry. | `main(argv)`, `build_parser()`, `run_scan(input_dir, output_dir, limit, progress, signals)`, `print_report()`, `_parse_signals()`, `_format_duration()`. Subcommands: `scan`, `benchmark`, `version`. | `config`, `signals`, `pipeline`, `benchmark`, `io_utils`, `results`, `tqdm`. | Adding a subcommand (`calibrate` phase04) or a scan-level flag.

`logoscanner/config.py` — Single source of tunables. | `BRAND_TERMS`, `IMAGE_EXTS`, `MAX_SIDE`, `ENABLED_SIGNALS`, `OCR_MIN_FUZZ`/`OCR_MIN_TEXT_LEN`, band names + provisional `POSITIVE_THRESHOLD`/`REVIEW_THRESHOLD`, `band_for(confidence)`. | stdlib only. | Any threshold/tunable change; phase04 calibration writes here.

`logoscanner/ocr.py` — OCR signal: read text with RapidOCR, fuzzy-match it to `BRAND_TERMS`. | `OcrSignal` (registered as `"ocr"`), `get_engine()` (one lazy engine per process), `read_text(image)`, `match_text(text, terms)`, `normalize()`, `compact()`, `_pair_ratio()`. Score = `fuzz/100 x ocr_confidence`; see D-013. | `config`, `signals`, rapidfuzz, rapidocr-onnxruntime, numpy. | Tuning the match rules, adding brand-term spellings, swapping the OCR engine.

`logoscanner/pipeline.py` — Runs the enabled signals over one image and applies the OR decision rule. | `Pipeline` (`run`, `names`), `build_pipeline(names)`, `decide(results)`, `Decision` (`contains_logo`, `to_row(filename)`). | `config`, `results`, `signals`. | Changing how signals combine, or what a decision carries into the CSV.

`logoscanner/signals.py` — Signal contract + name registry the pipeline and CLI select from. | `SignalResult` (name/score/bbox/detail, score clamped to [0,1]), `Signal` protocol, `register(name)`, `build(name)`, `build_all(names_or_instances)`, `available()`. | numpy. | Adding a signal (register it, then list it in `config.ENABLED_SIGNALS`).

`logoscanner/io_utils.py` — Filesystem walk and crash-proof image loading. | `iter_images(root)` (recursive, sorted, extension-filtered, skips junk/dot-files), `load_image(path, max_side)` -> `(bgr_array, None)` or `(None, "reason")`, `downscale(image, max_side)`. | `config`, cv2, numpy. | Changing accepted formats, resize policy, or error reporting.

`logoscanner/results.py` — Result schema and report writers (stdlib csv/json). | `ResultRow` dataclass, `CSV_COLUMNS`, `write_csv`/`read_csv`, `summarize(rows, seconds)`, `write_json`, `CSV_NAME`/`JSON_NAME`. | `config`. | Adding a CSV column (update `CSV_COLUMNS` + dataclass together; an assert guards drift) or a summary field.

## tools/
`tools/check_dataset.py` — Prints counts and file-size stats for `data/labeled/positive|negative`. | `main(argv)`, `_stats()`. | `logoscanner.io_utils`. | Changing the dataset layout or the stats reported.

`tools/make_dummy_logo.py` — Generates the committable fake mark `tests/assets/dummy_logo.png` (hexagon + "ACME", RGBA). | `make_logo()`, `main(argv)`. | cv2, numpy. | If tests need a different fake logo. Never put the real logo here.

`tools/wp_collect.py` — Collects the original images out of a WordPress `uploads/` tree (ignores the generated `-WxH` thumbnails, `.bak` optimizer backups and webp/avif conversions) into one flat folder for scanning. | `main(argv)`, `scan(source, first, last)`, `classify(path)`, `Candidate.rank()`, `fit_name()`, `long_path()`, `sha1()`. Writes `<dest>/<YYYY-MM>/<original filename>`, never renaming. | stdlib only. | Changing the variant-detection rules, the destination layout, or the year range.

`tools/make_synthetic.py` — Generates a synthetic labeled dataset for tests and pre-real-data benchmarks. | `generate(out_dir, count, positive_ratio, logo_path, size, seed, text_ratio)`, `make_background()`, `paste_logo()`, `draw_brand_text()` (brand name on a contrasting plaque, `--with-text`), `_rotate_rgba()`, background kinds solid/gradient/noise/shapes/text. | `logoscanner.config`, cv2, numpy. | Adding harder augmentations (blur, JPEG artifacts, occlusion) for later phases.

## tests/
`tests/conftest.py` — Puts repo root and `tools/` on `sys.path`; `dummy_logo_path` session fixture (regenerates the asset if missing). | — | pytest. | New shared fixtures.

`tests/test_benchmark.py` — Sweep metrics (precision / catch-recall / review share / misses), grid shape, recall-first ranking, BENCHMARKS row format, append-only writing, `score_labeled` over both classes with a stub signal. | — | `logoscanner.benchmark`, `make_synthetic`. | When a metric or the row format changes.

`tests/test_cli.py` — End-to-end `scan` (CSV+JSON written, corrupt file recorded not crashed, `--limit`, report printed, missing input exits 2; walk-only tests pin `signals=()`), the real OCR path on `--with-text` positives, unknown-signal rejection, and the `benchmark` subcommand. | — | `logoscanner.cli`, `make_synthetic`. | When `scan` or `benchmark` behaviour changes.

`tests/test_io_utils.py` — Walker (recursion, extension filter, junk/dot-file skip, missing root) and loader (ok / corrupt / empty / missing / downscale). | — | `logoscanner.io_utils`. | When walking or loading rules change.

`tests/test_ocr.py` — Brand-term matching (case, spacing, punctuation, glued, typo tolerance, fragment rejection, short-string guards, `OCR_MIN_FUZZ` boundary) plus an engine smoke test on rendered text and the failure-to-zero path. | — | `logoscanner.ocr`, cv2. | When the match rules or the engine change.

`tests/test_pipeline.py` — OR decision rule (strongest signal wins, silent signals do not dilute), band mapping, `contains_logo` semantics, `to_row` box handling, pipeline construction. | — | `logoscanner.pipeline`. | When the decision layer changes.

`tests/test_results.py` — CSV header, CSV round-trip, summary band/error/timing math, zero-elapsed case. | — | `logoscanner.results`. | When the schema or summary changes.

`tests/test_signals.py` — `SignalResult` clamping/bbox coercion, registry lookup, duplicate-name rejection, `build_all` passing instances through. | — | `logoscanner.signals`. | When the signal contract changes.

`tests/test_synthetic.py` — Generator split, loadability/size, all-negative needs no logo, missing-logo error, paste actually modifies the background, `--with-text` share and readability. | — | `make_synthetic`. | When the generator changes.

`tests/test_wp_collect.py` — Variant-selection rules: original beats thumbnails, `-scaled` fallback, largest-variant fallback, only the trailing `-WxH` is stripped, format preference, `.bak`/non-image skipping, per-month grouping, year range, `<YYYY-MM>/<original name>` layout, opt-in dedupe, `fit_name`. | — | `wp_collect`. | When the WordPress naming rules change.

`tests/assets/dummy_logo.png` — Committed fake logo (360x120 RGBA) produced by `tools/make_dummy_logo.py`. Public-safe.
