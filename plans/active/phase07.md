# phase07 — Production Hardening & the 10,000-image Run

**Goal:** make `scan` resumable, deduplicating, crash-proof and observable; then run the full collection.
**Depends on:** phase04 (or 05/06 if they ran)
**Conditional?** no

## Context to load
- `docs/CODEMAP.md`, `docs/ARCHITECTURE.md`, `logoscanner/{cli,pipeline,io_utils,results,config}.py`

## User prerequisites
- The full collection available under `input/` (subfolders fine).

## Steps
1. **Resumability:** `output/.progress.jsonl` — one JSON line per processed file (`path, sha256, band, confidence, bbox, method, ts`). On start, load it and skip done files; flush per file; handle `KeyboardInterrupt` cleanly. Final consolidation rewrites `results.csv` + `results.json` from the journal (journal is the source of truth).
2. **Dedup:** SHA-256 exact duplicates + in-house 64-bit dHash (OpenCV resize+threshold, no new deps); Hamming ≤ 4 ⇒ mark `duplicate_of` and copy the original's verdict without reprocessing.
3. **Review artifacts:** save crops (bbox + 10% padding) for `positive` and `review` → `output/crops/`; copy those images → `output/detected/` and `output/review/`. Negatives are listed only.
4. **Robustness:** per-file try/except → `output/errors.csv` (path, error), run continues; unsupported/corrupt formats logged, never fatal.
5. **Observability:** `tqdm` progress with live band counters; end-of-run summary block (totals per band, duplicates, errors, imgs/s, wall time).
6. **Performance (only if needed):** measure on 200 real images; if ETA(10k) > 12 h, add `--workers N` (`multiprocessing`, Windows-safe: `if __name__ == "__main__"` guard, per-worker signal init). GPU runtimes remain out of scope (D-005).
7. **Resume test:** scripted kill+resume on a synthetic set; assert no reprocessing and identical final CSV.
8. **THE RUN:** user launches `scan` on `input/`; monitor; append the real-collection summary to BENCHMARKS.
9. Docs: ARCHITECTURE (journal/dedup flow), CODEMAP, CHANGELOG.

## Acceptance criteria
- [ ] Kill+resume test passes (no duplicates, no reprocessing).
- [ ] Dedup verified on synthetic copies.
- [ ] Full 10k run completed; summary in BENCHMARKS; `detected/`, `review/`, `crops/`, `results.csv/json` present.
- [ ] `pytest` green.

## Verify
```powershell
pytest -q
python -m logoscanner scan --input input --output output
```

## User homework after this phase
- Manually review `output/review/` (use `crops/` for speed). Move confirmed images' labels into `data/labeled/` — this feeds the improvement loop (recalibrate anytime with the grown set).

## Progress Log

## Completion Report
