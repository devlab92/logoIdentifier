# Code Map

> One entry per source file. **Update in the same session as any change.** Keep alphabetical within each section. This file exists so the AI never has to scan the repo.

**Entry format:**
`path` — Purpose. | Key functions/classes. | Depends on. | When to modify.

## logoscanner/ (package)
`logoscanner/__init__.py` — Package marker + version string. | `__version__`. | — | On release bumps.

`logoscanner/__main__.py` — Entry point for `python -m logoscanner`. | delegates to `cli.main()`. | `cli`. | Almost never.

`logoscanner/cli.py` — Argparse CLI and the scan driver. | `main(argv)`, `build_parser()`, `run_scan(input_dir, output_dir, limit, progress)`, `print_report()`, `_format_duration()`. Subcommands: `scan`, `version`. | `config`, `io_utils`, `results`, `tqdm`. | Adding a subcommand (`benchmark` phase02, `calibrate` phase04) or wiring detection signals into `run_scan`.

`logoscanner/config.py` — Single source of tunables. | `BRAND_TERMS` (TODO: user sets real terms), `IMAGE_EXTS`, `MAX_SIDE`, band names + `POSITIVE_THRESHOLD`/`REVIEW_THRESHOLD` placeholders, `band_for(confidence)`. | stdlib only. | Any threshold/tunable change; phase04 calibration writes here.

`logoscanner/io_utils.py` — Filesystem walk and crash-proof image loading. | `iter_images(root)` (recursive, sorted, extension-filtered, skips junk/dot-files), `load_image(path, max_side)` -> `(bgr_array, None)` or `(None, "reason")`, `downscale(image, max_side)`. | `config`, cv2, numpy. | Changing accepted formats, resize policy, or error reporting.

`logoscanner/results.py` — Result schema and report writers (stdlib csv/json). | `ResultRow` dataclass, `CSV_COLUMNS`, `write_csv`/`read_csv`, `summarize(rows, seconds)`, `write_json`, `CSV_NAME`/`JSON_NAME`. | `config`. | Adding a CSV column (update `CSV_COLUMNS` + dataclass together; an assert guards drift) or a summary field.

## tools/
`tools/check_dataset.py` — Prints counts and file-size stats for `data/labeled/positive|negative`. | `main(argv)`, `_stats()`. | `logoscanner.io_utils`. | Changing the dataset layout or the stats reported.

`tools/make_dummy_logo.py` — Generates the committable fake mark `tests/assets/dummy_logo.png` (hexagon + "ACME", RGBA). | `make_logo()`, `main(argv)`. | cv2, numpy. | If tests need a different fake logo. Never put the real logo here.

`tools/make_synthetic.py` — Generates a synthetic labeled dataset for tests and pre-real-data benchmarks. | `generate(out_dir, count, positive_ratio, logo_path, size, seed)`, `make_background()`, `paste_logo()`, `_rotate_rgba()`, background kinds solid/gradient/noise/shapes/text. | cv2, numpy. | Adding harder augmentations (blur, JPEG artifacts, occlusion) for later phases.

## tests/
`tests/conftest.py` — Puts repo root and `tools/` on `sys.path`; `dummy_logo_path` session fixture (regenerates the asset if missing). | — | pytest. | New shared fixtures.

`tests/test_cli.py` — End-to-end `scan`: CSV+JSON written, corrupt file recorded not crashed, `--limit`, report printed, missing input exits 2. | — | `logoscanner.cli`, `make_synthetic`. | When `scan` behaviour changes.

`tests/test_io_utils.py` — Walker (recursion, extension filter, junk/dot-file skip, missing root) and loader (ok / corrupt / empty / missing / downscale). | — | `logoscanner.io_utils`. | When walking or loading rules change.

`tests/test_results.py` — CSV header, CSV round-trip, summary band/error/timing math, zero-elapsed case. | — | `logoscanner.results`. | When the schema or summary changes.

`tests/test_synthetic.py` — Generator split, loadability/size, all-negative needs no logo, missing-logo error, paste actually modifies the background. | — | `make_synthetic`. | When the generator changes.

`tests/assets/dummy_logo.png` — Committed fake logo (360x120 RGBA) produced by `tools/make_dummy_logo.py`. Public-safe.
