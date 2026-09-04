# Architecture

> Keep this file matching reality. Update on any behavioral change.

## Current state
**phase02 done: the OCR signal is live.** `python -m logoscanner scan` walks a folder
(`io_utils.iter_images`), loads each image safely (`io_utils.load_image`, downscaled to
`config.MAX_SIDE`, decode failures recorded not raised, AVIF via a Pillow fallback), runs
every signal in `config.ENABLED_SIGNALS` through `pipeline.Pipeline`, and writes one
`results.ResultRow` per image into `results.csv` + `summary.json`.

Only the OCR signal exists so far: `ocr.OcrSignal` reads text with RapidOCR and fuzzy-matches
each line against `config.BRAND_TERMS` (D-013), scoring `fuzz/100 x ocr_confidence` and
returning the winning line's box. `pipeline.decide` applies the OR rule over signals and bands
the winner with `config.band_for`; those thresholds are provisional (0.85 / 0.60) until phase04
calibrates them. SIFT lands in phase03.

`python -m logoscanner benchmark --labeled <dir> --signals ocr` scores `positive/` + `negative/`,
sweeps a coarse (review, positive) threshold grid and prints precision / catch-recall / review
share per signal, appending a row to `docs/BENCHMARKS.md`. Operating points are picked
recall-first (D-014) and reported only - nothing writes back into `config` yet.

Measured: phase01 baseline was ~42 img/s for walk + decode + resize alone. OCR dominates now
(see BENCHMARKS for the current figure), so the 10k ETA is set by the OCR cost per image.

Target design below.

## Target pipeline
```text
image ──► OCR signal   (RapidOCR + fuzzy brand-term match)      ─┐
      ──► SIFT signal  (keypoints + Lowe ratio + RANSAC verify) ─┤► rule-based decision ──► positive / review / negative
      ──► [conditional] region proposals + embedding similarity ─┤        │
      ──► [conditional] fine-tuned nano detector                ─┘        ▼
                                                              results.csv/json, crops/, detected/, review/
```

## Key principles
- Decision engine uses **OR rules**, not weighted averages: one strong signal ⇒ positive; a lone medium signal ⇒ review. Protects recall.
- Thresholds come from **calibration on the labeled set**, never intuition. Bands: positive / review / negative.
- Signals are independent modules returning `SignalResult(score, bbox, method, detail)` so the decision layer stays pluggable.
- CPU-first. Performance work only if measured ETA for 10k images exceeds ~12 h (then: multiprocessing before any GPU runtime).

## Data flow & artifacts
`input/` → scanner walk → per-image signals → decision → incremental `output/results.csv` + `output/.progress.jsonl` (resume) → final `results.json` summary + `crops/`, `detected/`, `review/`.
Incremental writing, resume and the crop/detected/review folders are still ahead; phase02 writes
the CSV and JSON once at the end of the run.
