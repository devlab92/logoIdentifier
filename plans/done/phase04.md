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
- [x] `pytest` green (161 tests).
- [x] Calibration ran on REAL labeled data (100/158); thresholds persisted in `config.py` + D-023.
- [x] Calibrated metrics row in BENCHMARKS; gate verdict recorded in STATUS + D-023.
- [x] FAILED: `output/gate_failures.txt` written, 6 misses, all categorised `invisible to every signal`.

## Verify
```powershell
python -m logoscanner calibrate --labeled data\labeled
python -m logoscanner benchmark --labeled data\labeled --signals ocr,sift
pytest -q
```

## Out of scope
- Any new signal; performance work.

## Progress Log
- 2026-09-04 — `decision.py`: per-signal `(weak, strong)` thresholds, OR over the bands each
  signal claims, normalized confidence anchored on the config scale (D-021). `pipeline.py` is now
  orchestration only and re-exports `decide`/`Decision`; `scan` bands through it.
- 2026-09-04 — `metrics.py`: `score_images` (one pass, per-file scores kept) + `evaluate`
  (precision / catch-recall / review share / confusion / per-signal wins / miss filenames).
  `benchmark.score_labeled` now adapts over it, so there is one loading loop in the repo.
- 2026-09-04 — `calibrate.py` + `calibrate` subcommand: vectorised grid search over every
  signal's `(weak, strong)` pair, objective = max precision s.t. catch-recall >= 0.97 and
  review <= 10%, relaxation when unreachable (D-022); writes `output/calibration.json`, rewrites
  the marked block in `config.py`, renders the gate verdict.
- 2026-09-04 — tests: `test_decision.py` (truth table + confidence scale), `test_metrics.py`
  (hand-checked mini-set), `test_calibrate.py` (search, config round-trip, gate), plus `calibrate`
  CLI coverage. Suite 122 -> 161 green.

## Completion Report
**Done 2026-09-04.** The decision layer is calibrated and the gate is decided: **FAILED**, so
phase05 runs.

**Built**
- `decision.py` - per-signal `(weak, strong)` thresholds; the image takes the best band any signal
  claims (OR moved from raw scores to bands, D-021); `confidence` is the winner's score normalized
  so weak → 0.50 and strong → 0.85 on one shared, monotonic (non-probability) scale; `method`
  lists every signal that claimed the band, and the box comes from the strongest winner that could
  localise. `pipeline.py` is orchestration only now.
- `metrics.py` - `score_images` (one expensive pass, per-file scores kept) and `evaluate`
  (precision, catch-recall, review share, confusion, per-signal wins, miss filenames).
  `benchmark.score_labeled` adapts over it, so there is one loading loop in the repo.
- `calibrate.py` + `python -m logoscanner calibrate` - vectorised search over all 44,100 threshold
  combinations, objective = max precision s.t. catch-recall >= 0.97 and review <= 10%, relaxing to
  the attainable ceiling when the constraint set is empty (D-022). Writes
  `output/calibration.json`, rewrites the marked block in `config.py`, prints the verdict, and on
  failure writes `output/gate_failures.txt` with a categorised reason per miss.

**Calibration result** (100 positive / 158 negative): OCR 0.60/0.95, SIFT 0.45/0.45 →
precision 0.882, catch-recall 0.940, review share 7.0%; positives 82/12/6, negatives 11/6/141;
wins ocr=105, sift=6. SIFT's weak and strong coincide: the search found no useful SIFT review
band, so it either flags or stays silent.

**GATE: FAILED** - review share passes (7.0% <= 10%), catch-recall does not (0.940 < 0.97). The 6
missing positives score exactly 0 on both signals, so the ceiling is 0.940 and no threshold can
reach the target. `phase05.md` and `phase06.md` stay in `plans/active/`; **phase05 runs next**.

**Deviations from the plan**
- The plan's `ocr_strong/weak, sift_strong/weak` became a generic `config.SIGNAL_THRESHOLDS`
  table plus `FALLBACK_THRESHOLDS`, so a phase05 signal needs no code change to be calibrated.
- `POSITIVE_THRESHOLD` / `REVIEW_THRESHOLD` were kept, redefined as the anchors of the normalized
  confidence scale (0.85 / 0.50), which keeps `config.band_for` honest instead of deleting it.
- The grid search is exhaustive (44,100 points) but vectorised; the winner is then re-measured
  through `metrics.evaluate` - the same `decision.decide` the scanner runs - so published numbers
  cannot drift from shipped behaviour.

**Not done / follow-ups**
- The cheapest lever for the 6 misses is still user homework: a symbol-only logo variant in
  `logo/` would let SIFT try them without any new code. phase05 should start only after that is
  ruled out.
