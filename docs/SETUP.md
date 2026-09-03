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

## Installed versions (phase01, `pip freeze`)
```
numpy==2.5.2
opencv-python==5.0.0.93
pytest==9.1.1
RapidFuzz==3.14.6
tqdm==4.70.0
```
Transitive: colorama 0.4.6, iniconfig 2.3.0, packaging 26.3, pluggy 1.6.0, Pygments 2.21.0.

## Commands (canonical list — extend as they are created)
| Command | What it does | Since |
|---|---|---|
| `pytest` | run test suite | phase01 |
| `python -m logoscanner version` | print version | phase01 |
| `python -m logoscanner scan --input input --output output [--limit N] [--no-progress]` | scan a folder recursively, write `results.csv` + `summary.json`, print throughput + ETA for 10k | phase01 (skeleton, no detection) |
| `python tools\make_dummy_logo.py` | (re)generate `tests/assets/dummy_logo.png` fake mark | phase01 |
| `python tools\make_synthetic.py --out .tmp_synth --count 50 [--positive-ratio 0.5] [--seed 1]` | generate a synthetic labeled set | phase01 |
| `python tools\check_dataset.py [--root data/labeled]` | counts + size stats for the labeled dataset | phase01 |
| `python -m logoscanner benchmark --labeled data/labeled` | metrics on labeled set | phase02 |
| `python -m logoscanner calibrate --labeled data/labeled` | tune thresholds | phase04 |

## Smoke test (phase01 verify)
```powershell
python tools\make_dummy_logo.py
python tools\make_synthetic.py --out .tmp_synth --count 50
python -m logoscanner scan --input .tmp_synth --output .tmp_out
pytest -q
```
`.tmp_*` folders are gitignored scratch; delete them freely.

## Outputs
- `output\results.csv` — one row per image: `filename, contains_logo, band, confidence, x, y, w, h, method, error`.
- `output\summary.json` — per-band totals, error count, seconds, img/s, ETA for 10,000 images.
