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
*(AI appends dated one-liners as milestones complete)*

## Completion Report
*(filled at the end)*
