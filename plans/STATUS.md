# Project Status

**Current phase:** none (phase01 done)
**Next phase:** phase02 - OCR signal + `benchmark` command
**Gate state:** not evaluated (set in phase04: PASSED → skip 05–06; FAILED → run 05)

## User homework (blockers owned by the human)
- [ ] Create GitHub repo, add remote, push
- [ ] Add real logo variants to `logo/` (light/dark/symbol-only, transparent PNG where possible)
- [ ] **Now unblocked:** set the real `BRAND_TERMS` in `logoscanner/config.py` (currently the `ACME` placeholder)
- [ ] **Now unblocked:** label ~300 real images into `data/labeled/positive|negative/` (~100-150 positives; include tiny, partial, over-photo, dark/light and low-res logos). Check with `python tools\check_dataset.py`.

## History
| Phase | Status | Finished | Commit | Notes |
|---|---|---|---|---|
| phase00 bootstrap | done | 2026-09-03 | 6529e95 | scaffold |
| phase01 foundation | done | 2026-09-03 | de93fb4 | CLI skeleton, safe IO, CSV/JSON reports, synthetic data tools, 23 tests; baseline 42 img/s |
