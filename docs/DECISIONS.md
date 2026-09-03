# Decisions (ADR-lite)

> Numbered, append-only. Format: context → decision → consequences.

## D-001 — Baseline = OCR + SIFT before any ML (bootstrap)
Logo contains text + symbol. OCR catches the text; SIFT + RANSAC catches the symbol with geometric verification. Both are CPU-cheap, dependency-light, and explainable. ML phases (embeddings, detector) are gated behind measured failure of this baseline.

## D-002 — RapidOCR over PaddleOCR/EasyOCR (bootstrap)
RapidOCR runs Paddle's models on ONNX Runtime: Apache-2.0, painless Windows install, no Paddle framework dependency. Swap only with a new DECISIONS entry.

## D-003 — Rule-based OR decision, not weighted average (bootstrap)
A weighted average can drown a single conclusive signal (e.g., OCR reads the brand at 0.95 while SIFT is silent) and cause false negatives. OR rules with per-signal thresholds + a review band protect recall.

## D-004 — No FAISS, no vector DB (bootstrap)
We compare against ≤ ~20 logo-variant vectors; NumPy cosine is microseconds. FAISS adds a dependency with zero benefit at this scale.

## D-005 — CPU-first; no OpenVINO/NPU by default (bootstrap)
10k images × even 0.5 img/s ≈ 6 h — one overnight run. Runtime optimization only if measured ETA > ~12 h; first lever is `multiprocessing`, not GPU runtimes.

## D-006 — Ultralytics (AGPL-3.0) only in conditional phase06 (bootstrap)
Fine for internal use. If phase06 ships in the public repo, resolve AGPL implications here before publishing (options: keep detector optional/plugin, comply with AGPL, or choose an alternative detector).

## D-007 - Dependency set frozen at 5 packages (phase01)
`opencv-python` (decode, resize, geometry - also the SIFT backend in phase03), `numpy`,
`rapidfuzz` (fuzzy brand-term matching in phase02), `tqdm` (progress on 10k-image runs),
`pytest`. CSV/JSON reporting uses the stdlib, not pandas: we stream rows once and never
query them, so pandas would be weight without use. Each further dependency needs its own
entry here.

## D-008 - `np.fromfile` + `cv2.imdecode` instead of `cv2.imread` (phase01)
`cv2.imread`/`imwrite` silently fail on non-ASCII paths on Windows, and the real input
lives under a OneDrive path with accented folder names. Decoding from a byte buffer works
everywhere and gives a clean place to turn failures into a recorded `error` string rather
than an exception. Applies to every read and write of an image file in this repo.

## D-009 - Results filename is relative to the scan root (phase01)
`results.csv` stores `positive\pos_0001.png`, not an absolute path: reports stay readable,
portable between machines, and never leak the operator's directory layout.

