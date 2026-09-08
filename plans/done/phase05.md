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

**2026-09-04 — step 0: the cheap lever first.** `logo/` had gained `ZPE Symbol Only.png` since
STATUS was written (the "cheapest next lever" homework item). Re-ran `calibrate` on `ocr,sift`
before adding any dependency. The symbol template *is* live (120 descriptors, 3 templates built),
and the result was byte-identical: precision 0.882, catch-recall 0.940, review 7.0%, the same 6
misses at ocr=0.00 sift=0.00. Lever exhausted; phase05 confirmed necessary.

**2026-09-04 — step 1: the misses are three different problems, not one.** Diagnosed each blind
positive locally (OCR raw lines + SIFT match counts):
- *Product-diagram images* (`NSCP-CE-Diagram.png`, `Untitled-1-1-1.png`) — OCR reads 15 clean
  lines including **"Nodegrid"** at 0.98-1.00 confidence. Invisible only because `BRAND_TERMS` is
  `["ZPE", "ZPE Systems"]`. **User decision: not in scope — ZPE marks only.** They stay misses and
  must be caught visually.
- *Stylised wordmark* (`Screen-Shot-2020-09-23-at-8.33.59-PM.jpg`) — OCR sees the mark but garbles
  it to a 2-character string at 0.54. The *box* is right even though the text is wrong: this is
  what makes OCR line boxes the highest-priority region proposal.
- *Small photos* (`ZPE-Systems-Frank-Basso.webp` 200x200, `fgJCL84Y.jpg` 300x300) — zero OCR
  lines, 3 good SIFT matches. Whether a mark is present at all could not be confirmed without
  viewing company images (hard rule 4). **User decision: ignore what cannot be confirmed** — these
  do not steer the design.
- `Networking-Field-Day-9123_400x250.jpg` — event branding, a lone `'P'` at 0.72.

**2026-09-04 — steps 2-4: built.** `torch 2.14.0+cpu` + `timm 1.0.29` installed (user-approved,
D-024). New `proposals.py` (OCR boxes / SIFT quad / MSER / tile fallback, padded, area-filtered,
merged, budget-capped) and `embeddings.py` (frozen DINOv2-small, crops embedded in one batch, max
cosine against logo variants composited on white *and* black). Registered as `emb` and added to
`ENABLED_SIGNALS`.

Three problems found and fixed while building, each pinned by a test:
- **OpenCV 5's MSER silently returns nothing for 1-channel input** (D-025) — the natural
  grayscale conversion would have disabled the source with no error.
- **MSER answers with one blob per letter**, useless to an embedding; `group_boxes` glues them
  into whole marks.
- **`propose` re-ran OCR**, the most expensive stage, doubling scan cost. `read_text` is now
  memoised on a content hash (D-026): 4.13 s cold, 0.004 s warm.
- **`calibrate.search` would have needed ~1 GB** for its index at three signals; the index is now
  arithmetic (D-027). Full 9.26 M-combination search: ~12 s, ~110 MB.

Measured cost of the new stage: **0.33 s/image** steady-state (0.19 s proposals, 0.65 s for 24
crops embedded in one batch on first call, then cached warm-up amortised).


**2026-09-08 - step 5-6: recalibrated, gate PASSED, then the labels turned out to be wrong.**
First calibration on the 100/158 set: catch-recall 0.970, precision 0.826, review 9.7% - gate
PASSED. The user then confirmed that `ZPE-Systems-Frank-Basso.webp` and `fgJCL84Y.jpg` carry no
logo at all (D-028). Both moved to `data/labeled/negative/`; the set is now 98/160 and everything
was recalibrated and re-benchmarked on it.

Final: **precision 0.873, catch-recall 0.980, review 8.9%, 0.45 img/s, GATE PASSED** (D-029).
Removing the two mislabeled images improved all three metrics at once - they were noise, not
difficulty. The stricter thresholds this allowed (emb 0.85/0.95 rather than 0.80/0.90) cost
`Untitled-1-1-1.png`, which the looser point had caught: the objective takes precision once
catch-recall clears 0.97.

phase05 was necessary regardless of the label fix - phase04's detector re-scored on the corrected
labels reaches only 0.959. **phase06 skipped** and moved to `plans/done/`.

## Completion Report

**Done 2026-09-08. The gate PASSED and phase06 is skipped.**

### Outcome
On the corrected labeled set (98 positive / 160 negative): precision **0.873**, catch-recall
**0.980**, review share **8.9%**, 0.45 img/s. Both gate targets met with no relaxation
(`feasible: true`); the attainable recall ceiling moved from 0.940 to **1.0**. Thresholds:
emb 0.85/0.95, ocr 0.75/0.85, sift 0.45/0.45 (D-029).

### Acceptance criteria
- [x] `pytest` green - 208 fast + 4 `slow` = **212 passed**.
- [x] Recalibrated metrics in BENCHMARKS; gate re-verdict in STATUS.
- [x] Throughput measured: the embedding stage costs **~0.33 s/image** steady-state; the full
      three-signal pipeline runs at **0.45 img/s** (emb alone 1.42, ocr 0.78, sift 4.14).

### What was built
`proposals.py` (OCR line boxes / caller-supplied boxes / MSER blobs grouped into whole marks /
always-kept tile grid + full frame, padded, area-filtered, IoU-merged, budget-capped) and
`embeddings.py` (frozen DINOv2-small on CPU, crops embedded in one batch, max cosine against every
`logo/` variant composited on both white and black). Registered as `emb`, added to
`ENABLED_SIGNALS`. Dependencies `torch 2.14.0+cpu` + `timm 1.0.29`, user-approved, verified to run
fully offline afterwards.

### What was learned (the useful part)
1. **Two "hard positives" were mislabeled** (D-028). `ZPE-Systems-Frank-Basso.webp` and
   `fgJCL84Y.jpg` carry no logo; they had been used to justify this whole phase. Removing them
   improved precision, recall *and* review share simultaneously, because mislabeled positives are
   noise that drags every threshold down - not difficulty. **A signal that scores 0 on every
   detector deserves a label check before it gets a new detector.** The agent cannot do that check
   itself (hard rule 4), so it must be asked of the user, and asked early.
2. **The phase was still necessary.** Phase04's detector re-scored on the corrected labels reaches
   only 0.959. The embedding signal cleared the gate, not the relabeling.
3. **Cheap levers first paid off as process, even though it found nothing.** The symbol-only logo
   variant was ruled out in one 17-minute run before 2 GB of PyTorch was installed.
4. **Silent library failures are the expensive kind.** OpenCV 5's MSER returns an empty result for
   single-channel input rather than raising (D-025); the natural grayscale conversion would have
   disabled a whole proposal source with no error anywhere. Pinned by a test.
5. **Sharing expensive work across signals matters more than optimising any one of them.** Region
   proposals wanted OCR boxes, which would have doubled scan cost; a content-hash memo on
   `read_text` (D-026) turned a 4.13 s repeat into 0.004 s.

### Cost carried forward
- Recall was bought for ~1 point of precision (0.882 -> 0.873) and ~2 points of review pile
  (7.0% -> 8.9%), measured against phase04 on the same corrected labels.
- The stricter thresholds cost `Untitled-1-1-1.png`, which the looser calibration caught. The
  `emb` pair is the dial if that image matters more than the false positives strictness avoids.
- `torch` + `timm` are ~2 GB on disk and the model needs an ~85 MB one-off download.

### Follow-ups (not blocking phase07)
- `Screen-Shot-2020-09-23-at-8.33.59-PM.jpg` remains the one detector failure with no easy answer.
- Whether "Nodegrid" counts as company branding is still an open scope question (ruled out here).

