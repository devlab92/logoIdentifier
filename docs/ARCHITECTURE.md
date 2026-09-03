# Architecture

> Keep this file matching reality. Update on any behavioral change.

## Current state
**phase01 done: skeleton, no detection.** `python -m logoscanner scan` walks a folder
(`io_utils.iter_images`), loads each image safely (`io_utils.load_image`, downscaled to
`config.MAX_SIDE`, decode failures recorded not raised), emits one `results.ResultRow` per
image and writes `results.csv` + `summary.json`, then prints throughput and the ETA for
10,000 images. Every image currently scores `0.0 / negative / method=none` - the signal
modules below land from phase02. Synthetic data (`tools/make_synthetic.py`) stands in for
the real labeled set until the user fills `data/labeled/`.

Measured phase01 baseline: ~42 img/s on 800x600 PNGs (walk + decode + resize only),
i.e. ~4 minutes for 10k. The 12 h budget in Key principles is therefore almost entirely
available to the detection signals.

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
