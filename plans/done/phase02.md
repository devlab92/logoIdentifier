# phase02 — OCR Signal (brand text)

**Goal:** OCR-based signal that finds the brand name in images, plus a `benchmark` command measuring per-signal quality on a labeled set.
**Depends on:** phase01
**Conditional?** no

## Context to load
- `docs/CODEMAP.md`, `docs/ARCHITECTURE.md`, `logoscanner/config.py`, `logoscanner/results.py`, `logoscanner/cli.py`

## User prerequisites
- `BRAND_TERMS` set. Labeled real data helps; if absent, run benchmarks on synthetic and flag homework pending.

## Steps
1. Add `rapidocr-onnxruntime` (+ `onnxruntime`) to requirements; verify it runs fully offline after install (models ship with the package). DECISIONS already covers the choice (D-002).
2. `logoscanner/signals.py` — shared `SignalResult` dataclass (`name, score∈[0,1], bbox|None, detail`) and a signal registry the pipeline iterates (enabled list in `config.py`).
3. `logoscanner/ocr.py` — `OcrSignal`: lazy engine init (load once per process); run OCR; normalize text (casefold, collapse whitespace, strip punctuation); match each detected text against every `BRAND_TERMS` entry with `rapidfuzz.fuzz.partial_ratio`; guard against trivially short matches; `score = (fuzz/100) × ocr_confidence`; return best box.
4. `logoscanner/pipeline.py` — orchestrates enabled signals per image; `scan` now records the best signal (`method`, `confidence`, bbox) even though banding is provisional until phase04 (temporary rule: score ≥ 0.85 → positive, ≥ 0.60 → review).
5. Extend `tools/make_synthetic.py`: `--with-text` renders the first brand term into some positives (varied fonts/sizes) so OCR is testable synthetically.
6. `benchmark` subcommand: `--labeled <dir> --signals ocr[,sift,...]` → runs signals over `positive/`+`negative/`, sweeps a coarse threshold grid, prints best precision/catch-recall/review-share per signal, appends a row to `docs/BENCHMARKS.md`.
7. Tests: matcher variants (case, spacing, OCR-typo like `AC1VIE`→ACME tolerance boundaries); OCR smoke test on a synthetic text image; registry returns well-formed `SignalResult`s.
8. Docs: CODEMAP (new files + pipeline), ARCHITECTURE (pipeline now real), CHANGELOG, BENCHMARKS row.

## Acceptance criteria
- [x] `pytest` green (OCR smoke included). 97 passed.
- [x] `benchmark --signals ocr` runs on the real `data/labeled` (100/158) and the row is in BENCHMARKS.
- [x] `scan` output now contains real OCR scores/bboxes.

## Verify
```powershell
python -m logoscanner benchmark --labeled data\labeled --signals ocr
pytest -q
```

## Out of scope
- SIFT; final thresholds; calibration.

## User homework after this phase
- Finish labeling if not done — phase04 hard-requires it.

## Progress Log
- **2026-09-04** - `rapidocr-onnxruntime==1.4.4` installed; ONNX models ship inside the wheel
  (`site-packages/rapidocr_onnxruntime/models/`, ~16 MB), so the runtime stays offline. Engine
  init ~2.3 s once per process. D-015 records the dependency.
- **2026-09-04** - `signals.py` (SignalResult + name registry), `ocr.py` (OcrSignal, lazy engine,
  normalise + fuzzy match, D-013) and `pipeline.py` (OR decision, provisional bands 0.85/0.60)
  landed; `scan` now writes real scores, methods and boxes.
- **2026-09-04** - `benchmark.py` + `benchmark` subcommand: scores both classes, sweeps a
  0.05-step (review, positive) grid, prints the per-threshold table and appends a BENCHMARKS
  row. Operating point chosen recall-first (D-014).
- **2026-09-04** - `make_synthetic.py --with-text` renders the first brand term on a contrasting
  plaque into a share of the positives (default 0.6), which is what makes the OCR path testable
  without company images.
- **2026-09-04** - Found while benchmarking: 11 of the 258 labeled files are AVIF, which the
  opencv-python wheels cannot decode and the walker was skipping *silently* (2 of them
  positives). Added a Pillow fallback in `io_utils.load_image` and `.avif` to `IMAGE_EXTS`
  (D-016) so the whole set is measured.

## Completion Report

**Finished 2026-09-04.** OCR is the first live signal and the project now has a measuring stick.

**Shipped**
- `signals.py` (contract + registry), `ocr.py` (`OcrSignal`), `pipeline.py` (OR decision),
  `benchmark.py` + the `benchmark` subcommand; `scan` wired to the pipeline.
- `--signals` on both `scan` and `benchmark`; unknown names are rejected with the available list.
- `tools/make_synthetic.py --with-text` for OCR-testable synthetic positives.
- Tests 34 -> 97 green. New files: `test_signals.py`, `test_ocr.py`, `test_pipeline.py`,
  `test_benchmark.py`.

**Numbers** (real labeled set, 100 positive / 158 negative, OCR only)

| metric | value |
|---|---|
| catch-recall (positive u review) | **0.930** (7 missed) |
| precision of the positive band | **0.875** |
| review share of all images | **8.5%** |
| best pair | `t_rev=0.60`, `t_pos=0.95` |
| throughput | 0.55 img/s -> ~5.1 h for 10k |

Recall is flat at 0.930 for every threshold from 0.05 to 0.75: the 7 missed positives score
exactly 0, i.e. OCR reads no brand-like text in them at all. No threshold tuning can recover
them - they need the shape signal from phase03. Conversely 11 negatives still score >= 0.95;
those are the images where OCR legitimately reads brand-like words.

**Deviations from the plan**
- Added a Pillow fallback decoder and `.avif` to `IMAGE_EXTS` (D-016). Not in the phase scope,
  but the benchmark was silently ignoring 11 of 258 labeled files (2 positives) because
  opencv-python cannot decode AVIF - a silent-miss bug that hard rule 5 exists to prevent.
- Provisional bands were set in `config` (0.85 / 0.60) rather than hard-coded in the pipeline,
  so `band_for` stays the single place phase04 has to touch.
- The benchmark reports the recall-first operating point but never writes it back into `config`;
  that is deliberately phase04's job.

**For phase03/04**
- The 7 OCR-blind positives are the acceptance target for SIFT.
- `t_pos=0.95` looking best is an artefact of OCR confidence clustering near 1.0; treat the
  whole (review, positive) surface, not just the argmax, when phase04 calibrates.
- 0.55 img/s is the number to watch if more signals are added (12 h budget, D-005).
