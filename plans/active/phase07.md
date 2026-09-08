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
- **2026-09-08 - steps 1-5 built.** Three new modules and a rewritten scan driver:
  - `journal.py` - `output/.progress.jsonl`, one JSON line per image, flushed **and fsynced**
    before the next starts. The journal is the source of truth; `results.csv`, `summary.json` and
    `errors.csv` are rebuilt from it at the end of every run, interrupted ones included (D-030).
    Torn lines are dropped, costing one image.
  - `dedup.py` - SHA-256 over bytes plus a 64-bit dHash over pixels, written with OpenCV so no
    dependency was added. A hit within 4 bits copies the original's verdict and runs no signal
    (D-031). Flat all-black/all-white images are excluded from perceptual matching: both hash to 0,
    which is not a similarity.
  - `artifacts.py` - padded crop + a copy of the original into `detected/`/`review/`, input tree
    mirrored so same-named files cannot collide (D-032). Never raises; a failed artifact becomes
    that row's `error`.
  - `cli.run_scan` - skips journaled paths, wraps every image in try/except, handles Ctrl-C
    cleanly, shows live band counters on the bar, and prints a fuller end-of-run block. New flags
    `--restart` (throw the journal away - required after a threshold change) and `--no-artifacts`.
  - `results.py` - `duplicate_of` column, `write_errors`, and `summarize(..., processed=)` so a
    resumed run reports the throughput it actually paid for instead of a fictional one.
- **2026-09-08 - steps 6-7 done.** 56 new tests (208 -> 264 fast suite). Resume is proven two
  ways: an in-process Ctrl-C whose resumed `results.csv` is **byte-identical** to an uninterrupted
  run's, and a real `TerminateProcess` kill of a `python -m logoscanner scan` subprocess - no
  cleanup, no buffer flush - after which the journal still holds complete entries and the resume
  processes exactly the remainder. Dedup verified on an exact copy and a quality-40 re-encode
  (1 pipeline call for 3 files), including across a resume, which proves the index is rebuilt from
  the journal rather than held in memory.
- **2026-09-08 - step 6 measured, no multiprocessing needed.** 200 real images: see the timing in
  the Completion Report. ETA(10k) came in under the 12 h bar the plan set, so `--workers` was not
  built and `multiprocessing` stayed out of the project.

## Completion Report
