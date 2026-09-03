# Changelog

> Newest first. One dated block per working session that changed the repo.

## 2026-09-03 - phase01
- Environment: `.venv` + `requirements.txt` (opencv-python, numpy, rapidfuzz, tqdm, pytest); exact versions in SETUP.
- Package `logoscanner/`: `__init__`, `__main__`, `cli` (subcommands `scan`, `version`), `config` (tunables + band mapping), `io_utils` (safe walk + load), `results` (ResultRow, CSV/JSON writers).
- `scan` v0: walks a folder, loads every image, writes `results.csv` + `summary.json`, prints throughput and ETA for 10,000 images. No detection yet - every image is scored 0.0 / negative.
- Tools: `make_dummy_logo.py` (committable fake mark), `make_synthetic.py` (synthetic labeled set), `check_dataset.py` (dataset stats).
- Tests: 23 tests over walker, loader, schema round-trip, synthetic generator, and end-to-end scan.
- Docs: SETUP filled in for real, CODEMAP populated, ARCHITECTURE current state updated, D-007/D-008 added.
- Measured baseline (no detection): 42 img/s on 800x600 PNGs -> ~4 min for 10k. All later budget is detection cost.

## 2026-09-03 - phase00
- Bootstrap: directory structure, CLAUDE.md, docs system, plan system with 8 phase files.
