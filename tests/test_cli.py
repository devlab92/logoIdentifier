"""End-to-end `scan` and `benchmark` behaviour.

The walk/load/report tests run with `signals=()` so they stay fast and cannot
be perturbed by what the OCR engine reads out of procedural noise; the real
pipeline is covered by `test_scan_detects_brand_text_end_to_end`.
"""

from __future__ import annotations

import json

import make_synthetic
from logoscanner import __version__, config
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

    summary = run_scan(input_dir, output_dir, progress=False, signals=())

    assert summary["images"] == 6
    assert summary["bands"]["negative"] == 6  # signals disabled for this test
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

    summary = run_scan(input_dir, output_dir, progress=False, signals=())

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
    assert run_scan(input_dir, output_dir, limit=3, progress=False, signals=())["images"] == 3


def test_scan_via_main_prints_report(tmp_path, dummy_logo_path, capsys):
    input_dir, output_dir = tmp_path / "in", tmp_path / "out"
    make_synthetic.generate(
        input_dir, count=2, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(80, 100), seed=4,
    )
    exit_code = main([
        "scan", "--input", str(input_dir), "--output", str(output_dir),
        "--no-progress", "--signals", "",
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


def test_scan_detects_brand_text_end_to_end(tmp_path, dummy_logo_path):
    """The real OCR pipeline: brand text in, positive rows with boxes out."""
    input_dir, output_dir = tmp_path / "in", tmp_path / "out"
    make_synthetic.generate(
        input_dir, count=4, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(240, 420), seed=21, text_ratio=1.0,
    )

    summary = run_scan(input_dir, output_dir, progress=False)

    assert summary["signals"] == list(config.ENABLED_SIGNALS)
    rows = {row.filename: row for row in read_csv(output_dir / CSV_NAME)}
    positives = [row for name, row in rows.items() if name.startswith("positive")]
    assert positives and all(row.contains_logo for row in positives)
    assert all(row.method == "ocr" and row.confidence > 0.7 for row in positives)
    assert all(None not in (row.x, row.y, row.w, row.h) for row in positives)
    negatives = [row for name, row in rows.items() if name.startswith("negative")]
    assert all(not row.contains_logo for row in negatives)


def test_unknown_signal_name_is_rejected(tmp_path, capsys):
    exit_code = main([
        "scan", "--input", str(tmp_path), "--output", str(tmp_path / "out"),
        "--signals", "nope",
    ])
    assert exit_code == 2
    assert "unknown signal" in capsys.readouterr().out


def test_benchmark_command_runs_and_records(tmp_path, dummy_logo_path, capsys, monkeypatch):
    labeled = tmp_path / "labeled"
    make_synthetic.generate(
        labeled, count=4, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(240, 420), seed=22, text_ratio=1.0,
    )
    docs = tmp_path / "BENCHMARKS.md"
    monkeypatch.chdir(tmp_path)  # keep the real docs/BENCHMARKS.md untouched

    exit_code = main([
        "benchmark", "--labeled", str(labeled), "--signals", "ocr",
        "--no-progress", "--no-record",
    ])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "signal: ocr" in out and "catch-recall" in out
    assert not docs.exists()


def test_benchmark_missing_folder_exits_nonzero(tmp_path, capsys):
    assert main(["benchmark", "--labeled", str(tmp_path / "nope")]) == 2
    assert "not found" in capsys.readouterr().out
