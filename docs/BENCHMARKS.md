# Benchmarks (append-only)

> One row per run. `catch-recall` counts positives landing in positive ∪ review.

| Date | Phase | Dataset (P/N) | Signals | Precision(pos) | Catch-recall | Review % | imgs/s | Notes |
|---|---|---|---|---|---|---|---|---|
| 2026-09-04 | phase02 | 100/158 | ocr | 0.875 | 0.930 | 8.5% | 0.55 | t_rev=0.60 t_pos=0.95; OCR only, full set incl. AVIF; 7 positives score 0 (no readable brand text) -> SIFT's job in phase03; 10k ETA ~5.1 h |
| 2026-09-04 | phase03 | 100/158 | ocr | 0.875 | 0.930 | 8.5% | 0.73 | t_rev=0.60 t_pos=0.95; SIFT added; OCR unchanged |
| 2026-09-04 | phase03 | 100/158 | sift | 1.000 | 0.550 | 14.3% | 3.97 | t_rev=0.05 t_pos=0.65; symbol matching alone: 55/100 positives, only 2 negatives ever score >0 (max 0.92); 2 real logo variants |
| 2026-09-04 | phase03 | 100/158 | ocr+sift | 0.875 | 0.940 | 8.9% | 0.62 | t_rev=0.60 t_pos=0.95; naive OR (what a scan ships); SIFT rescues 1 of the 7 OCR-blind positives, 6 still invisible to both; 10k ETA ~4.5 h |
| 2026-09-04 | phase04 | 100/158 | ocr+sift (calibrated) | 0.882 | 0.940 | 7.0% | 0.29 | **project baseline.** Calibrated bands, not a sweep: ocr weak=0.60/strong=0.95, sift weak=strong=0.45 (no SIFT review band). Confusion pos 82/12/6, neg 11/6/141; wins ocr=105 sift=6. GATE FAILED on catch-recall (0.940 < 0.97), ceiling is 0.940 - 6 positives score 0 on both signals. every phase04 rate was measured on a machine also running the test suite, so treat phase03's 0.62 img/s as the clean throughput reference |
| 2026-09-04 | phase04 | 100/158 | ocr | 0.875 | 0.930 | 8.5% | 0.24 | t_rev=0.60 t_pos=0.95; post-calibration-verify |
| 2026-09-04 | phase04 | 100/158 | sift | 1.000 | 0.550 | 14.3% | 1.68 | t_rev=0.05 t_pos=0.65; post-calibration-verify |
| 2026-09-04 | phase04 | 100/158 | ocr+sift | 0.875 | 0.940 | 8.9% | 0.21 | t_rev=0.60 t_pos=0.95; naive OR; post-calibration-verify |
