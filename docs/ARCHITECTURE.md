# Architecture

> Keep this file matching reality. Update on any behavioral change.

## Current state
**phase04 done: the decision engine is calibrated and the ML gate FAILED (D-023).**
`python -m logoscanner scan` walks a folder (`io_utils.iter_images`), loads each image safely
(`io_utils.load_image`, downscaled to `config.MAX_SIDE`, decode failures recorded not raised,
AVIF via a Pillow fallback), runs every signal in `config.ENABLED_SIGNALS` through
`pipeline.Pipeline`, bands the result with `decision.decide`, and writes one `results.ResultRow`
per image into `results.csv` + `summary.json`.

`ocr.OcrSignal` reads text with RapidOCR and fuzzy-matches each line against
`config.BRAND_TERMS` (D-013), scoring `fuzz/100 x ocr_confidence` and returning the winning
line's box. `keypoints.SiftSignal` covers the logos OCR cannot read: SIFT descriptors are
computed once per variant in `logo/`, matched with a Lowe ratio test kept one-per-image-location,
and verified by a RANSAC homography whose projected quad must be a believable logo placement
(D-017); score is `min(1, inliers / SIFT_SCORE_NORM)`. An empty or missing `logo/` warns once
and the signal scores 0, so a scan still runs on OCR alone.

`decision.decide` gives each signal its own `(weak, strong)` pair from
`config.SIGNAL_THRESHOLDS`, asks each which band it claims, and takes the best band claimed
(D-021). Calibrated 2026-09-04: OCR 0.60/0.95, SIFT 0.45/0.45 - SIFT has no review band, it
either flags or stays silent. `confidence` is the winner's score normalized onto the shared scale
(weak → 0.50, strong → 0.85) and `method` names every signal that claimed the band.

`python -m logoscanner calibrate --labeled <dir>` re-derives those four numbers and writes them
back into `config.py`; `python -m logoscanner benchmark --labeled <dir> --signals ocr,sift`
reports what each signal could do alone plus a naive-OR row (D-019), appending to
`docs/BENCHMARKS.md`.

Measured on the labeled set (100/158): precision **0.882**, catch-recall **0.940**, review share
**7.0%**. The gate FAILED on catch-recall (target 0.97): 6 positives score 0 on both signals and
no threshold can recover them, so **phase05 (embeddings) runs**; see `output/gate_failures.txt`.
phase01 baseline was ~42 img/s for walk + decode + resize alone; OCR dominates the cost. See
BENCHMARKS for throughput and the 10k ETA.

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
- Decision engine uses **OR rules**, not weighted averages: one strong signal ⇒ positive; a lone medium signal ⇒ review. Protects recall. Since phase04 the OR runs over the *bands each signal claims*, not over raw scores, because a score means something different in each signal (D-021).
- Every signal owns a `(weak, strong)` threshold pair; `confidence` is the winner's score normalized onto one shared scale (weak → 0.50, strong → 0.85). Monotonic, comparable, **not** a probability.
- Thresholds come from **calibration on the labeled set**, never intuition: `calibrate` grid-searches them and writes them into `config.py`. Bands: positive / review / negative.
- Signals are independent modules returning `SignalResult(score, bbox, method, detail)` so the decision layer stays pluggable.
- CPU-first. Performance work only if measured ETA for 10k images exceeds ~12 h (then: multiprocessing before any GPU runtime).

## Calibration flow
```text
data/labeled/{positive,negative}
        │  metrics.score_images  (load once, every signal scores every image)
        ▼
   [ScoredImage(filename, label, {signal: score})]
        │  calibrate.search      (grid over each signal's (weak, strong); band vectors, OR, metrics)
        ▼
   objective: max precision  s.t. catch-recall >= 0.97 and review <= 10%   (relaxed if unreachable, D-022)
        │
        ├─► metrics.evaluate on the winner  ─► output/calibration.json
        ├─► config.SIGNAL_THRESHOLDS block rewritten in place
        └─► gate verdict  ─► output/gate_failures.txt when it fails
```
Scoring is the only expensive step, so it happens once and tens of thousands of threshold
combinations are judged on the stored scores. The winner is re-measured through
`metrics.evaluate` - the same `decision.decide` the scanner runs - so the published numbers can
never drift from the shipped behaviour.

## Data flow & artifacts
`input/` → scanner walk → per-image signals → decision → incremental `output/results.csv` + `output/.progress.jsonl` (resume) → final `results.json` summary + `crops/`, `detected/`, `review/`.
Incremental writing, resume and the crop/detected/review folders are still ahead; phase02 writes
the CSV and JSON once at the end of the run.
