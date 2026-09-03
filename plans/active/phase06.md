# phase06 — Fine-tuned Nano Detector (CONDITIONAL, last resort)

**Goal:** train a one-class nano object detector on the company's own annotated images to close the remaining recall gap.
**Depends on:** phase05
**Conditional?** **Only if the gate still FAILED after phase05.**

## Context to load
- `plans/STATUS.md`, `output/gate_failures.txt`, `docs/DECISIONS.md` (D-006), `logoscanner/{config,signals,pipeline}.py`

## User prerequisites (hard, human labor)
- Bounding-box annotations on the ~100–300 positive images: use a free tool (makesense.ai runs in-browser/offline, or Label Studio locally), single class `logo`, export in YOLO format into `data/annotations/`.
- Decide training venue: local CPU (overnight, fully private) or free Colab (faster, but images leave the machine — **explicit user opt-in required**; default is local).

## Steps
1. `tools/prep_dataset.py` — assemble YOLO dataset structure (train/val split 80/20, negatives included as background images) from `data/labeled` + `data/annotations`; validate label files.
2. Add `ultralytics` to requirements **for training only** → DECISIONS entry re-confirming D-006 (AGPL) and the plan for public release.
3. `tools/train_detector.py` — fine-tune the current Ultralytics nano detection model, imgsz 960, sensible small-dataset augmentation; export best weights to ONNX → `models/logo_nano.onnx`.
4. `logoscanner/detector.py` — `DetectorSignal` running the ONNX model via `onnxruntime` (keeps the runtime dependency light; ultralytics needed only to train). Score = top detection confidence; bbox from detection.
5. Register; recalibrate with detector thresholds; benchmark; **final gate check** — if still failing, stop and present options to the user (more annotations / accept larger review band / revisit targets) instead of piling on complexity.
6. Tests: ONNX inference smoke on a synthetic image (skip if `models/` absent); dataset prep validation.
7. Docs: ARCHITECTURE, CODEMAP, CHANGELOG, DECISIONS (training config + license resolution), BENCHMARKS.

## Acceptance criteria
- [ ] Dataset prep validated; training completed; `models/logo_nano.onnx` exists (gitignored).
- [ ] Detector signal integrated; recalibrated metrics in BENCHMARKS; gate verdict in STATUS.
- [ ] AGPL resolution recorded before phaseFinal.

## Verify
```powershell
python tools\prep_dataset.py --check
python -m logoscanner benchmark --labeled data\labeled --signals ocr,sift,emb,det
pytest -q -m "not slow"
```

## Progress Log

## Completion Report
