"""Sampling the rejected images to measure what the scanner misses (D-034).

The point of this tool is an *unbiased* estimate, so the tests care most about
what must stay out of the sample - duplicates, failures, anything already
labeled - and about the interval maths, which has to stay honest when a clean
sample tempts it to claim certainty.
"""

from __future__ import annotations

import csv

import numpy as np
import pytest

import audit_negatives
from logoscanner import artifacts
from logoscanner.results import ResultRow, write_csv


def _row(name, band="negative", **kwargs) -> ResultRow:
    return ResultRow(name, band == "positive", band, 0.0, method="none", **kwargs)


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "input").mkdir()
    for cls in ("positive", "negative"):
        (tmp_path / "labeled" / cls).mkdir(parents=True)
    return tmp_path


def _write_inputs(workspace, relatives):
    rng = np.random.default_rng(0)
    for relative in relatives:
        path = workspace / "input" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        artifacts.write_image(rng.integers(0, 255, (40, 50, 3), dtype=np.uint8), path)


def _run(workspace, *extra) -> int:
    return audit_negatives.main([
        "--results", str(workspace / "results.csv"),
        "--input", str(workspace / "input"),
        "--labeled", str(workspace / "labeled"),
        "--out", str(workspace / "audit"),
        *extra,
    ])


def test_only_unlabeled_unique_readable_negatives_are_eligible():
    rows = [
        _row("a/keep.png"),
        _row("a/flagged.png", band="positive"),
        _row("a/review.png", band="review"),
        _row("a/copy.png", duplicate_of="a/keep.png"),
        _row("a/broken.png", error="decode failed"),
        _row("a/already.png"),
    ]
    pool = audit_negatives.candidates(rows, already={"already.png"})
    assert pool == ["a/keep.png"]


def test_a_label_written_with_the_month_prefix_still_counts_as_labeled():
    rows = [_row("wp/2020-08/pic.png")]
    assert audit_negatives.candidates(rows, already={"2020-08__pic.png"}) == []
    assert audit_negatives.candidates(rows, already={"pic.png"}) == []


def test_labeled_names_reads_both_spellings(workspace):
    (workspace / "labeled" / "positive" / "2020-08__pic.png").write_bytes(b"x")
    (workspace / "labeled" / "negative" / "plain.png").write_bytes(b"x")
    names = audit_negatives.labeled_names(workspace / "labeled")
    assert names == {"2020-08__pic.png", "pic.png", "plain.png"}


def test_flat_name_keeps_the_month():
    assert audit_negatives.flat_name("wp/2020-08/a.png") == "2020-08__a.png"
    assert audit_negatives.flat_name("a.png") == "a.png"


def test_wilson_never_claims_certainty_from_a_clean_sample():
    low, high = audit_negatives.wilson(0, 100)
    assert low == 0.0
    assert 0.0 < high < 0.05, "0/100 must not be reported as a proven zero"


def test_wilson_brackets_the_observed_rate():
    low, high = audit_negatives.wilson(5, 100)
    assert low < 0.05 < high
    assert audit_negatives.wilson(0, 0) == (0.0, 1.0)


def test_prepare_copies_the_sample_and_writes_a_manifest(workspace):
    relatives = [f"2020-01/pic{i}.png" for i in range(10)]
    _write_inputs(workspace, relatives)
    write_csv([_row(r) for r in relatives], workspace / "results.csv")

    assert _run(workspace, "--count", "4") == 0

    audit = workspace / "audit"
    copied = {p.name for p in audit.iterdir() if p.is_file() and p.name != "manifest.csv"}
    assert len(copied) == 4
    with (audit / "manifest.csv").open(encoding="utf-8", newline="") as handle:
        entries = list(csv.DictReader(handle))
    assert {e["sample_name"] for e in entries} == copied
    assert all(e["source"] in relatives for e in entries)
    assert (audit / "has_logo").is_dir()


def test_the_sample_is_reproducible_from_its_seed(workspace):
    relatives = [f"2020-01/pic{i}.png" for i in range(20)]
    _write_inputs(workspace, relatives)
    write_csv([_row(r) for r in relatives], workspace / "results.csv")

    _run(workspace, "--count", "5", "--seed", "7")
    first = {p.name for p in (workspace / "audit").iterdir() if p.is_file()}

    import shutil
    shutil.rmtree(workspace / "audit")
    _run(workspace, "--count", "5", "--seed", "7")
    second = {p.name for p in (workspace / "audit").iterdir() if p.is_file()}

    assert first == second


def test_prepare_refuses_to_overwrite_a_sample_in_progress(workspace, capsys):
    relatives = ["2020-01/pic.png"]
    _write_inputs(workspace, relatives)
    write_csv([_row(r) for r in relatives], workspace / "results.csv")
    _run(workspace, "--count", "1")

    assert _run(workspace, "--count", "1") == 2
    assert "already exists" in capsys.readouterr().out


def test_prepare_reports_when_there_is_nothing_left_to_audit(workspace, capsys):
    write_csv([_row("a.png", band="positive")], workspace / "results.csv")
    assert _run(workspace) == 1
    assert "nothing to audit" in capsys.readouterr().out


def test_report_counts_what_the_human_moved(workspace, capsys):
    relatives = [f"2020-01/pic{i}.png" for i in range(10)]
    _write_inputs(workspace, relatives)
    write_csv([_row(r) for r in relatives], workspace / "results.csv")
    _run(workspace, "--count", "10")

    audit = workspace / "audit"
    moved = sorted(p for p in audit.iterdir() if p.is_file() and p.name != "manifest.csv")[:2]
    for path in moved:
        path.rename(audit / "has_logo" / path.name)

    assert _run(workspace, "--report") == 0
    out = capsys.readouterr().out
    assert "logos found in it    : 2" in out
    assert "miss rate            : 20.0%" in out


def test_report_ignores_a_stray_file_and_says_so(workspace, capsys):
    relatives = ["2020-01/pic.png"]
    _write_inputs(workspace, relatives)
    write_csv([_row(r) for r in relatives], workspace / "results.csv")
    _run(workspace, "--count", "1")
    (workspace / "audit" / "has_logo" / "not-from-the-sample.png").write_bytes(b"x")

    _run(workspace, "--report")
    out = capsys.readouterr().out

    assert "logos found in it    : 0" in out
    assert "not from this sample" in out


def test_report_without_a_manifest_fails_cleanly(workspace, capsys):
    write_csv([_row("a.png")], workspace / "results.csv")
    assert _run(workspace, "--report") == 2
    assert "no " in capsys.readouterr().out
