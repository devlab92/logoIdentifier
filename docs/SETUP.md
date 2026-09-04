# Setup & Commands

> Windows/PowerShell first. Keep current as commands are added.

## Requirements
- Python 3.12 (developed on 3.12.10), 64-bit.
- No GPU, no network at runtime. Everything below runs offline once installed.

## Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks activation: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

## Installed versions (phase02, `pip freeze`)
```
numpy==2.5.2
opencv-python==5.0.0.93
pytest==9.1.1
RapidFuzz==3.14.6
rapidocr-onnxruntime==1.4.4
tqdm==4.70.0
```
Transitive: colorama 0.4.6, flatbuffers 25.12.19, iniconfig 2.3.0, onnxruntime 1.29.0,
packaging 26.3, pillow 12.3.0, pluggy 1.6.0, protobuf 7.36.1, pyclipper 1.4.0,
Pygments 2.21.0, PyYAML 6.0.3, shapely 2.1.2, six 1.17.0.

`rapidocr-onnxruntime` bundles its three ONNX models inside the wheel
(`.venv/Lib/site-packages/rapidocr_onnxruntime/models/`, ~16 MB), so the first OCR run
needs no network. Engine start-up costs ~2 s once per process.

## Commands (canonical list — extend as they are created)
| Command | What it does | Since |
|---|---|---|
| `pytest` | run test suite | phase01 |
| `python -m logoscanner version` | print version | phase01 |
| `python -m logoscanner scan --input input --output output [--limit N] [--no-progress] [--signals ocr]` | scan a folder recursively, run the enabled signals, write `results.csv` + `summary.json`, print throughput + ETA for 10k | phase01, detection since phase02 |
| `python tools\make_dummy_logo.py` | (re)generate `tests/assets/dummy_logo.png` fake mark | phase01 |
| `python tools\make_synthetic.py --out .tmp_synth --count 50 [--positive-ratio 0.5] [--seed 1] [--with-text [RATIO]]` | generate a synthetic labeled set; `--with-text` also renders the brand name into that share of the positives (bare flag = 0.6) so OCR is testable without company images | phase01, `--with-text` phase02 |
| `python tools\check_dataset.py [--root data/labeled]` | counts + size stats for the labeled dataset | phase01 |
| `python tools\wp_collect.py [--dry-run] [--dedupe] [--source DIR] [--dest DIR] [--years 2014-2026]` | collect one original per image from a WordPress `uploads/` tree into `input\wp_originals\<YYYY-MM>\<original name>` + a manifest CSV | side tool |
| `python -m logoscanner benchmark --labeled data/labeled [--signals ocr] [--limit N] [--no-progress] [--no-record] [--note "..."]` | score every signal over `positive/` + `negative/`, sweep the (review, positive) threshold grid, print the table and append a row to `docs/BENCHMARKS.md` (`--no-record` skips the row) | phase02 |
| `python -m logoscanner calibrate --labeled data/labeled` | tune thresholds | phase04 |

## Smoke test (phase02 verify)
```powershell
python tools\make_dummy_logo.py
python tools\make_synthetic.py --out .tmp_synth --count 50 --with-text
python -m logoscanner scan --input .tmp_synth --output .tmp_out
python -m logoscanner benchmark --labeled data\labeled --signals ocr
pytest -q
```
`.tmp_*` folders are gitignored scratch; delete them freely.

## Outputs
- `output\results.csv` — one row per image: `filename, contains_logo, band, confidence, x, y, w, h, method, error`.
- `output\summary.json` — per-band totals, error count, seconds, img/s, ETA for 10,000 images.
