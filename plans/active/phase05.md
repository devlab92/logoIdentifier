# phase05 — Region Proposals + Visual Embeddings (CONDITIONAL)

**Goal:** recover the recall the baseline missed by comparing candidate regions against logo-variant embeddings.
**Depends on:** phase04
**Conditional?** **Only if the phase04 gate FAILED.** If STATUS says PASSED, this file should already be in `plans/done/` marked SKIPPED — do not execute.

## Context to load
- `plans/STATUS.md`, `output/gate_failures.txt`, `docs/CODEMAP.md`, `logoscanner/{config,signals,pipeline,decision}.py`

## User prerequisites
- Accept a heavy local dependency (PyTorch CPU, ~2 GB disk). Still free/offline after download.

## Steps
1. Read `output/gate_failures.txt` first — let the actual failure modes steer choices below; note conclusions in DECISIONS.
2. Add `torch` (CPU build) + `timm` (or `transformers`) to requirements → DECISIONS entry (size/justification).
3. `logoscanner/proposals.py` — candidate regions per image: OCR text boxes ∪ SIFT projected box ∪ MSER stable regions (merge overlapping, pad 15%, filter by min/max area) ∪ coarse 3×3 tile fallback. Cap N regions (config).
4. `logoscanner/embeddings.py` — `EmbeddingSignal`: DINOv2-small, CPU; embed each `logo/` variant once (L2-normalized); embed candidate crops (resize/pad to model input); score = max cosine across variants; bbox = best region. Plain NumPy — no FAISS (D-004).
5. Register signal; extend `benchmark`/`calibrate` to include `emb_strong/weak` thresholds; **recalibrate** on the labeled set.
6. **Re-run the GATE** (same targets, same protocol as phase04 step 5): PASSED → skip phase06 (move to done/ as SKIPPED) → phase07. FAILED → phase06, update gate_failures.
7. Tests: proposals on synthetic (logo region among candidates); embedding smoke (dummy-logo crop scores ≫ random crop); mark model-download-dependent tests `slow`.
8. Docs: ARCHITECTURE (new stage), CODEMAP, CHANGELOG, DECISIONS, BENCHMARKS.

## Acceptance criteria
- [ ] `pytest` green (fast suite; `slow` may be skipped in CI-style runs).
- [ ] Recalibrated metrics in BENCHMARKS; gate re-verdict in STATUS.
- [ ] Throughput measured and noted (embeddings will be the slowest stage — record imgs/s).

## Verify
```powershell
python -m logoscanner calibrate --labeled data\labeled
python -m logoscanner benchmark --labeled data\labeled --signals ocr,sift,emb
pytest -q -m "not slow"
```

## Out of scope
- Training anything; GPU runtimes; FAISS.

## Progress Log

## Completion Report
