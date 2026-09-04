# Project Status

**Current phase:** none (phase04 done)
**Next phase:** phase05 - region proposals + embedding similarity (the gate sent us here)
**Gate state:** **FAILED** 2026-09-04 - catch-recall 0.940 < target 0.97 (review share 7.0% <= 10%
passes). Recorded in D-023; misses categorised in `output/gate_failures.txt`. phase06 stays
conditional on phase05's result.

## Where the detector stands
Calibrated on the real labeled set (100 positive / 158 negative), thresholds OCR 0.60/0.95 and
SIFT 0.45/0.45 (`output/calibration.json`, D-023):
precision **0.882**, catch-recall **0.940**, review share **7.0%**.
Confusion - positives: 82 positive / 12 review / 6 negative; negatives: 11 positive / 6 review /
141 negative. OCR decided 105 of the 111 flagged-or-reviewed images, SIFT 6. SIFT has no review
band by choice: it either flags or stays silent.

The 6 misses score **0 on both signals**, so no threshold reaches 0.97 - that is exactly why the
gate failed and phase05 exists:
`fgJCL84Y.jpg`, `Networking-Field-Day-9123_400x250.jpg`, `NSCP-CE-Diagram.png`,
`Screen-Shot-2020-09-23-at-8.33.59-PM.jpg`, `Untitled-1-1-1.png`, `ZPE-Systems-Frank-Basso.webp`.

## User homework (blockers owned by the human)
- [~] GitHub repo created and `origin` set (`devlab92/logoIdentifier`); **push still pending** -
      run `git push -u origin main` yourself (the agent's push is blocked by permissions)
- [x] Set the real `BRAND_TERMS` in `logoscanner/config.py` (`ZPE`, `ZPE Systems`)
- [x] Label real images into `data/labeled/positive|negative/` (100 / 158, all now readable)
- [x] Confirm `logo/` holds the variants SIFT should match (2 files, both full wordmarks)
- [ ] **Cheapest next lever, still open:** a **symbol-only** logo file (the mark without the words)
      and a transparent-PNG variant in `logo/`. Both current variants are wordmarks, so SIFT is
      mostly re-finding the text OCR already reads. Drop any such file into `logo/` and re-run
      `calibrate` - no code change required, and it could still lift the 6 blind positives more
      cheaply than phase05 does.
- [ ] Optional: eyeball the 6 blind positives above before phase05 starts, so we know what the
      embedding signal has to see (tiny mark? photo of a person? diagram?).

## History
| Phase | Status | Finished | Commit | Notes |
|---|---|---|---|---|
| phase00 bootstrap | done | 2026-09-03 | 6529e95 | scaffold |
| phase01 foundation | done | 2026-09-03 | de93fb4 | CLI skeleton, safe IO, CSV/JSON reports, synthetic data tools, 23 tests; baseline 42 img/s |
| phase02 OCR signal | done | 2026-09-04 | b097bd5 | RapidOCR signal, signal registry, pipeline, `benchmark` command, 97 tests; catch-recall 0.930 / precision 0.875 |
| phase03 SIFT signal | done | 2026-09-04 | 052a2cf | keypoint match + homography verification, naive-OR benchmark row, 122 tests; ocr+sift catch-recall 0.940 / precision 0.875 |
| phase04 decision + calibration + GATE | done | 2026-09-04 | 92e9185 | per-signal thresholds, `calibrate` command, 161 tests; calibrated catch-recall 0.940 / precision 0.882 / review 7.0%; **gate FAILED -> phase05** |
