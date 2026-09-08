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
| 2026-09-08 | phase05 | ~~100/158~~ | ocr | 0.875 | 0.930 | 8.5% | 0.65 | t_rev=0.60 t_pos=0.95; phase05: embedding signal added; calibrated bands, gate PASSED |
| 2026-09-08 | phase05 | ~~100/158~~ | sift | 1.000 | 0.550 | 14.3% | 3.70 | t_rev=0.05 t_pos=0.65; phase05: embedding signal added; calibrated bands, gate PASSED |
| 2026-09-08 | phase05 | ~~100/158~~ | emb | 1.000 | 1.000 | 90.7% | 1.03 | t_rev=0.40 t_pos=0.95; phase05: embedding signal added; calibrated bands, gate PASSED |
| 2026-09-08 | phase05 | ~~100/158~~ | ocr+sift+emb | 0.876 | 1.000 | 57.4% | 0.36 | t_rev=0.40 t_pos=0.95; naive OR; phase05: embedding signal added; calibrated bands, gate PASSED |
| 2026-09-08 | phase05 | ~~100/158~~ | ocr+sift+emb (calibrated) | 0.826 | 0.970 | 9.7% | 0.25 | **SUPERSEDED** (kept for history) - measured before two mislabeled positives were found (D-028). Calibrated bands: emb 0.80/0.90, ocr weak=strong=0.75, sift weak=strong=0.65. Confusion pos 95/2/3, neg 20/23/115; wins ocr=109 emb=30 sift=1. **GATE PASSED** (catch-recall 0.970 >= 0.97, review 9.7% <= 10%); ceiling rose 0.940 -> 1.000. The four sweep rows above pick their own recall-first operating point (emb alone reaches recall 1.000, but at a 90.7% review pile) - they show what each signal *could* do, not what ships |
| 2026-09-08 | phase05 | 98/160 | ocr | 0.875 | 0.949 | 8.5% | 0.78 | t_rev=0.60 t_pos=0.95; phase05 re-run on corrected labels (98/160): ZPE-Systems-Frank-Basso.webp + fgJCL84Y.jpg confirmed logo-free by the user and moved to negative/ |
| 2026-09-08 | phase05 | 98/160 | sift | 1.000 | 0.561 | 14.3% | 4.14 | t_rev=0.05 t_pos=0.65; phase05 re-run on corrected labels (98/160): ZPE-Systems-Frank-Basso.webp + fgJCL84Y.jpg confirmed logo-free by the user and moved to negative/ |
| 2026-09-08 | phase05 | 98/160 | emb | 1.000 | 1.000 | 86.8% | 1.42 | t_rev=0.45 t_pos=0.95; phase05 re-run on corrected labels (98/160): ZPE-Systems-Frank-Basso.webp + fgJCL84Y.jpg confirmed logo-free by the user and moved to negative/ |
| 2026-09-08 | phase05 | 98/160 | ocr+sift+emb | 0.876 | 1.000 | 34.9% | 0.45 | t_rev=0.70 t_pos=0.95; naive OR; phase05 re-run on corrected labels (98/160): ZPE-Systems-Frank-Basso.webp + fgJCL84Y.jpg confirmed logo-free by the user and moved to negative/ |
| 2026-09-08 | phase05 | 98/160 | ocr+sift+emb (calibrated) | 0.873 | 0.980 | 8.9% | 0.45 | **project baseline.** Calibrated bands on the corrected label set, not a sweep: emb 0.85/0.95, ocr 0.75/0.85, sift weak=strong=0.45. Confusion pos 89/7/2, neg 13/16/131; wins ocr=108 emb=15 sift=2. **GATE PASSED** (catch-recall 0.980 >= 0.97, review 8.9% <= 10%); ceiling 1.000. The two misses are `Screen-Shot-2020-09-23...` and `Untitled-1-1-1.png`. Rows marked ~~100/158~~ above predate the label fix and are not comparable. The four sweep rows pick their own recall-first point: note that **emb alone reaches catch-recall 1.000**, which is why the ceiling moved off 0.940 - but it does so with an 86.8% review pile, so it is a ceiling, not an operating point |

## Production runs (append-only)

> The table above measures *quality* on the labeled set. These rows measure a real scan of the
> unlabeled collection: there are no labels here, so there is no precision or recall to report -
> only what the scanner found, what it cost, and what it wrote.

### 2026-09-08 - phase07 - `input/` (the full WordPress collection)

| | |
|---|---|
| Images walked | **3,370** |
| Unique images actually analysed | 2,552 |
| Duplicates (verdict copied, no pipeline pass) | **818** (24.3%) |
| Errors | **0** |
| Wall time | 2 h 06 m 45 s for 3,170 images (200 were already journaled from the timing run) |
| Throughput | **0.42 img/s** end to end, duplicates included |
| ETA 10,000 | 6 h 40 m |
| Signals | ocr, sift, emb at the D-029 calibrated thresholds |

Bands, and the same counts with duplicates removed - the second column is what a human actually
has to look at, since a duplicate is never copied into `detected/` or `review/`:

| band | all 3,370 | unique only |
|---|---|---|
| positive | 1,203 | **843** |
| review | 423 | **322** |
| negative | 1,744 | 1,387 |

Which signal claimed the winning band, over all 1,626 flagged images:

| method | count |
|---|---|
| ocr | 927 |
| ocr+sift | 322 |
| emb | 256 |
| sift | 53 |
| ocr+emb | 50 |
| emb+ocr | 8 |
| sift+ocr | 7 |
| emb+sift | 3 |

Artifacts written: `detected/` 843 files (103.6 MB), `review/` 322 files (18.7 MB), `crops/` 1,165
files (4.7 MB), `.progress.jsonl` 3,370 lines (1.1 MB). Every flagged image carried a box, so every
one has a crop.

Notes:
- **Zero errors in 3,370 real files** - every format in the collection decoded, AVIF included.
- **Dedup paid for itself twice.** It removed roughly 35 minutes of pipeline time, and - the part
  that matters more - it kept 461 redundant copies (360 positive + 101 review) out of the folders
  a human has to page through.
- **The resume path was exercised in production, not only in tests.** The run picked up the 200
  images from the timing run and skipped them; re-running the finished command afterwards
  processed 0 images and rewrote the reports in under a second.
- **`emb` is not redundant.** It is the sole claimer on 256 flagged images - 15.7% of everything
  flagged - which OCR and SIFT both missed. That is the phase05 signal earning its 2 GB.
- The 35.7% positive rate is high for a random image collection but expected for a company's own
  site export, where the mark sits in headers, footers and marketing material. At the labeled-set
  precision of 0.873 a meaningful minority of those will be false positives; the user's review of
  `detected/` and `review/` is what turns this into labels for the next calibration.

