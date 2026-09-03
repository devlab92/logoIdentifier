"""End-to-end `scan` behaviour (phase01: walk + load + report, no detection)."""

from __future__ import annotations

import json

import make_synthetic
from logoscanner import __version__
from logoscanner.cli import main, run_scan
from logoscanner.results import CSV_NAME, JSON_NAME, read_csv


def test_version_command(capsys):
    assert main(["version"]) == 0
    assert __version__ in capsys.readouterr().out


def test_scan_writes_csv_and_json(tmp_path, dummy_logo_path):
    input_dir, output_dir = tmp_path / "in", tmp_path / "out"
    make_synthetic.generate(
        input_dir, count=6, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(120, 160), seed=11,
    )

    summary = run_scan(input_dir, output_dir, progress=False)

    assert summary["images"] == 6
    assert summary["bands"]["negative"] == 6  # no detector yet
    assert summary["errors"] == 0
    assert summary["eta_10k_seconds"] is not None

    rows = read_csv(output_dir / CSV_NAME)
    assert len(rows) == 6
    assert all(row.band == "negative" and row.confidence == 0.0 for row in rows)
    # Filenames are relative to the input root, so subfolders stay visible.
    assert all(row.filename.startswith(("positive", "negative")) for row in rows)

    written = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    assert written["images"] == 6


def test_corrupt_file_does_not_crash_and_lands_in_error_column(tmp_path, dummy_logo_path):
    input_dir, output_dir = tmp_path / "in", tmp_path / "out"
    make_synthetic.generate(
        input_dir, count=2, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(100, 120), seed=5,
    )
    (input_dir / "broken.png").write_bytes(b"\x89PNG\r\n\x1a\nnot really a png")

    summary = run_scan(input_dir, output_dir, progress=False)

    assert summary["images"] == 3
    assert summary["errors"] == 1
    errored = [row for row in read_csv(output_dir / CSV_NAME) if row.error]
    assert len(errored) == 1
    assert errored[0].filename == "broken.png"
    assert "decode failed" in errored[0].error


def test_limit_caps_the_number_of_images(tmp_path, dummy_logo_path):
    input_dir, output_dir = tmp_path / "in", tmp_path / "out"
    make_synthetic.generate(
        input_dir, count=8, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(80, 100), seed=9,
    )
    assert run_scan(input_dir, output_dir, limit=3, progress=False)["images"] == 3


def test_scan_via_main_prints_report(tmp_path, dummy_logo_path, capsys):
    input_dir, output_dir = tmp_path / "in", tmp_path / "out"
    make_synthetic.generate(
        input_dir, count=2, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(80, 100), seed=4,
    )
    exit_code = main([
        "scan", "--input", str(input_dir), "--output", str(output_dir), "--no-progress",
    ])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Throughput" in out and "ETA 10,000" in out


def test_missing_input_folder_exits_nonzero(tmp_path, capsys):
    exit_code = main([
        "scan", "--input", str(tmp_path / "nope"), "--output", str(tmp_path / "out"),
    ])
    assert exit_code == 2
    assert "not found" in capsys.readouterr().out
