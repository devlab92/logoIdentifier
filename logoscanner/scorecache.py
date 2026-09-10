"""Remembers what each signal scored on each labeled image, so calibration
does not pay for the same pass twice.

Scoring is the whole cost of `calibrate`: on 1,759 images it is over an hour,
while judging tens of millions of threshold combinations against those scores
takes seconds. Every re-run - a new target, a wider grid, five hundred images
added to the labeled set - was repeating that hour to recompute numbers that
had not changed (D-035).

So scores are written to `output/scores.json`, keyed by filename, and the next
run scores **only the images the cache does not have**. Labeling 500 more
images then costs 500 images of work, not 1,759.

A cached score is only valid for the signal that produced it, so the cache
records which signals it holds and is discarded whole if that set changes. It
is a derived artifact: deleting it is always safe, and always costs exactly one
re-score.
"""

from __future__ import annotations

import json
from pathlib import Path

from logoscanner.metrics import ScoredImage

CACHE_NAME = "scores.json"
FORMAT = 1


def load(path: str | Path, signal_names) -> dict[str, ScoredImage]:
    """Cached records keyed by filename, or `{}` when unusable.

    Unusable covers every way a cache can be stale or wrong - missing, corrupt,
    written by another format version, or holding a different signal set - and
    all of them mean the same thing: score it again.
    """
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        return {}
    if list(payload.get("signals") or ()) != list(signal_names):
        return {}

    records: dict[str, ScoredImage] = {}
    for entry in payload.get("images") or ():
        try:
            filename, label = entry["filename"], entry["label"]
            scores = {name: float(entry["scores"][name]) for name in signal_names}
        except (KeyError, TypeError, ValueError):
            continue  # one bad row is not a reason to redo the other 1,758
        records[filename] = ScoredImage(filename=filename, label=label, scores=scores)
    return records


def save(path: str | Path, records, signal_names) -> Path:
    """Write `records` as the cache for `signal_names`."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": FORMAT,
        "signals": list(signal_names),
        "images": [
            {"filename": r.filename, "label": r.label,
             "scores": {name: round(float(r.scores.get(name, 0.0)), 6)
                        for name in signal_names}}
            for r in sorted(records, key=lambda r: r.filename)
        ],
    }
    path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    return path


def reuse(cached: dict[str, ScoredImage], filename: str, label: str) -> ScoredImage | None:
    """The cached scores for `filename`, re-stamped with the label it has *now*.

    A file that moved from `negative/` to `positive/` scores exactly the same -
    the pixels did not change, only a human's mind - so its scores are still
    worth reusing. But the label must come from where the file sits today, or
    calibration would optimise against a judgement already overturned.
    """
    record = cached.get(filename)
    if record is None:
        return None
    return ScoredImage(filename=filename, label=label, scores=record.scores)
