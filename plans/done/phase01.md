# phase01 — Foundation, CLI Skeleton & Dataset Protocol

**Goal:** working repo: environment, package skeleton, `scan` command that walks images and measures throughput (no detection yet), synthetic test-data generator, and the labeling protocol for the real dataset.
**Depends on:** phase00 (bootstrap)
**Conditional?** no

## Context to load
- `docs/SETUP.md`, `docs/CODEMAP.md`

## User prerequisites
- None. (Real logo files in `logo/` help but are not required yet.)

## Steps
1. Create `.venv`; write `requirements.txt`: `opencv-python`, `numpy`, `rapidfuzz`, `tqdm`, `pytest`. Install. Record exact versions in `docs/SETUP.md`.
2. Create the package:
   - `logoscanner/__init__.py` — version string.
   - `logoscanner/__main__.py` — delegates to `cli.main()`.
   - `logoscanner/cli.py` — `argparse` with subcommands `scan`, `version` (later phases add `benchmark`, `calibrate`). `scan --input <dir> --output <dir> [--limit N]`.
   - `logoscanner/config.py` — single source of tunables: `BRAND_TERMS = ["ACME", "ACME Systems"]  # TODO(user): set real terms`, `IMAGE_EXTS`, `MAX_SIDE = 1600`, placeholder thresholds (filled in later phases), band names `positive/review/negative`.
   - `logoscanner/io_utils.py` — `iter_images(root)` recursive walker filtered by `IMAGE_EXTS`; `load_image(path)` returning BGR array or a recorded error; never raises on a bad file.
   - `logoscanner/results.py` — `ResultRow` dataclass (`filename, contains_logo, band, confidence, x, y, w, h, method, error`); CSV writer (stdlib `csv`); JSON summary writer (totals per band, timing).
3. `scan` v0: walk → load → (no signals yet: every image `band=negative, confidence=0.0`) → write CSV+JSON → print throughput report: `images, seconds, imgs/s, ETA for 10,000`.
4. `tools/make_dummy_logo.py` — generates `tests/assets/dummy_logo.png`: fake mark = colored geometric symbol + the text `ACME` (safe for the public repo). Commit the PNG.
5. `tools/make_synthetic.py` — `--out <dir> --count N --positive-ratio 0.5`: composes images (solid/gradient/noise/random-shapes/random-text backgrounds); positives get the dummy logo pasted at random scale (0.3–1.5×), position, slight rotation (±10°), optional 60–100% opacity; writes into `<out>/positive/` and `<out>/negative/`. Used by tests and pre-real-data benchmarks.
6. `tools/check_dataset.py` — prints counts and size stats for `data/labeled/positive|negative`.
7. Tests (`tests/`): walker skips non-images and junk files; corrupt file yields recorded error, not a crash; CSV/JSON schema round-trip; synthetic generator produces the requested split. Use `tmp_path` + `tests/assets/` only.
8. Docs: fill `docs/SETUP.md` for real; add every new file to `docs/CODEMAP.md`; CHANGELOG entry; update ARCHITECTURE "Current state".

## Deliverables
- `requirements.txt`, `logoscanner/{__init__,__main__,cli,config,io_utils,results}.py`, `tools/{make_dummy_logo,make_synthetic,check_dataset}.py`, `tests/*`, `tests/assets/dummy_logo.png`, updated docs.

## Acceptance criteria
- [ ] `pytest` green.
- [ ] `scan` over 50 synthetic images produces valid CSV+JSON and prints the throughput report with ETA for 10k.
- [ ] Corrupt file in input does not crash the run and appears in the CSV `error` column.
- [ ] CODEMAP has one accurate entry per new file.

## Verify
```powershell
python tools\make_dummy_logo.py
python tools\make_synthetic.py --out .tmp_synth --count 50
python -m logoscanner scan --input .tmp_synth --output .tmp_out
pytest -q
```

## Out of scope
- Any detection logic; OCR; SIFT; performance tuning.

## User homework after this phase
- Set real `BRAND_TERMS` in `logoscanner/config.py`.
- Put real logo variants into `logo/` (light/dark/symbol-only, transparent PNG when possible).
- Label ~300 real images by dragging them into `data/labeled/positive/` and `data/labeled/negative/` (~100–150 positives). **Include the hard cases:** tiny logo, partial logo, logo over photos/charts/screenshots, dark & light variants, low resolution.

## Progress Log
- 2026-09-03 - `.venv` created, 5 deps installed, versions pinned in `docs/SETUP.md`.
- 2026-09-03 - package skeleton done: `config`, `io_utils`, `results`, `cli`, `__main__`.
- 2026-09-03 - `scan` v0 walks + loads + writes CSV/JSON + prints throughput & 10k ETA.
- 2026-09-03 - `tools/make_dummy_logo.py` written and run; `tests/assets/dummy_logo.png` committed.
- 2026-09-03 - `tools/make_synthetic.py` + `tools/check_dataset.py` written; verify run over 50 synthetic images.
- 2026-09-03 - 23 tests green; docs (SETUP, CODEMAP, CHANGELOG, ARCHITECTURE, DECISIONS D-007..D-009) updated.

## Completion Report

**Status:** done - 2026-09-03. All acceptance criteria met.

**What shipped**
- `requirements.txt` + `.venv` (Python 3.12.10): opencv-python 5.0.0.93, numpy 2.5.2, RapidFuzz 3.14.6, tqdm 4.70.0, pytest 9.1.1.
- `logoscanner/`: `__init__` (0.1.0), `__main__`, `cli` (`scan`, `version`), `config` (BRAND_TERMS placeholder, IMAGE_EXTS, MAX_SIDE, band names + placeholder thresholds, `band_for`), `io_utils` (`iter_images`, `load_image`, `downscale`), `results` (`ResultRow`, CSV writer/reader, `summarize`, `write_json`).
- `tools/`: `make_dummy_logo.py`, `make_synthetic.py`, `check_dataset.py`.
- `tests/`: 23 tests across `test_io_utils`, `test_results`, `test_synthetic`, `test_cli`, plus `conftest.py` and the committed `tests/assets/dummy_logo.png`.
- Docs: SETUP (real environment + command table), CODEMAP (one entry per new file), CHANGELOG, ARCHITECTURE current state, DECISIONS D-007/D-008/D-009.

**Verify output (50 synthetic images)**
```
Scanned    : 50 images from .tmp_synth
Bands      : positive=0  review=0  negative=50
Errors     : 0
Elapsed    : 1.19 s
Throughput : 41.93 img/s
ETA 10,000 : 3m 58s
```
`pytest -q` -> `23 passed`.

**Baseline for later phases:** ~42 img/s for walk + decode + resize on 800x600 PNGs, i.e. ~4 min for 10k images. Roughly the whole 12 h budget from D-005 remains available to the detection signals.

**Deviations / notes**
- `BRAND_TERMS` intentionally left as the `ACME` placeholder even though real logo files exist in `logo/` - the real terms are the user's homework and the plan specified the placeholder.
- `tools/check_dataset.py` bootstraps `sys.path` itself so it runs as a plain script from the repo root.
- Console output kept ASCII-only: the Windows console codepage mangles em dashes.
- `.gitignore` extended with `.tmp_*/` for the verify-command scratch folders.

**Follow-ups for the next phase**
- phase02 fills `run_scan` with the OCR signal and adds the `benchmark` subcommand; `ResultRow.method` / `confidence` / box columns are already in place for it.
- Synthetic positives currently vary scale, rotation, position and opacity only. Blur, JPEG artifacts and occlusion are worth adding when the baseline starts passing too easily.
