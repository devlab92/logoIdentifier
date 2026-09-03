# Setup & Commands

> Windows/PowerShell first. Populated for real in phase01; keep current afterwards.

## Environment (phase01 will finalize)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Commands (canonical list — extend as they are created)
| Command | What it does | Since |
|---|---|---|
| `pytest` | run test suite | phase01 |
| `python -m logoscanner scan --input input --output output` | scan a folder | phase01 (skeleton) |
| `python -m logoscanner benchmark --labeled data/labeled` | metrics on labeled set | phase02 |
| `python -m logoscanner calibrate --labeled data/labeled` | tune thresholds | phase04 |
