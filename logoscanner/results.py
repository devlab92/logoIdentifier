"""Result row schema and the CSV / JSON report writers (stdlib only)."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Iterable, Sequence

from logoscanner.config import BANDS

CSV_NAME = "results.csv"
JSON_NAME = "summary.json"
ERRORS_NAME = "errors.csv"

# Columns of the errors report: every file the scan could not process.
ERROR_COLUMNS = ("filename", "error")

# Column order of the CSV; also the accepted schema when reading one back.
CSV_COLUMNS = (
    "filename",
    "contains_logo",
    "band",
    "confidence",
    "x",
    "y",
    "w",
    "h",
    "method",
    "duplicate_of",
    "error",
)


@dataclass
class ResultRow:
    """One scanned image. `x/y/w/h` describe the best match box, if any."""

    filename: str
    contains_logo: bool = False
    band: str = "negative"
    confidence: float = 0.0
    x: int | None = None
    y: int | None = None
    w: int | None = None
    h: int | None = None
    method: str = ""
    duplicate_of: str = ""
    error: str = ""

    def to_csv_dict(self) -> dict[str, str]:
        """Render as CSV-safe strings; `None` boxes become empty cells."""
        row = asdict(self)
        row["contains_logo"] = "true" if self.contains_logo else "false"
        row["confidence"] = f"{float(self.confidence):.4f}"
        for key in ("x", "y", "w", "h"):
            row[key] = "" if row[key] is None else str(int(row[key]))
        for key in ("filename", "band", "method", "duplicate_of", "error"):
            row[key] = "" if row[key] is None else str(row[key])
        return row

    @classmethod
    def from_csv_dict(cls, row: dict[str, str]) -> "ResultRow":
        """Inverse of `to_csv_dict`, so a written CSV round-trips."""
        return cls(
            filename=row["filename"],
            contains_logo=row["contains_logo"].strip().lower() == "true",
            band=row["band"],
            confidence=float(row["confidence"] or 0.0),
            x=_opt_int(row["x"]),
            y=_opt_int(row["y"]),
            w=_opt_int(row["w"]),
            h=_opt_int(row["h"]),
            method=row["method"],
            duplicate_of=row.get("duplicate_of", ""),
            error=row["error"],
        )


def _opt_int(value: str) -> int | None:
    value = (value or "").strip()
    return int(value) if value else None


def write_csv(rows: Iterable[ResultRow], path: str | Path) -> Path:
    """Write `rows` to `path` as UTF-8 CSV with the canonical header."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_dict())
    return path


def read_csv(path: str | Path) -> list[ResultRow]:
    """Read back a results CSV written by `write_csv`."""
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return [ResultRow.from_csv_dict(row) for row in csv.DictReader(handle)]


def summarize(rows: Sequence[ResultRow], seconds: float, processed: int | None = None) -> dict:
    """Build the JSON summary: per-band totals, error count and timing.

    `rows` is everything the run knows about (a resumed run includes the images
    an earlier attempt already did); `processed` is how many of them this run
    actually paid for. Throughput is measured on the latter so a resume cannot
    report a fictional img/s - it defaults to `len(rows)` for a fresh run.
    """
    counts = {band: 0 for band in BANDS}
    for row in rows:
        counts[row.band] = counts.get(row.band, 0) + 1
    total = len(rows)
    done = total if processed is None else int(processed)
    rate = done / seconds if seconds > 0 else 0.0
    return {
        "images": total,
        "processed": done,
        "skipped": total - done,
        "bands": counts,
        "duplicates": sum(1 for row in rows if row.duplicate_of),
        "errors": sum(1 for row in rows if row.error),
        "seconds": round(seconds, 3),
        "images_per_second": round(rate, 3),
        "eta_10k_seconds": round(10_000 / rate, 1) if rate > 0 else None,
    }


def write_errors(rows: Iterable[ResultRow], path: str | Path) -> Path:
    """Write the failed files to their own small CSV (`filename, error`).

    Errors are already a column of `results.csv`; this file exists so a human
    can see at a glance whether a 10k run lost anything, without filtering.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ERROR_COLUMNS))
        writer.writeheader()
        for row in rows:
            if row.error:
                writer.writerow({"filename": row.filename, "error": row.error})
    return path


def write_json(summary: dict, path: str | Path) -> Path:
    """Write the summary dict as pretty JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return path


# Guard against the dataclass and the CSV header drifting apart.
assert tuple(f.name for f in fields(ResultRow)) == CSV_COLUMNS
