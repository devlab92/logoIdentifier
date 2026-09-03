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
- [ ] `pytest` green (OCR smoke included).
- [ ] `benchmark --signals ocr` runs on `data/labeled` (or synthetic fallback, flagged) and the row is in BENCHMARKS.
- [ ] `scan` output now contains real OCR scores/bboxes.

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

## Completion Report
