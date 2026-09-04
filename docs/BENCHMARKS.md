# Benchmarks (append-only)

> One row per run. `catch-recall` counts positives landing in positive ∪ review.

| Date | Phase | Dataset (P/N) | Signals | Precision(pos) | Catch-recall | Review % | imgs/s | Notes |
|---|---|---|---|---|---|---|---|---|
| 2026-09-04 | phase02 | 100/158 | ocr | 0.875 | 0.930 | 8.5% | 0.55 | t_rev=0.60 t_pos=0.95; OCR only, full set incl. AVIF; 7 positives score 0 (no readable brand text) -> SIFT's job in phase03; 10k ETA ~5.1 h |
