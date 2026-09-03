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
