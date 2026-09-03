# LogoScanner — Project Bootstrap & Master Plan

> **If you are an AI assistant (Claude Code) reading this file:** this document is your complete set of instructions. Read it fully, then execute **Section 7 (Bootstrap Execution)** immediately. After the bootstrap, this file becomes historical reference — everything future sessions need will live in `CLAUDE.md`, `docs/` and `plans/`.
>
> **If you are a human:** drop this file into an empty folder opened in Claude Code and say: *"Read BOOTSTRAP.md and execute it."* When it finishes, open a **new conversation** and say *"Start phase01"*. Repeat per phase.

---

## 1. Mission

Build **LogoScanner**: a free, local, offline CLI tool that scans a folder with ~10,000 heterogeneous images (photos, charts, screenshots, documents, real-world scenes) and reports **which images contain the company logo**, producing:

- `results.csv` — `filename, contains_logo, band, confidence, x, y, width, height, method`
- `results.json` — summary + per-file records
- `output/detected/` and `output/review/` — copies of positive and uncertain images
- `output/crops/` — cropped logo regions for fast human verification

The logo contains **text + a symbol**, and appears in many variants (light/dark, small/large, partial, over complex backgrounds).

### Non-negotiable constraints

1. **Free & local.** No paid APIs, no cloud processing, no images ever leave the machine.
2. **Windows host.** Dell Precision 3590 — Intel Core Ultra 7 165H, 32 GB RAM, Intel Arc iGPU. CPU-first; GPU/NPU/OpenVINO only if a measured need appears (a one-night CPU run for 10k images is acceptable).
3. **Simple.** No MCP servers, no multi-agent setups, no Docker, no microservices, no vector databases. Prefer stdlib over dependencies. Every new dependency must be justified in `docs/DECISIONS.md`.
4. **Recall first.** Losing an image that contains the logo is the worst failure. False positives go to a human-review band instead.
5. **Measure before complicating.** ML-heavy phases (05, 06) are **conditional** — they only run if the simple baseline fails a measurable quality gate (defined in phase04).
6. **English everywhere.** Code, comments, docs, commits — all English. The repository will be published publicly on GitHub.

### Target quality gate (tunable in `logoscanner/config.py`)

- **Catch-recall ≥ 0.97** — of the truly-positive images, ≥ 97% must land in the `positive` or `review` band (i.e., not silently lost).
- **Precision ≥ 0.90** on the `positive` band.
- **Review band ≤ 10%** of all images.

---

## 2. How this project is operated (human + AI workflow)

The human works in short sessions. Each implementation phase is executed in a **fresh conversation** to keep context small. The repository itself — not the chat history — is the project's memory. Therefore:

- `CLAUDE.md` (auto-loaded by Claude Code every session) is a **short index**, not a manual.
- `docs/` is the knowledge base. It must always reflect reality.
- `plans/` holds the phase files: `plans/active/` (not yet done) and `plans/done/` (finished, with completion reports).
- A phase is **not finished** until its documentation updates are made and its plan file is moved to `plans/done/`.

### Session protocols (these also get embedded in CLAUDE.md)

**A. "Start phaseXX"**
1. `CLAUDE.md` is already in context (Claude Code loads it automatically).
2. Read `plans/STATUS.md`.
3. Read `plans/active/phaseXX.md`.
4. Read **only** the files listed in that phase's *Context to load* section. Nothing else.
5. Post a 3–6 bullet execution summary to the user, then execute the steps in order.
6. Append short entries to the phase's *Progress Log* as milestones complete (this enables resuming in a later conversation).
7. Finish with the **Definition of Done** (Section 4).

**B. "Continue phaseXX"** — same as A, but read the phase's *Progress Log* first and resume from the last entry.

**C. Ad-hoc request ("fix X", "change Y")**
1. Consult `docs/CODEMAP.md` to locate the relevant file(s).
2. Read only those files (targeted line ranges when possible).
3. Make the change, run the tests, update `docs/CODEMAP.md` + `docs/CHANGELOG.md` in the same session.

**D. "Add a new phase"** — copy `plans/TEMPLATE_PHASE.md`, fill it, save to `plans/active/`, register it in `plans/STATUS.md`.

### Question policy

If genuinely blocked or facing an ambiguous decision with real consequences, ask the user **one focused question**. Otherwise, decide, record the reasoning in `docs/DECISIONS.md`, and proceed.

---

## 3. Token-economy rules (mandatory, every session)

These rules exist so the AI can work on this repo without ever loading it whole:

1. **Never scan or grep the entire repository.** `docs/CODEMAP.md` tells you what every file does and when to touch it — start there.
2. **Never read binary or bulk folders:** `input/`, `output/`, `models/`, `logo/`, `data/` (images, weights). Reference them by path only.
3. **Never re-read a file you are not about to modify** if its CODEMAP entry answers the question.
4. Prefer **targeted reads** (specific files, line ranges) over whole-file reads.
5. **Phase files whitelist their own context.** During a phase, do not read outside its *Context to load* list unless a step explicitly requires it.
6. Keep responses lean: no restating file contents back to the user, no long recaps.
7. When a doc answers a question, **cite the doc path** instead of re-deriving the answer from source code.

---

## 4. Documentation system

### Files

| File | Purpose | Updated when |
|---|---|---|
| `CLAUDE.md` | Short AI index: protocols, hard rules, repo map | Only if workflow itself changes |
| `docs/ARCHITECTURE.md` | How the pipeline works end-to-end (signals, decision bands, data flow) | Any behavioral/architectural change |
| `docs/CODEMAP.md` | One entry per source file: purpose, key functions, dependencies, "when to modify" | **Every** file created/renamed/significantly changed |
| `docs/DECISIONS.md` | ADR-lite log: numbered decisions with context and consequences | Every non-obvious choice (dependency, algorithm, threshold policy, license) |
| `docs/CHANGELOG.md` | Dated log of what changed | Every working session that changes the repo |
| `docs/SETUP.md` | Environment setup, all CLI commands, test commands (Windows/PowerShell first) | When commands/env change |
| `docs/BENCHMARKS.md` | Metrics history table (append-only) | Every benchmark/calibration run |
| `docs/USER_GUIDE.md` | End-user manual for non-developers | Written in phaseFinal, then on UX changes |

### The rule of rules

> **Any creation or modification of code or behavior must update the relevant doc(s) in the same session.** If something new doesn't fit an existing doc, create a new doc under `docs/` and register it in `CLAUDE.md`'s repo map. Undocumented work is unfinished work.

### Definition of Done for a phase (checklist)

- [ ] All acceptance criteria in the phase file are checked off.
- [ ] `pytest` is green and the phase's *Verify* command was run, with output shown to the user.
- [ ] `docs/CODEMAP.md` and `docs/CHANGELOG.md` updated (plus `DECISIONS.md` / `ARCHITECTURE.md` / `BENCHMARKS.md` if applicable).
- [ ] A *Completion Report* (what was done, deviations, metrics, follow-ups) is appended to the phase file.
- [ ] Phase file moved from `plans/active/` to `plans/done/`.
- [ ] `plans/STATUS.md` updated (history row + next phase + user homework).
- [ ] Git commit: `phaseXX: <one-line summary>`. Attempt `git push`; if auth fails, tell the user to push manually.

---

## 5. Directory structure (created at bootstrap)

```text
logoscanner/                     # repo root
├── CLAUDE.md                    # AI index (auto-loaded by Claude Code)
├── README.md                    # public-facing (skeleton now, polished in phaseFinal)
├── BOOTSTRAP.md                 # this file (moved to plans/done/ after bootstrap)
├── .gitignore
├── requirements.txt             # populated in phase01
├── logoscanner/                 # Python package (created in phase01)
├── tools/                       # helper scripts (synthetic data, dataset checks)
├── tests/
│   └── assets/                  # tiny fake assets safe for a public repo
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CODEMAP.md
│   ├── DECISIONS.md
│   ├── CHANGELOG.md
│   ├── SETUP.md
│   └── BENCHMARKS.md
├── plans/
│   ├── STATUS.md
│   ├── TEMPLATE_PHASE.md
│   ├── active/                  # phase01 ... phaseFinal live here until done
│   └── done/
├── logo/                        # REAL logo variants (gitignored; user adds)
├── data/
│   └── labeled/
│       ├── positive/            # user drags real images WITH the logo here
│       └── negative/            # user drags real images WITHOUT the logo here
├── input/                       # the 10k images (gitignored)
├── output/                      # results (gitignored)
└── models/                      # downloaded/trained weights (gitignored)
```

**Privacy note:** `logo/`, `data/`, `input/`, `output/`, `models/` are gitignored. The public repo ships only code, docs, and fake test assets. Automated tests use a **generated dummy logo** (`tests/assets/`), never the real one.

---

## 6. Technical strategy (summary — details live in each phase file)

Two cheap, complementary signals first; ML only if the gate fails:

```text
image ──► OCR signal   (brand text via RapidOCR + fuzzy match)  ─┐
      ──► SIFT signal  (keypoints + RANSAC geometric check)     ─┤► decision engine ──► positive / review / negative
      ──► [phase05, conditional] region proposals + embeddings  ─┤
      ──► [phase06, conditional] fine-tuned nano detector       ─┘
```

- **Decision engine is rule-based (OR logic), not a weighted average** — one strong signal is enough for positive; a lone medium signal sends to review. This protects recall.
- Thresholds are **calibrated on the labeled set** (phase04), never hardcoded by intuition.
- **No FAISS** (comparing against ≤ ~20 logo-variant vectors is a NumPy dot product). **No OpenVINO/NPU** unless the measured ETA for 10k images exceeds ~12 h.
- OCR engine: **RapidOCR (ONNX Runtime)** — Apache-2.0, trivial Windows install (fallback: PaddleOCR/EasyOCR, record in DECISIONS if swapped).
- Phase06 uses Ultralytics (**AGPL-3.0**) — fine for internal use; if it ends up in the public release, the license implications must be recorded and resolved in `docs/DECISIONS.md` before publishing.

Phases: **01** foundation+data · **02** OCR · **03** SIFT · **04** decision+calibration → **GATE** · **05** embeddings *(conditional)* · **06** detector *(conditional)* · **07** production run · **Final** docs+release.

---

## 7. Bootstrap Execution — DO THIS NOW (Phase 00)

Execute these steps in order. Do not skip the self-check.

1. **Git:** if the folder is not a git repo, run `git init` (default branch `main`).
2. **Create the directory tree** from Section 5 (empty dirs get a `.gitkeep`).
3. **Create the root files** exactly as specified in Section 8: `CLAUDE.md`, `.gitignore`, `README.md`.
4. **Create the docs** from the templates in Section 9.
5. **Create the plan system:** `plans/STATUS.md` and `plans/TEMPLATE_PHASE.md` from Section 9; then create every phase file in `plans/active/` by copying each block in Section 10 **verbatim** into its own file (`phase01.md` … `phase07.md`, `phaseFinal.md`).
6. **Move this file** (`BOOTSTRAP.md`) to `plans/done/phase00-bootstrap.md`.
7. **Self-check:** print the resulting tree (2 levels); confirm every file from steps 3–5 exists and is non-empty; confirm `plans/active/` has exactly 8 phase files.
8. **Commit:** `git add -A && git commit -m "phase00: bootstrap scaffold (structure, docs, plans)"`.
9. **Hand off** with exactly this message to the user:

> Bootstrap complete. Next steps for you:
> 1. Create an empty repository on GitHub and connect it (`git remote add origin <url>` + `git push -u origin main`).
> 2. Put your real logo variants into `logo/` (PNG, ideally transparent background; include light/dark/symbol-only versions).
> 3. Open `logoscanner/config.py` after phase01 and set your real `BRAND_TERMS`.
> 4. Open a **new conversation** and say: **"Start phase01"**.

---

## 8. Root files (create verbatim)

### 8.1 — `CLAUDE.md`

----- BEGIN FILE: CLAUDE.md -----
# LogoScanner — AI Context (auto-loaded every session)

**One-liner:** free, local, offline CLI that scans a folder of images and reports which contain the company logo (text + symbol), with `positive / review / negative` confidence bands. Recall first; false positives go to review, never silently lost.

## Session start protocol
1. This file is an **index**. Do not explore the repo.
2. Read `plans/STATUS.md` (current phase, blockers, user homework).
3. `"Start phaseXX"` → read `plans/active/phaseXX.md`, then **only** the files in its *Context to load*. Execute its steps; log milestones in its *Progress Log*.
4. `"Continue phaseXX"` → same, but read the *Progress Log* first and resume.
5. Any other request → find the file via `docs/CODEMAP.md`; read only what you'll touch.

## Repo map
- `logoscanner/` — source package. File-by-file guide: `docs/CODEMAP.md` (always current).
- `docs/` — ARCHITECTURE (how it works) · CODEMAP (what each file does) · DECISIONS (why) · CHANGELOG (what/when) · SETUP (env + commands) · BENCHMARKS (metrics history) · USER_GUIDE (end users, from phaseFinal).
- `plans/` — STATUS.md · TEMPLATE_PHASE.md · active/ · done/.
- `tools/`, `tests/` — helpers and pytest suite (fake assets only).
- `logo/`, `data/`, `input/`, `output/`, `models/` — local-only, gitignored. **Never read image/weight binaries.**

## Hard rules
1. **Token economy:** never scan the repo; never read `input/ output/ models/ logo/ data/`; targeted reads only; CODEMAP before code.
2. **Docs are the memory:** any created/changed file ⇒ update `docs/CODEMAP.md` + `docs/CHANGELOG.md` in the same session; non-obvious choices ⇒ `docs/DECISIONS.md`. Undocumented work is unfinished.
3. **Simplicity:** CPU-first; stdlib > deps; no MCP, agents, Docker, cloud, or paid APIs. New dependency ⇒ DECISIONS entry.
4. **Privacy:** company images and the real logo never leave the machine and are never committed. Tests use `tests/assets/` fakes.
5. **Recall first:** when tuning, protect catch-recall (positive ∪ review) before precision.
6. Blocked or truly ambiguous ⇒ ask the user **one** focused question; otherwise decide, record in DECISIONS, proceed.
7. Windows host (PowerShell). Use `pathlib`; keep commands cross-platform where possible.

## Phase Definition of Done
- [ ] Phase acceptance criteria all checked
- [ ] `pytest` green + phase *Verify* command run (show output)
- [ ] CODEMAP + CHANGELOG updated (+ DECISIONS / ARCHITECTURE / BENCHMARKS if touched)
- [ ] *Completion Report* appended to the phase file; file moved to `plans/done/`
- [ ] `plans/STATUS.md` updated
- [ ] Commit `phaseXX: <summary>`; try push, else tell user

## Commands
All environment/run/test commands: `docs/SETUP.md`.
----- END FILE -----

### 8.2 — `.gitignore`

----- BEGIN FILE: .gitignore -----
# Python
.venv/
venv/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/

# Private data — never commit company material
input/
output/
logo/
data/
models/

# Model weights anywhere
*.onnx
*.pt
*.pth

# OS / IDE
.DS_Store
Thumbs.db
.vscode/
.idea/
.claude/settings.local.json

# Keep folder placeholders
!**/.gitkeep
----- END FILE -----

### 8.3 — `README.md` (skeleton; polished in phaseFinal)

----- BEGIN FILE: README.md -----
# LogoScanner

Free, local, offline CLI that scans a large folder of images (photos, charts, screenshots, documents) and reports **which images contain a specific company logo** — with confidence bands and a human-review workflow.

**Status: under construction.** Built phase-by-phase by an AI pair-programming workflow; see `plans/` for the roadmap and `docs/` for architecture.

Quickstart, examples and full instructions will land here in the final phase. End-user manual: `docs/USER_GUIDE.md` (coming).
----- END FILE -----

---

## 9. Docs & plan-system templates (create verbatim)

### 9.1 — `docs/ARCHITECTURE.md`

----- BEGIN FILE: docs/ARCHITECTURE.md -----
# Architecture

> Keep this file matching reality. Update on any behavioral change.

## Current state
Bootstrap only — no source code yet. Target design below.

## Target pipeline
```text
image ──► OCR signal   (RapidOCR + fuzzy brand-term match)      ─┐
      ──► SIFT signal  (keypoints + Lowe ratio + RANSAC verify) ─┤► rule-based decision ──► positive / review / negative
      ──► [conditional] region proposals + embedding similarity ─┤        │
      ──► [conditional] fine-tuned nano detector                ─┘        ▼
                                                              results.csv/json, crops/, detected/, review/
```

## Key principles
- Decision engine uses **OR rules**, not weighted averages: one strong signal ⇒ positive; a lone medium signal ⇒ review. Protects recall.
- Thresholds come from **calibration on the labeled set**, never intuition. Bands: positive / review / negative.
- Signals are independent modules returning `SignalResult(score, bbox, method, detail)` so the decision layer stays pluggable.
- CPU-first. Performance work only if measured ETA for 10k images exceeds ~12 h (then: multiprocessing before any GPU runtime).

## Data flow & artifacts
`input/` → scanner walk → per-image signals → decision → incremental `output/results.csv` + `output/.progress.jsonl` (resume) → final `results.json` summary + `crops/`, `detected/`, `review/`.
----- END FILE -----

### 9.2 — `docs/CODEMAP.md`

----- BEGIN FILE: docs/CODEMAP.md -----
# Code Map

> One entry per source file. **Update in the same session as any change.** Keep alphabetical within each section. This file exists so the AI never has to scan the repo.

**Entry format:**
`path` — Purpose. | Key functions/classes. | Depends on. | When to modify.

## logoscanner/ (package)
*(empty — populated from phase01)*

## tools/
*(empty — populated from phase01)*

## tests/
*(empty — populated from phase01)*
----- END FILE -----

### 9.3 — `docs/DECISIONS.md`

----- BEGIN FILE: docs/DECISIONS.md -----
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
----- END FILE -----

### 9.4 — `docs/CHANGELOG.md`

----- BEGIN FILE: docs/CHANGELOG.md -----
# Changelog

> Newest first. One dated block per working session that changed the repo.

## <YYYY-MM-DD> — phase00
- Bootstrap: directory structure, CLAUDE.md, docs system, plan system with 8 phase files.
----- END FILE -----

### 9.5 — `docs/SETUP.md`

----- BEGIN FILE: docs/SETUP.md -----
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
----- END FILE -----

### 9.6 — `docs/BENCHMARKS.md`

----- BEGIN FILE: docs/BENCHMARKS.md -----
# Benchmarks (append-only)

> One row per run. `catch-recall` counts positives landing in positive ∪ review.

| Date | Phase | Dataset (P/N) | Signals | Precision(pos) | Catch-recall | Review % | imgs/s | Notes |
|---|---|---|---|---|---|---|---|---|
----- END FILE -----

### 9.7 — `plans/STATUS.md`

----- BEGIN FILE: plans/STATUS.md -----
# Project Status

**Current phase:** none (bootstrap done)
**Next phase:** phase01
**Gate state:** not evaluated (set in phase04: PASSED → skip 05–06; FAILED → run 05)

## User homework (blockers owned by the human)
- [ ] Create GitHub repo, add remote, push
- [ ] Add real logo variants to `logo/`
- [ ] After phase01: set `BRAND_TERMS` in `logoscanner/config.py`; label ~300 real images into `data/labeled/positive|negative/`

## History
| Phase | Status | Finished | Commit | Notes |
|---|---|---|---|---|
| phase00 bootstrap | done | <date> | <hash> | scaffold |
----- END FILE -----

### 9.8 — `plans/TEMPLATE_PHASE.md`

----- BEGIN FILE: plans/TEMPLATE_PHASE.md -----
# phaseXX — <Title>

**Goal:** <one sentence>
**Depends on:** <phase(s)>
**Conditional?** <no / only if gate FAILED>

## Context to load (whitelist — read nothing else)
- docs/... , logoscanner/...

## User prerequisites
- <what the human must have done before this phase>

## Steps
1. ...

## Deliverables
- `path` — purpose

## Acceptance criteria
- [ ] ...

## Verify
```powershell
<command(s) proving the phase works>
```

## Out of scope
- ...

## User homework after this phase
- ...

## Progress Log
*(AI appends dated one-liners as milestones complete)*

## Completion Report
*(filled at the end: what was done, deviations, metrics, follow-ups)*
----- END FILE -----
---

## 10. Phase files (copy each block verbatim into `plans/active/<name>.md`)

### 10.1 — `plans/active/phase01.md`

----- BEGIN FILE: plans/active/phase01.md -----
# phase01 — Foundation, CLI Skeleton & Dataset Protocol

**Goal:** working repo: environment, package skeleton, `scan` command that walks images and measures throughput (no detection yet), synthetic test-data generator, and the labeling protocol for the real dataset.
**Depends on:** phase00 (bootstrap)
**Conditional?** no

## Context to load
- `docs/SETUP.md`, `docs/CODEMAP.md`

## User prerequisites
- None. (Real logo files in `logo/` help but are not required yet.)

## Steps
1. Create `.venv`; write `requirements.txt`: `opencv-python`, `numpy`, `rapidfuzz`, `tqdm`, `pytest`. Install. Record exact versions in `docs/SETUP.md`.
2. Create the package:
   - `logoscanner/__init__.py` — version string.
   - `logoscanner/__main__.py` — delegates to `cli.main()`.
   - `logoscanner/cli.py` — `argparse` with subcommands `scan`, `version` (later phases add `benchmark`, `calibrate`). `scan --input <dir> --output <dir> [--limit N]`.
   - `logoscanner/config.py` — single source of tunables: `BRAND_TERMS = ["ACME", "ACME Systems"]  # TODO(user): set real terms`, `IMAGE_EXTS`, `MAX_SIDE = 1600`, placeholder thresholds (filled in later phases), band names `positive/review/negative`.
   - `logoscanner/io_utils.py` — `iter_images(root)` recursive walker filtered by `IMAGE_EXTS`; `load_image(path)` returning BGR array or a recorded error; never raises on a bad file.
   - `logoscanner/results.py` — `ResultRow` dataclass (`filename, contains_logo, band, confidence, x, y, w, h, method, error`); CSV writer (stdlib `csv`); JSON summary writer (totals per band, timing).
3. `scan` v0: walk → load → (no signals yet: every image `band=negative, confidence=0.0`) → write CSV+JSON → print throughput report: `images, seconds, imgs/s, ETA for 10,000`.
4. `tools/make_dummy_logo.py` — generates `tests/assets/dummy_logo.png`: fake mark = colored geometric symbol + the text `ACME` (safe for the public repo). Commit the PNG.
5. `tools/make_synthetic.py` — `--out <dir> --count N --positive-ratio 0.5`: composes images (solid/gradient/noise/random-shapes/random-text backgrounds); positives get the dummy logo pasted at random scale (0.3–1.5×), position, slight rotation (±10°), optional 60–100% opacity; writes into `<out>/positive/` and `<out>/negative/`. Used by tests and pre-real-data benchmarks.
6. `tools/check_dataset.py` — prints counts and size stats for `data/labeled/positive|negative`.
7. Tests (`tests/`): walker skips non-images and junk files; corrupt file yields recorded error, not a crash; CSV/JSON schema round-trip; synthetic generator produces the requested split. Use `tmp_path` + `tests/assets/` only.
8. Docs: fill `docs/SETUP.md` for real; add every new file to `docs/CODEMAP.md`; CHANGELOG entry; update ARCHITECTURE "Current state".

## Deliverables
- `requirements.txt`, `logoscanner/{__init__,__main__,cli,config,io_utils,results}.py`, `tools/{make_dummy_logo,make_synthetic,check_dataset}.py`, `tests/*`, `tests/assets/dummy_logo.png`, updated docs.

## Acceptance criteria
- [ ] `pytest` green.
- [ ] `scan` over 50 synthetic images produces valid CSV+JSON and prints the throughput report with ETA for 10k.
- [ ] Corrupt file in input does not crash the run and appears in the CSV `error` column.
- [ ] CODEMAP has one accurate entry per new file.

## Verify
```powershell
python tools\make_dummy_logo.py
python tools\make_synthetic.py --out .tmp_synth --count 50
python -m logoscanner scan --input .tmp_synth --output .tmp_out
pytest -q
```

## Out of scope
- Any detection logic; OCR; SIFT; performance tuning.

## User homework after this phase
- Set real `BRAND_TERMS` in `logoscanner/config.py`.
- Put real logo variants into `logo/` (light/dark/symbol-only, transparent PNG when possible).
- Label ~300 real images by dragging them into `data/labeled/positive/` and `data/labeled/negative/` (~100–150 positives). **Include the hard cases:** tiny logo, partial logo, logo over photos/charts/screenshots, dark & light variants, low resolution.

## Progress Log
*(AI appends dated one-liners as milestones complete)*

## Completion Report
*(filled at the end)*
----- END FILE -----

### 10.2 — `plans/active/phase02.md`

----- BEGIN FILE: plans/active/phase02.md -----
# phase02 — OCR Signal (brand text)

**Goal:** OCR-based signal that finds the brand name in images, plus a `benchmark` command measuring per-signal quality on a labeled set.
**Depends on:** phase01
**Conditional?** no

## Context to load
- `docs/CODEMAP.md`, `docs/ARCHITECTURE.md`, `logoscanner/config.py`, `logoscanner/results.py`, `logoscanner/cli.py`

## User prerequisites
- `BRAND_TERMS` set. Labeled real data helps; if absent, run benchmarks on synthetic and flag homework pending.

## Steps
1. Add `rapidocr-onnxruntime` (+ `onnxruntime`) to requirements; verify it runs fully offline after install (models ship with the package). DECISIONS already covers the choice (D-002).
2. `logoscanner/signals.py` — shared `SignalResult` dataclass (`name, score∈[0,1], bbox|None, detail`) and a signal registry the pipeline iterates (enabled list in `config.py`).
3. `logoscanner/ocr.py` — `OcrSignal`: lazy engine init (load once per process); run OCR; normalize text (casefold, collapse whitespace, strip punctuation); match each detected text against every `BRAND_TERMS` entry with `rapidfuzz.fuzz.partial_ratio`; guard against trivially short matches; `score = (fuzz/100) × ocr_confidence`; return best box.
4. `logoscanner/pipeline.py` — orchestrates enabled signals per image; `scan` now records the best signal (`method`, `confidence`, bbox) even though banding is provisional until phase04 (temporary rule: score ≥ 0.85 → positive, ≥ 0.60 → review).
5. Extend `tools/make_synthetic.py`: `--with-text` renders the first brand term into some positives (varied fonts/sizes) so OCR is testable synthetically.
6. `benchmark` subcommand: `--labeled <dir> --signals ocr[,sift,...]` → runs signals over `positive/`+`negative/`, sweeps a coarse threshold grid, prints best precision/catch-recall/review-share per signal, appends a row to `docs/BENCHMARKS.md`.
7. Tests: matcher variants (case, spacing, OCR-typo like `AC1VIE`→ACME tolerance boundaries); OCR smoke test on a synthetic text image; registry returns well-formed `SignalResult`s.
8. Docs: CODEMAP (new files + pipeline), ARCHITECTURE (pipeline now real), CHANGELOG, BENCHMARKS row.

## Acceptance criteria
- [ ] `pytest` green (OCR smoke included).
- [ ] `benchmark --signals ocr` runs on `data/labeled` (or synthetic fallback, flagged) and the row is in BENCHMARKS.
- [ ] `scan` output now contains real OCR scores/bboxes.

## Verify
```powershell
python -m logoscanner benchmark --labeled data\labeled --signals ocr
pytest -q
```

## Out of scope
- SIFT; final thresholds; calibration.

## User homework after this phase
- Finish labeling if not done — phase04 hard-requires it.

## Progress Log

## Completion Report
----- END FILE -----

### 10.3 — `plans/active/phase03.md`

----- BEGIN FILE: plans/active/phase03.md -----
# phase03 — SIFT Signal (symbol matching)

**Goal:** keypoint-matching signal that finds the logo symbol at any scale/rotation, with geometric verification for precision.
**Depends on:** phase02
**Conditional?** no

## Context to load
- `docs/CODEMAP.md`, `logoscanner/{config,signals,pipeline}.py`

## User prerequisites
- Real logo variants in `logo/` (tests fall back to `tests/assets/dummy_logo.png`; if `logo/` is empty at scan time, warn and skip the signal).

## Steps
1. `logoscanner/keypoints.py` — `SiftSignal`:
   - On init: load every image in `logo/` (grayscale; upscale tiny variants to ~300 px min side), compute SIFT descriptors once per variant.
   - Per image: downscale to `MAX_SIDE` (keep the scale factor), SIFT detect, `BFMatcher.knnMatch(k=2)`, Lowe ratio 0.75.
   - If good matches ≥ `SIFT_MIN_GOOD` (start 8): `cv2.findHomography(..., RANSAC)`; require inliers ≥ `SIFT_MIN_INLIERS` (start 8) **and** a sane projected box (convex, positive area, plausible size, inside image). Score `= min(1, inliers / SIFT_SCORE_NORM)` (start 25). Bbox = projected logo corners scaled back to original coordinates. Best across variants wins.
2. Config: `SIFT_MIN_GOOD`, `SIFT_MIN_INLIERS`, `SIFT_SCORE_NORM`, provisional strong/weak thresholds.
3. Register in the pipeline; `benchmark --signals sift` and `--signals ocr,sift` must work.
4. Tests (synthetic, dummy logo): pasted at 0.4×/1.0×/1.5× and ±10° → detected with valid bbox; pure-negative image → score ≈ 0; degenerate homography rejected.
5. Docs: CODEMAP, CHANGELOG, BENCHMARKS rows (sift alone; ocr+sift naive-OR).

## Acceptance criteria
- [ ] `pytest` green (multi-scale synthetic cases pass).
- [ ] BENCHMARKS has `sift` and `ocr,sift` rows on the labeled set (or flagged synthetic fallback).
- [ ] Missing `logo/` degrades gracefully (warning, signal skipped).

## Verify
```powershell
python -m logoscanner benchmark --labeled data\labeled --signals ocr,sift
pytest -q
```

## Out of scope
- Embeddings, detectors, threshold calibration.

## Progress Log

## Completion Report
----- END FILE -----

### 10.4 — `plans/active/phase04.md`

----- BEGIN FILE: plans/active/phase04.md -----
# phase04 — Decision Engine, Calibration & THE GATE

**Goal:** rule-based decision bands, thresholds calibrated on the real labeled set, and the go/no-go decision on ML phases.
**Depends on:** phase03
**Conditional?** no

## Context to load
- `docs/CODEMAP.md`, `docs/BENCHMARKS.md`, `logoscanner/{config,signals,pipeline}.py`

## User prerequisites (hard)
- `data/labeled/` populated with real images (~100+ positives, ~150+ negatives, hard cases included). If missing: stop and request it — synthetic data must NOT drive calibration.

## Steps
1. `logoscanner/decision.py` — `decide(results) -> (band, confidence, bbox, method)`:
   - any signal ≥ its **strong** threshold → `positive`
   - else any signal ≥ its **weak** threshold → `review`
   - else `negative`
   - `confidence` = best normalized score (document: monotonic, not a probability); `method` = winning signal(s).
2. `logoscanner/metrics.py` — from labeled dirs: precision(positive band), **catch-recall** (positives in positive ∪ review), review share, confusion counts, per-signal wins, and the list of false-negative filenames.
3. `calibrate` subcommand — grid-search the 4 thresholds (`ocr_strong/weak`, `sift_strong/weak`) on the labeled set. Objective: **maximize precision subject to catch-recall ≥ 0.97 and review share ≤ 10%**; tie-break by higher catch-recall, then lower review share. Write `output/calibration.json`, update the values in `config.py`, record chosen numbers + date in `docs/DECISIONS.md`.
4. Wire `decide()` into `scan`; remove the provisional phase02 rule.
5. **GATE evaluation** on the calibrated labeled-set metrics:
   - **PASSED** (targets met): record in `plans/STATUS.md` + DECISIONS; move `phase05.md` and `phase06.md` to `plans/done/` each with Completion Report = `SKIPPED — gate passed on <date>, metrics: ...`. Next phase = phase07.
   - **FAILED:** record which target failed; copy the false-negative files list to `output/gate_failures.txt` with a one-line reason each (tiny logo / stylized text / occlusion...). Next phase = phase05.
6. Tests: decision truth-table; metrics on a crafted mini-set with known answers.
7. Docs: ARCHITECTURE (bands + calibration flow), CODEMAP, CHANGELOG, BENCHMARKS (calibrated row — the project baseline).

## Acceptance criteria
- [ ] `pytest` green.
- [ ] Calibration ran on REAL labeled data; thresholds persisted in config + DECISIONS.
- [ ] Calibrated metrics row in BENCHMARKS; gate verdict recorded in STATUS.
- [ ] If FAILED: `output/gate_failures.txt` exists with categorized misses.

## Verify
```powershell
python -m logoscanner calibrate --labeled data\labeled
python -m logoscanner benchmark --labeled data\labeled --signals ocr,sift
pytest -q
```

## Out of scope
- Any new signal; performance work.

## Progress Log

## Completion Report
----- END FILE -----
### 10.5 — `plans/active/phase05.md`

----- BEGIN FILE: plans/active/phase05.md -----
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
----- END FILE -----

### 10.6 — `plans/active/phase06.md`

----- BEGIN FILE: plans/active/phase06.md -----
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
----- END FILE -----

### 10.7 — `plans/active/phase07.md`

----- BEGIN FILE: plans/active/phase07.md -----
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
- [ ] Kill+resume test passes (no duplicates, no reprocessing).
- [ ] Dedup verified on synthetic copies.
- [ ] Full 10k run completed; summary in BENCHMARKS; `detected/`, `review/`, `crops/`, `results.csv/json` present.
- [ ] `pytest` green.

## Verify
```powershell
pytest -q
python -m logoscanner scan --input input --output output
```

## User homework after this phase
- Manually review `output/review/` (use `crops/` for speed). Move confirmed images' labels into `data/labeled/` — this feeds the improvement loop (recalibrate anytime with the grown set).

## Progress Log

## Completion Report
----- END FILE -----

### 10.8 — `plans/active/phaseFinal.md`

----- BEGIN FILE: plans/active/phaseFinal.md -----
# phaseFinal — Documentation, User Guide & GitHub Release

**Goal:** a stranger can clone the repo and use the tool without reading the source; the repo is clean, licensed and released.
**Depends on:** phase07
**Conditional?** no

## Context to load
- `docs/` (all files), `plans/STATUS.md`, `README.md`

## Steps
1. `docs/USER_GUIDE.md` — for non-developers, Windows-first: install Python 3.11+, clone, venv, `pip install -r requirements.txt`; put logo variants in `logo/`; set `BRAND_TERMS`; drop images in `input/`; run `scan`; how to read `results.csv` bands; the review workflow (`output/review/` + `crops/`); how the labeled set + `calibrate` improve the system over time; troubleshooting (common errors from `errors.csv`).
2. `README.md` final: what/why, 60-second quickstart, sample output table, ASCII architecture, honest limitations (very small/blurred logos, heavy occlusion, stylized redesigns), benchmark summary, license, "built with an AI-driven phase workflow — see `plans/`".
3. **License:** ask the user; recommend MIT if phase06 was skipped. If phase06 shipped, resolve D-006 (AGPL) explicitly before publishing.
4. **Hygiene audit:** review `git ls-files` — zero private assets (no real logo, no company images, no weights); `.gitignore` verified; fresh-clone smoke: `pip install -r requirements.txt && pytest -q -m "not slow"` passes.
5. Final STATUS update (project complete, improvement-loop instructions), CHANGELOG, CODEMAP sweep for accuracy.
6. Commit `phaseFinal: docs + release`, tag `v1.0.0`, push (user assists with auth if needed); short GitHub release notes; suggest repo description + topics.

## Acceptance criteria
- [ ] USER_GUIDE complete; a non-developer path exists from zero to results.
- [ ] Hygiene audit clean; fresh-clone smoke passes.
- [ ] LICENSE chosen and committed; v1.0.0 tagged.

## Verify
```powershell
git ls-files
pytest -q -m "not slow"
```

## Progress Log

## Completion Report
----- END FILE -----

---

## 11. Backlog (ideas, NOT phases — add via TEMPLATE_PHASE only if the user asks)
- Small local UI (Streamlit) over the CLI · watch-folder mode for new images · OpenVINO/Arc acceleration if the tool becomes recurring at larger scale · packaging as a single executable (PyInstaller).

*End of bootstrap document. AI: execute Section 7 now.*
