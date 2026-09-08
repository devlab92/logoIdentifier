"""The append-only scan journal: `output/.progress.jsonl`, one line per image.

A 10,000-image run takes hours, and hours are long enough for a laptop to
sleep, a disk to fill or a human to hit Ctrl-C. The journal makes that cheap:
each finished image is appended as one JSON line and flushed to disk before the
next one starts, so an interrupted run loses at most the image in flight. On
the next start every journaled path is skipped.

The journal - not `results.csv` - is the source of truth (D-030). The CSV and
the JSON summary are *rewritten from it* at the end of every run, including an
interrupted one, so the reports can never drift from what was actually scanned
and a half-written CSV is never something to recover from.

Lines are independent: a line torn in half by a power cut fails to parse and is
dropped, costing one re-scanned image instead of the whole run.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from logoscanner.dedup import format_hash, parse_hash
from logoscanner.results import ResultRow

JOURNAL_NAME = ".progress.jsonl"


@dataclass
class JournalEntry:
    """One processed image, as stored on a journal line."""

    path: str  # relative to the scan root; the identity used when resuming
    sha256: str = ""
    dhash: str = ""
    band: str = "negative"
    confidence: float = 0.0
    bbox: tuple[int, int, int, int] | None = None
    method: str = ""
    duplicate_of: str = ""
    error: str = ""
    ts: float = field(default_factory=time.time)

    @property
    def image_hash(self) -> int | None:
        """The perceptual hash as an int, for `dedup.DuplicateIndex`."""
        return parse_hash(self.dhash)

    def to_row(self) -> ResultRow:
        """Render as the CSV row for this image."""
        from logoscanner import config

        x, y, w, h = self.bbox if self.bbox else (None, None, None, None)
        return ResultRow(
            filename=self.path,
            contains_logo=self.band == config.BAND_POSITIVE,
            band=self.band,
            confidence=self.confidence,
            x=x, y=y, w=w, h=h,
            method=self.method,
            duplicate_of=self.duplicate_of,
            error=self.error,
        )

    def to_json(self) -> str:
        data = asdict(self)
        data["bbox"] = list(self.bbox) if self.bbox else None
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> "JournalEntry | None":
        """Parse one line; None when it is blank, torn or not an entry."""
        line = line.strip()
        if not line:
            return None
        try:
            data = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            return None
        if not isinstance(data, dict) or not data.get("path"):
            return None
        bbox = data.get("bbox")
        return cls(
            path=str(data["path"]),
            sha256=str(data.get("sha256") or ""),
            dhash=str(data.get("dhash") or ""),
            band=str(data.get("band") or "negative"),
            confidence=float(data.get("confidence") or 0.0),
            bbox=tuple(int(v) for v in bbox) if bbox else None,
            method=str(data.get("method") or ""),
            duplicate_of=str(data.get("duplicate_of") or ""),
            error=str(data.get("error") or ""),
            ts=float(data.get("ts") or 0.0),
        )

    @classmethod
    def from_decision(cls, path: str, decision, sha: str = "", image_hash: int | None = None):
        """Build an entry from what `pipeline.run` returned."""
        return cls(
            path=path,
            sha256=sha,
            dhash=format_hash(image_hash),
            band=decision.band,
            confidence=round(float(decision.confidence), 4),
            bbox=decision.bbox,
            method=decision.method,
        )


def copy_of(original: JournalEntry, path: str, sha: str = "",
            image_hash: int | None = None) -> JournalEntry:
    """A new entry for `path` carrying `original`'s verdict, marked as its copy.

    The duplicate keeps its own hashes (they are what proved the match) but not
    its own analysis: no signal ever runs on it, which is the whole point.
    """
    return JournalEntry(
        path=path,
        sha256=sha,
        dhash=format_hash(image_hash),
        band=original.band,
        confidence=original.confidence,
        bbox=original.bbox,
        method=original.method,
        duplicate_of=original.duplicate_of or original.path,
    )


def error_entry(path: str, error: str, sha: str = "") -> JournalEntry:
    """An entry recording that this file could not be processed."""
    from logoscanner import config

    return JournalEntry(path=path, sha256=sha, band=config.BAND_NEGATIVE,
                        method="none", error=error)


def load(path: str | Path) -> dict[str, JournalEntry]:
    """Read a journal into `{relative path: entry}`, newest line winning.

    Unparseable lines are skipped silently - see the module docstring. A
    missing file is simply an empty journal (a first run).
    """
    path = Path(path)
    entries: dict[str, JournalEntry] = {}
    if not path.is_file():
        return entries
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            entry = JournalEntry.from_json(line)
            if entry is not None:
                entries[entry.path] = entry
    return entries


def rows(entries: Iterable[JournalEntry]) -> list[ResultRow]:
    """Journal entries -> CSV rows, sorted by path so reports are stable."""
    return [entry.to_row() for entry in sorted(entries, key=lambda e: e.path)]


class Journal:
    """Append-only writer that flushes each entry to disk before returning."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = None

    def __enter__(self) -> "Journal":
        self._handle = self.path.open("a", encoding="utf-8", newline="\n")
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def append(self, entry: JournalEntry) -> JournalEntry:
        """Write one entry and force it out to the filesystem."""
        if self._handle is None:  # pragma: no cover - misuse
            raise RuntimeError("journal is not open")
        self._handle.write(entry.to_json() + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())
        return entry

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None


def reset(path: str | Path) -> None:
    """Delete the journal so the next scan starts from scratch."""
    path = Path(path)
    if path.exists():
        path.unlink()
