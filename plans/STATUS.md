# Project Status

**Current phase:** none (phase02 done)
**Next phase:** phase03 - SIFT signal (shape/keypoint match against the logo variants)
**Gate state:** not evaluated (set in phase04: PASSED -> skip 05-06; FAILED -> run 05)

## Where the detector stands
OCR alone, on the real labeled set (100 positive / 158 negative):
catch-recall **0.930**, precision **0.875**, review share **8.5%**, 0.55 img/s (~5.1 h for 10k).
The 7 missed positives score exactly 0 - no brand-like text in them at all - so they are the
target phase03's SIFT signal has to hit. Bands are provisional (0.85 / 0.60) until phase04.

## User homework (blockers owned by the human)
- [ ] Create GitHub repo, add remote, push
- [x] Set the real `BRAND_TERMS` in `logoscanner/config.py` (`ZPE`, `ZPE Systems`)
- [x] Label real images into `data/labeled/positive|negative/` (100 / 158, all now readable)
- [ ] **For phase03:** confirm `logo/` holds the variants SIFT should match. Two files are there
      (`ZPE System - Logo White.png`, `ZPE Systems - Gray Logo FullHD.png`); a symbol-only mark
      and a transparent-PNG variant would help if they exist.
- [ ] Optional: more positives among the 7 OCR-blind kinds (logo as pure shape, no legible text)
      would make phase03's benchmark sharper.

## History
| Phase | Status | Finished | Commit | Notes |
|---|---|---|---|---|
| phase00 bootstrap | done | 2026-09-03 | 6529e95 | scaffold |
| phase01 foundation | done | 2026-09-03 | de93fb4 | CLI skeleton, safe IO, CSV/JSON reports, synthetic data tools, 23 tests; baseline 42 img/s |
| phase02 OCR signal | done | 2026-09-04 | (pending) | RapidOCR signal, signal registry, pipeline, `benchmark` command, 97 tests; catch-recall 0.930 / precision 0.875 |
