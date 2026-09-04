# Project Status

**Current phase:** none (phase03 done)
**Next phase:** phase04 - threshold calibration + the gate decision (PASSED -> skip 05-06; FAILED -> run 05)
**Gate state:** not evaluated (set in phase04)

## Where the detector stands
On the real labeled set (100 positive / 158 negative), `ocr,sift` naive-OR:
catch-recall **0.940**, precision **0.875**, review share **8.9%**, 0.62 img/s (~4.5 h for 10k).
SIFT alone is the precise-but-narrow signal: catch-recall 0.550 at precision **1.000** (only 2 of
158 negatives ever score above 0), 3.97 img/s.

phase03's target was the 7 positives OCR cannot read. SIFT caught **1** of them. The other 6 carry
neither readable brand text nor matchable symbol geometry:
`fgJCL84Y.jpg`, `Networking-Field-Day-9123_400x250.jpg`, `NSCP-CE-Diagram.png`,
`Screen-Shot-2020-09-23-at-8.33.59-PM.jpg`, `Untitled-1-1-1.png`, `ZPE-Systems-Frank-Basso.webp`.
Bands are still provisional (0.85 / 0.60) until phase04.

## User homework (blockers owned by the human)
- [ ] Create GitHub repo, add remote, push
- [x] Set the real `BRAND_TERMS` in `logoscanner/config.py` (`ZPE`, `ZPE Systems`)
- [x] Label real images into `data/labeled/positive|negative/` (100 / 158, all now readable)
- [x] Confirm `logo/` holds the variants SIFT should match (2 files, both full wordmarks)
- [ ] **Cheapest next lever:** a **symbol-only** logo file (the mark without the words) and a
      transparent-PNG variant in `logo/`. Both current variants are wordmarks, so SIFT is mostly
      re-finding the text OCR already reads; a bare mark is what the 6 blind positives would need.
      Drop any such file into `logo/` and re-run the benchmark - no code change required.
- [ ] Optional: eyeball the 6 blind positives above. If they are genuinely too small/abstract to
      match, phase04's gate should fail on purpose and phase05 (embeddings) is the answer.

## History
| Phase | Status | Finished | Commit | Notes |
|---|---|---|---|---|
| phase00 bootstrap | done | 2026-09-03 | 6529e95 | scaffold |
| phase01 foundation | done | 2026-09-03 | de93fb4 | CLI skeleton, safe IO, CSV/JSON reports, synthetic data tools, 23 tests; baseline 42 img/s |
| phase02 OCR signal | done | 2026-09-04 | b097bd5 | RapidOCR signal, signal registry, pipeline, `benchmark` command, 97 tests; catch-recall 0.930 / precision 0.875 |
| phase03 SIFT signal | done | 2026-09-04 | 052a2cf | keypoint match + homography verification, naive-OR benchmark row, 122 tests; ocr+sift catch-recall 0.940 / precision 0.875 |
