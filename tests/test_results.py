"""CSV / JSON schema round-trip."""

from __future__ import annotations

import csv
import json

from logoscanner.config import BANDS
from logoscanner.results import (
    CSV_COLUMNS,
    ResultRow,
    read_csv,
    summarize,
    write_csv,
    write_json,
)


def _rows():
    return [
        ResultRow("a.png", True, "positive", 0.9123, 10, 20, 30, 40, "template"),
        ResultRow("sub/b.jpg", False, "review", 0.5, method="ocr"),
        ResultRow("bad.png", False, "negative", 0.0, method="none", error="decode failed"),
    ]


def test_csv_header_matches_schema(tmp_path):
    path = write_csv(_rows(), tmp_path / "out" / "results.csv")
    with path.open(encoding="utf-8", newline="") as handle:
        assert next(csv.reader(handle)) == list(CSV_COLUMNS)


def test_csv_round_trips(tmp_path):
    original = _rows()
    path = write_csv(original, tmp_path / "results.csv")
    restored = read_csv(path)
    assert len(restored) == len(original)
    for before, after in zip(original, restored):
        assert after.filename == before.filename
        assert after.contains_logo == before.contains_logo
        assert after.band == before.band
        assert after.confidence == round(before.confidence, 4)
        assert (after.x, after.y, after.w, after.h) == (before.x, before.y, before.w, before.h)
        assert after.method == before.method
        assert after.error == before.error


def test_summary_counts_bands_errors_and_timing(tmp_path):
    summary = summarize(_rows(), seconds=2.0)
    assert summary["images"] == 3
    assert summary["bands"] == {"positive": 1, "review": 1, "negative": 1}
    assert set(summary["bands"]) == set(BANDS)
    assert summary["errors"] == 1
    assert summary["images_per_second"] == 1.5
    assert summary["eta_10k_seconds"] == round(10_000 / 1.5, 1)

    path = write_json(summary, tmp_path / "summary.json")
    assert json.loads(path.read_text(encoding="utf-8")) == summary


def test_summary_handles_zero_elapsed():
    summary = summarize([], seconds=0.0)
    assert summary["images"] == 0
    assert summary["eta_10k_seconds"] is None
