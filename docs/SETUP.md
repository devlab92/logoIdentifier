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

## Embedding signal dependencies (phase05)
`torch` (CPU) + `timm` add roughly **2 GB** on disk (D-024). On Windows the PyPI wheel is already
CPU-only; elsewhere pin the CPU index explicitly:
```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install timm
```
The DINOv2 checkpoint (~85 MB) is fetched from the HuggingFace hub the **first** time the `emb`
signal runs and cached in `%USERPROFILE%\.cache\huggingface`; every run after that is offline.
That first load takes ~110 s including the download, ~2 s afterwards. Verified offline: with
`$env:HF_HUB_OFFLINE=1` the model still loads from the cache, so set that variable on an
air-gapped machine to stop `timm` reaching for the hub at all. Without torch, without the
checkpoint or with an empty `logo/`, the signal warns once and scores 0 - scans still run on OCR
and SIFT.

## Installed versions (phase05, `pip freeze`)
```
huggingface_hub==1.30.0
numpy==2.5.2
opencv-python==5.0.0.93
pillow==12.3.0
pytest==9.1.1
RapidFuzz==3.14.6
rapidocr-onnxruntime==1.4.4
safetensors==0.8.0
timm==1.0.29
torch==2.14.0+cpu
torchvision==0.29.0
tqdm==4.70.0
```

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
| `pytest -m "not slow"` | fast suite: skips the tests that need the DINOv2 checkpoint | phase05 |
| `python -m logoscanner version` | print version | phase01 |
| `python -m logoscanner scan --input input --output output [--limit N] [--no-progress] [--signals ocr,sift]` | scan a folder recursively, run the enabled signals, write `results.csv` + `summary.json`, print throughput + ETA for 10k | phase01, OCR since phase02, SIFT since phase03 |
| `python tools\make_dummy_logo.py` | (re)generate `tests/assets/dummy_logo.png` fake mark | phase01 |
| `python tools\make_synthetic.py --out .tmp_synth --count 50 [--positive-ratio 0.5] [--seed 1] [--with-text [RATIO]]` | generate a synthetic labeled set; `--with-text` also renders the brand name into that share of the positives (bare flag = 0.6) so OCR is testable without company images | phase01, `--with-text` phase02 |
| `python tools\check_dataset.py [--root data/labeled]` | counts + size stats for the labeled dataset | phase01 |
| `python tools\wp_collect.py [--dry-run] [--dedupe] [--source DIR] [--dest DIR] [--years 2014-2026]` | collect one original per image from a WordPress `uploads/` tree into `input\wp_originals\<YYYY-MM>\<original name>` + a manifest CSV | side tool |
| `python -m logoscanner benchmark --labeled data/labeled [--signals ocr,sift] [--limit N] [--no-progress] [--no-record] [--note "..."]` | score every signal over `positive/` + `negative/`, sweep the (review, positive) threshold grid, print the table and append a row to `docs/BENCHMARKS.md` (`--no-record` skips the row); several signals also get a combined naive-OR row | phase02, combined row phase03 |
| `python -m logoscanner calibrate --labeled data/labeled [--signals ocr,sift,emb] [--limit N] [--no-progress] [--no-apply]` | score the labeled set once, grid-search each signal's `(weak, strong)` thresholds, print the metrics + gate verdict, write `output/calibration.json`, rewrite the calibrated block in `logoscanner/config.py` (`--no-apply` skips that) and, when the gate fails, write `output/gate_failures.txt` | phase04 |

## Smoke test (phase04 verify)
```powershell
python -m logoscanner calibrate --labeled data\labeled
python -m logoscanner benchmark --labeled data\labeled --signals ocr,sift
pytest -q
```
`calibrate` edits `logoscanner/config.py` in place, between the
`# --- calibrated thresholds` markers - keep them when hand-editing that file, and re-run
`calibrate` after any change to a signal's scoring.

## Smoke test (phase03, no company data needed)
```powershell
python tools\make_dummy_logo.py
python tools\make_synthetic.py --out .tmp_synth --count 50 --with-text
python -m logoscanner scan --input .tmp_synth --output .tmp_out
pytest -q
```
The SIFT signal reads the logo variants in `logo/` (local-only, gitignored). With that folder
empty it warns once and scores 0 - the scan still runs on OCR alone.
`.tmp_*` folders are gitignored scratch; delete them freely.

## Outputs
- `output\results.csv` — one row per image: `filename, contains_logo, band, confidence, x, y, w, h, method, error`.
- `output\summary.json` — per-band totals, error count, seconds, img/s, ETA for 10,000 images.
- `output\calibration.json` — what `calibrate` chose: thresholds, metrics, confusion counts, the misses by name, and the gate verdict.
- `output\gate_failures.txt` — written only when the gate fails: one line per positive the signals missed, with a reason.
