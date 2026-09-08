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
- [x] Kill+resume test passes (no duplicates, no reprocessing). Twice: an in-process Ctrl-C whose
      resumed `results.csv` is byte-identical to an uninterrupted run's, and a real
      `TerminateProcess` kill of a `scan` subprocess.
- [x] Dedup verified on synthetic copies (exact copy + a quality-40 re-encode: 1 pipeline call for
      3 files), and across a resume.
- [x] Full run completed - 3,370 images, the whole collection; summary in BENCHMARKS ->
      Production runs; `detected/` (843), `review/` (322), `crops/` (1,165), `results.csv`,
      `summary.json` and `errors.csv` all present.
- [x] `pytest` green: **269 passed** (265 fast + 4 slow).

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
- **2026-09-08 - step 6 measured, no multiprocessing needed.** 200 real images in 7 m 34 s =
  **0.44 img/s**, ETA(10k) **6 h 18 m** - under the 12 h bar the plan set, so `--workers` was not
  built and `multiprocessing` stayed out of the project.
- **2026-09-08 - step 8, THE RUN.** 3,370 images, 2 h 06 m 45 s, **0 errors**. Numbers in
  BENCHMARKS -> Production runs. The resume path was exercised for real: the run picked up the 200
  images from the timing run and skipped them.

## Completion Report

**Done 2026-09-08.** The scanner survives a multi-hour run over a real collection, and that run has
happened.

### What was built
Three new modules and a rewritten scan driver:
- `logoscanner/journal.py` - `output/.progress.jsonl`, one JSON line per image, flushed **and
  fsynced** before the next starts. It is the source of truth: `results.csv`, `summary.json` and
  `errors.csv` are rebuilt from it at the end of every run, interrupted ones included, so no report
  can ever be half-written (D-030). A torn line is dropped and costs one image.
- `logoscanner/dedup.py` - SHA-256 over bytes + a 64-bit dHash over pixels, both written with
  OpenCV so **no dependency was added**. Within 4 bits, the verdict is copied and no signal runs
  (D-031).
- `logoscanner/artifacts.py` - padded crops plus copies of the flagged originals into `detected/`
  and `review/`, input tree mirrored so same-named files cannot collide (D-032).
- `cli.run_scan` - skips journaled paths, wraps every image in try/except, handles Ctrl-C cleanly,
  live band counters on the bar, fuller end-of-run block, `--restart` and `--no-artifacts`.

### The run
| | |
|---|---|
| Images | **3,370** (2,552 unique + 818 duplicates) |
| Errors | **0** |
| Wall time | 2 h 06 m 45 s for 3,170 images |
| Throughput | 0.42 img/s, ETA(10k) 6 h 40 m |
| To review by hand | **843 detected + 322 review = 1,165 crops** |

Bands over all 3,370: positive 1,203 / review 423 / negative 1,744. Signal wins across the 1,626
flagged: ocr 927, ocr+sift 322, **emb 256**, sift 53, ocr+emb 50, plus 18 mixed - the embedding
signal is the sole claimer on 15.7% of everything flagged, which is phase05 continuing to earn its
keep.

### Three things worth remembering
1. **Dedup was worth far more than the CPU it saved.** 818 of 3,370 files (24.3%) are re-saves of
   something already scanned. That is ~35 minutes of pipeline time, but the real win is the 461
   redundant flagged copies it kept *out of the folders a human has to page through*.
2. **The 12 h performance bar was never approached, so no multiprocessing was written.** Measuring
   first (200 real images, 0.44 img/s) is what kept `multiprocessing`, a `--workers` flag and their
   Windows spawn-guard complexity out of the project entirely.
3. **Resume creates one trap, and it is a silent one.** A plain re-run after `calibrate` changes a
   threshold would happily reuse the *old* verdicts and report numbers that no longer match the
   config. `--restart` exists for exactly that, and it is documented next to the thresholds rather
   than buried in `--help`.

### Deviations from the plan
- **Step 6 (`--workers`) was deliberately not built.** The plan made it conditional on
  ETA(10k) > 12 h; measured 6 h 18 m. Building it anyway would have added a dependency-free but
  genuinely tricky Windows code path for no measured benefit.
- **The summary file keeps its phase01 name, `summary.json`.** The plan called it `results.json`;
  three phases of docs and tests already say `summary.json`, and it is a summary. Recorded in
  D-030 rather than silently renamed.
- **The collection is 3,370 images, not 10,000.** That is simply what `input/` holds; the ETA for
  10k is reported and comfortable.

### Known limitation
Artifacts are written when an image is *processed*, so a resume does not backfill them: scanning
with `--no-artifacts` and then resuming without the flag leaves the first run's flagged images in
the CSV but absent from `review/`. `--restart` is the fix. Backfilling would mean either holding
every scanned image's pixels or re-decoding the whole collection to rebuild a folder the CSV
already describes (D-032).

### Files
New: `logoscanner/{journal,dedup,artifacts}.py`, `tests/test_{journal,dedup,artifacts,scan_resume}.py`.
Changed: `logoscanner/{cli,results}.py`, `tests/test_results.py`, docs
ARCHITECTURE / CODEMAP / CHANGELOG / DECISIONS (D-030..D-032) / SETUP / BENCHMARKS.
Tests 208 -> 269.
