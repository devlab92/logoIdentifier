# Project Status

**Current phase:** none (phase07 done)
**Next phase:** phaseFinal - packaging + USER_GUIDE. **It is worth doing the review homework below
first:** the 1,165 crops this run produced are the raw material for a recalibration, and phaseFinal
ships whatever the thresholds say at that point.

## The collection has been scanned (phase07, 2026-09-08)
3,370 images, 2 h 06 m 45 s, **0 errors**, 0.42 img/s. 818 (24.3%) were duplicates whose verdict was
copied instead of recomputed. Full numbers in BENCHMARKS -> Production runs.

| where to look | what is in it |
|---|---|
| `output/crops/` | **1,165 crops - start here.** Just the matched box of each flagged image |
| `output/detected/` | 843 images the scanner calls `positive` |
| `output/review/` | 322 images it is unsure about |
| `output/results.csv` | all 3,370 rows: band, confidence, box, method, `duplicate_of`, error |
| `output/errors.csv` | empty but for its header - nothing failed |

Duplicates are listed in the CSV (naming the original in `duplicate_of`) but deliberately **not**
copied into `detected/`/`review/`: 461 redundant copies you do not have to look at twice.

The scan is resumable - stop it any time and re-run the same command. **After changing a threshold,
a signal or `logo/`, pass `--restart`**, or the old verdicts in `output/.progress.jsonl` are reused
(D-030).

**Gate state:** **PASSED** 2026-09-08 - catch-recall 0.980 >= target 0.97, review share 8.9% <=
10%. Recorded in D-029. `output/gate_failures.txt` no longer exists because there is no gate
failure to describe. **phase06 (fine-tuned nano detector) is unnecessary and was moved to
`plans/done/` marked SKIPPED** - no bounding-box annotation work is required of the user, and no
AGPL training dependency entered the project.

## Dataset correction (read this before comparing to older numbers)
`ZPE-Systems-Frank-Basso.webp` and `fgJCL84Y.jpg` were labeled positive but **contain no logo at
all** (user-confirmed 2026-09-08, D-028). They are now in `data/labeled/negative/`, where they
serve as hard negatives. The labeled set is **98 positive / 160 negative**.

Every metric below is on that corrected set. Phase02-04 numbers in the History table were measured
on the old 100/158 set and are **not directly comparable** - two of phase04's six "misses" were
never misses.

## Where the detector stands
Calibrated on the corrected labeled set (three signals, 9,261,000 threshold combinations,
`output/calibration.json`, D-029):

| signal | weak (review) | strong (positive) |
|---|---|---|
| emb | 0.85 | 0.95 |
| ocr | 0.75 | 0.85 |
| sift | 0.45 | 0.45 |

precision **0.873**, catch-recall **0.980**, review share **8.9%**, throughput **0.45 img/s**.
Confusion - positives: 89 positive / 7 review / 2 negative; negatives: 13 positive / 16 review /
131 negative. Signal wins: ocr 108, emb 15, sift 2.

SIFT calibrated to weak == strong, so it either flags or stays silent; OCR and the embedding
signal both carry a real review band.

**The embedding signal is what cleared the gate, not the relabeling.** Phase04's detector
re-scored on the corrected labels reaches only catch-recall 0.959 - still short of 0.97. Against
that fair baseline, phase05 bought 0.959 -> 0.980 recall for about one point of precision
(0.882 -> 0.873) and two points of review pile (7.0% -> 8.9%).

Two positives are still missed, both genuine detector failures:
- `Screen-Shot-2020-09-23-at-8.33.59-PM.jpg` - OCR sees the wordmark but garbles it to two
  characters at 0.54 confidence, and no crop cleared the embedding bar.
- `Untitled-1-1-1.png` - a product diagram the embedding *did* catch at the looser thresholds
  calibrated on the mislabeled set. With cleaner labels the search could afford to be stricter and
  took the precision instead. If this image matters more than the false positives that strictness
  buys back, lower `emb` weak/strong - that is the dial.

## User homework (blockers owned by the human)
- [ ] **Review `output/crops/` (fast) or `output/detected/` + `output/review/` (full images).**
      Move what you confirm into `data/labeled/positive|negative/`, then re-run
      `python -m logoscanner calibrate --labeled data\labeled`. The labeled set is 258 images and
      the scan just produced 1,165 candidates - this is the single biggest available improvement to
      the detector, and it needs a human, not more code.
- [x] GitHub repo `devlab92/logoIdentifier` created, `origin` set, and **pushed** - the earlier
      permission block has cleared; `main` is up to date through phase05 (b88e5e8)
- [x] Set the real `BRAND_TERMS` in `logoscanner/config.py` (`ZPE`, `ZPE Systems`)
- [x] Label real images into `data/labeled/positive|negative/` - now 98/160 after the two
      logo-free images were reclassified
- [x] Symbol-only logo variant added to `logo/` (3 files). Re-calibrated with it on `ocr,sift`:
      **it changed nothing** - byte-identical metrics, same misses. The SIFT template is genuinely
      built from it (120 descriptors), so the lever is spent, not untried.
- [x] Confirmed the two unfindable photos carry no logo (D-028)
- [ ] Optional: decide whether the product wordmark **"Nodegrid"** should count as company
      branding. Ruled out this phase (ZPE marks only); it is a scope question, not a recall one.
- [ ] Optional: if the review pile ever needs shrinking, or `Untitled-1-1-1.png` needs catching,
      the `emb` thresholds are the single dial. Re-run `calibrate` after any change.

## History
| Phase | Status | Finished | Commit | Notes |
|---|---|---|---|---|
| phase00 bootstrap | done | 2026-09-03 | 6529e95 | scaffold |
| phase01 foundation | done | 2026-09-03 | de93fb4 | CLI skeleton, safe IO, CSV/JSON reports, synthetic data tools, 23 tests; baseline 42 img/s |
| phase02 OCR signal | done | 2026-09-04 | b097bd5 | RapidOCR signal, signal registry, pipeline, `benchmark` command, 97 tests; catch-recall 0.930 / precision 0.875 *(old 100/158 labels)* |
| phase03 SIFT signal | done | 2026-09-04 | 052a2cf | keypoint match + homography verification, naive-OR benchmark row, 122 tests; ocr+sift catch-recall 0.940 / precision 0.875 *(old labels)* |
| phase04 decision + calibration + GATE | done | 2026-09-04 | 92e9185 | per-signal thresholds, `calibrate` command, 161 tests; catch-recall 0.940 / precision 0.882 / review 7.0% *(old labels; 0.959 re-scored on corrected ones)*; **gate FAILED -> phase05** |
| phase05 proposals + embeddings + GATE | done | 2026-09-08 | 60d5c10 | region proposals + frozen DINOv2-small (`emb`), torch/timm added, OCR read memoised, calibration search made scalable, 2 mislabeled positives found; catch-recall 0.980 / precision 0.873 / review 8.9% on 98/160; **gate PASSED -> phase06 SKIPPED** |
| phase06 nano detector | **skipped** | 2026-09-08 | — | not needed: phase05 met the gate. No annotation work, no AGPL dependency |
| phase07 hardening + THE RUN | done | 2026-09-08 | (see below) | resume journal, SHA-256 + dHash dedup, crops/detected/review, errors.csv, `--restart`/`--no-artifacts`, 269 tests. **Full collection scanned: 3,370 images, 2 h 06 m, 0 errors, 24.3% duplicates.** No multiprocessing: measured ETA(10k) 6 h 18 m, under the 12 h bar |
