# phase04 — Decision Engine, Calibration & THE GATE

**Goal:** rule-based decision bands, thresholds calibrated on the real labeled set, and the go/no-go decision on ML phases.
**Depends on:** phase03
**Conditional?** no

## Context to load
- `docs/CODEMAP.md`, `docs/BENCHMARKS.md`, `logoscanner/{config,signals,pipeline}.py`

## User prerequisites (hard)
- `data/labeled/` populated with real images (~100+ positives, ~150+ negatives, hard cases included). If missing: stop and request it — synthetic data must NOT drive calibration.

## Steps
1. `logoscanner/decision.py` — `decide(results) -> (band, confidence, bbox, method)`:
   - any signal ≥ its **strong** threshold → `positive`
   - else any signal ≥ its **weak** threshold → `review`
   - else `negative`
   - `confidence` = best normalized score (document: monotonic, not a probability); `method` = winning signal(s).
2. `logoscanner/metrics.py` — from labeled dirs: precision(positive band), **catch-recall** (positives in positive ∪ review), review share, confusion counts, per-signal wins, and the list of false-negative filenames.
3. `calibrate` subcommand — grid-search the 4 thresholds (`ocr_strong/weak`, `sift_strong/weak`) on the labeled set. Objective: **maximize precision subject to catch-recall ≥ 0.97 and review share ≤ 10%**; tie-break by higher catch-recall, then lower review share. Write `output/calibration.json`, update the values in `config.py`, record chosen numbers + date in `docs/DECISIONS.md`.
4. Wire `decide()` into `scan`; remove the provisional phase02 rule.
5. **GATE evaluation** on the calibrated labeled-set metrics:
   - **PASSED** (targets met): record in `plans/STATUS.md` + DECISIONS; move `phase05.md` and `phase06.md` to `plans/done/` each with Completion Report = `SKIPPED — gate passed on <date>, metrics: ...`. Next phase = phase07.
   - **FAILED:** record which target failed; copy the false-negative files list to `output/gate_failures.txt` with a one-line reason each (tiny logo / stylized text / occlusion...). Next phase = phase05.
6. Tests: decision truth-table; metrics on a crafted mini-set with known answers.
7. Docs: ARCHITECTURE (bands + calibration flow), CODEMAP, CHANGELOG, BENCHMARKS (calibrated row — the project baseline).

## Acceptance criteria
- [ ] `pytest` green.
- [ ] Calibration ran on REAL labeled data; thresholds persisted in config + DECISIONS.
- [ ] Calibrated metrics row in BENCHMARKS; gate verdict recorded in STATUS.
- [ ] If FAILED: `output/gate_failures.txt` exists with categorized misses.

## Verify
```powershell
python -m logoscanner calibrate --labeled data\labeled
python -m logoscanner benchmark --labeled data\labeled --signals ocr,sift
pytest -q
```

## Out of scope
- Any new signal; performance work.

## Progress Log

## Completion Report
