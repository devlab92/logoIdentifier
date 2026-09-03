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
