"""Resume, dedup, artifacts and robustness of the `scan` driver (phase07).

These are the promises a multi-hour run rests on: an interrupted scan loses at
most the image in flight, a resumed scan reproduces exactly the reports an
uninterrupted one would have written, the same picture is never analysed twice,
and no single bad file can end the run.

Every test drives the pipeline with a stub signal so the assertions are about
the driver, not about what OCR reads out of procedural noise.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

import make_synthetic
from logoscanner import artifacts, journal
from logoscanner.cli import main, run_scan
from logoscanner.journal import JOURNAL_NAME
from logoscanner.results import CSV_NAME, ERRORS_NAME, read_csv
from logoscanner.signals import SignalResult

# Scores chosen against config.FALLBACK_THRESHOLDS (0.60 / 0.85), which is what
# an unregistered signal name gets: positive / review / negative.
_SCORES = (0.95, 0.70, 0.10)


class StubSignal:
    """Deterministic per-image score, with a call counter and an optional trap.

    The score depends only on the pixels, so the same image always lands in the
    same band - that is what lets a resumed run be compared byte for byte with
    an uninterrupted one.
    """

    name = "stub"

    def __init__(self, interrupt_after: int | None = None, crash_on: int | None = None,
                 fixed_score: float | None = None):
        self.calls = 0
        self.interrupt_after = interrupt_after
        self.crash_on = crash_on
        self.fixed_score = fixed_score

    def run(self, image: np.ndarray) -> SignalResult:
        if self.interrupt_after is not None and self.calls >= self.interrupt_after:
            raise KeyboardInterrupt
        self.calls += 1
        if self.crash_on is not None and self.calls == self.crash_on:
            raise RuntimeError("signal exploded")
        if self.fixed_score is not None:
            score = self.fixed_score
        else:
            digest = hashlib.sha256(image.tobytes()).digest()
            score = _SCORES[digest[0] % len(_SCORES)]
        return SignalResult(name=self.name, score=score, bbox=(5, 5, 40, 30), detail="stub")


@pytest.fixture
def synthetic(tmp_path, dummy_logo_path):
    """A small labeled tree to scan; contents do not matter, only that they differ."""
    input_dir = tmp_path / "in"
    make_synthetic.generate(
        input_dir, count=10, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(120, 160), seed=17,
    )
    return input_dir


def test_interrupted_run_journals_what_it_finished_and_still_writes_reports(
    tmp_path, synthetic
):
    output = tmp_path / "out"
    stub = StubSignal(interrupt_after=4)

    summary = run_scan(synthetic, output, progress=False, signals=[stub])

    assert summary["interrupted"] is True
    assert summary["processed"] == 4
    assert stub.calls == 4
    assert len(journal.load(output / JOURNAL_NAME)) == 4
    # The reports describe what was done, not what was planned.
    assert len(read_csv(output / CSV_NAME)) == 4


def test_resume_skips_finished_images_and_reproduces_the_uninterrupted_report(
    tmp_path, synthetic
):
    reference_out, resumed_out = tmp_path / "ref", tmp_path / "resumed"

    reference = StubSignal()
    run_scan(synthetic, reference_out, progress=False, signals=[reference])
    assert reference.calls == 10  # nothing deduplicated; a fair comparison

    killed = StubSignal(interrupt_after=4)
    run_scan(synthetic, resumed_out, progress=False, signals=[killed])

    resumed = StubSignal()
    summary = run_scan(synthetic, resumed_out, progress=False, signals=[resumed])

    assert summary["interrupted"] is False
    assert resumed.calls == 6, "the first four images were re-analysed"
    assert summary["processed"] == 6 and summary["skipped"] == 4
    assert summary["images"] == 10
    assert (resumed_out / CSV_NAME).read_text(encoding="utf-8") == (
        reference_out / CSV_NAME
    ).read_text(encoding="utf-8")


def test_resuming_a_finished_scan_does_no_work_at_all(tmp_path, synthetic):
    output = tmp_path / "out"
    run_scan(synthetic, output, progress=False, signals=[StubSignal()])

    again = StubSignal()
    summary = run_scan(synthetic, output, progress=False, signals=[again])

    assert again.calls == 0
    assert summary["processed"] == 0 and summary["images"] == 10


def test_restart_discards_the_journal_and_scans_everything_again(tmp_path, synthetic):
    output = tmp_path / "out"
    run_scan(synthetic, output, progress=False, signals=[StubSignal()])

    stub = StubSignal()
    summary = run_scan(synthetic, output, progress=False, signals=[stub], restart=True)

    assert stub.calls == 10 and summary["processed"] == 10
    assert summary["images"] == 10  # not 20: the journal was replaced, not appended


def test_exact_and_near_duplicates_borrow_the_verdict_without_being_scanned(
    tmp_path, dummy_logo_path
):
    input_dir = tmp_path / "in"
    input_dir.mkdir(parents=True)
    rng = np.random.default_rng(3)
    picture = np.zeros((160, 240, 3), np.uint8)
    for i in range(6):
        x, y = int(rng.integers(0, 200)), int(rng.integers(0, 120))
        cv2.rectangle(picture, (x, y), (x + 40, y + 40),
                      [int(v) for v in rng.integers(30, 230, 3)], -1)
    cv2.imwrite(str(input_dir / "a_original.png"), picture)
    shutil.copy2(input_dir / "a_original.png", input_dir / "b_exact_copy.png")
    cv2.imwrite(str(input_dir / "c_recompressed.jpg"), picture,
                [cv2.IMWRITE_JPEG_QUALITY, 40])

    stub = StubSignal()
    summary = run_scan(input_dir, tmp_path / "out", progress=False, signals=[stub])

    assert stub.calls == 1, "the same picture went through the pipeline more than once"
    assert summary["duplicates"] == 2
    rows = {row.filename: row for row in read_csv(tmp_path / "out" / CSV_NAME)}
    assert rows["a_original.png"].duplicate_of == ""
    assert rows["b_exact_copy.png"].duplicate_of == "a_original.png"
    assert rows["c_recompressed.jpg"].duplicate_of == "a_original.png"
    # The copies carry the original's verdict, boxes included.
    for name in ("b_exact_copy.png", "c_recompressed.jpg"):
        assert rows[name].band == rows["a_original.png"].band
        assert rows[name].x == rows["a_original.png"].x


def test_duplicates_are_still_deduplicated_after_a_resume(tmp_path):
    """The dedup index is rebuilt from the journal, not kept only in memory."""
    input_dir = tmp_path / "in"
    input_dir.mkdir(parents=True)
    rng = np.random.default_rng(9)
    picture = rng.integers(0, 255, (100, 120, 3), dtype=np.uint8)
    cv2.imwrite(str(input_dir / "a.png"), picture)

    run_scan(input_dir, tmp_path / "out", progress=False, signals=[StubSignal()])
    shutil.copy2(input_dir / "a.png", input_dir / "b.png")

    stub = StubSignal()
    summary = run_scan(input_dir, tmp_path / "out", progress=False, signals=[stub])

    assert stub.calls == 0 and summary["duplicates"] == 1


def test_flagged_images_get_a_crop_and_a_copy_but_duplicates_do_not(tmp_path, synthetic):
    output = tmp_path / "out"
    shutil.copy2(
        sorted((synthetic / "positive").iterdir())[0], synthetic / "positive" / "twin.png"
    )

    summary = run_scan(synthetic, output, progress=False, signals=[StubSignal()])

    flagged = [
        row for row in read_csv(output / CSV_NAME)
        if row.band in ("positive", "review") and not row.duplicate_of
    ]
    assert flagged, "the stub should flag something"
    for row in flagged:
        folder = artifacts.DETECTED_DIR if row.band == "positive" else artifacts.REVIEW_DIR
        assert (output / folder / row.filename).is_file()
        crop = artifacts.crop_path(output, row.filename)
        assert crop.is_file() and crop.stat().st_size > 0

    copies = [row for row in read_csv(output / CSV_NAME) if row.duplicate_of]
    assert summary["duplicates"] == len(copies) == 1
    assert not (output / artifacts.DETECTED_DIR / copies[0].filename).exists()
    assert not (output / artifacts.REVIEW_DIR / copies[0].filename).exists()


def test_negatives_are_listed_only(tmp_path, synthetic):
    output = tmp_path / "out"
    run_scan(synthetic, output, progress=False, signals=[StubSignal(fixed_score=0.1)])
    negatives = [row for row in read_csv(output / CSV_NAME) if row.band == "negative"]
    assert len(negatives) == 10
    for row in negatives:
        assert not (output / artifacts.DETECTED_DIR / row.filename).exists()
        assert not (output / artifacts.REVIEW_DIR / row.filename).exists()
        assert not artifacts.crop_path(output, row.filename).exists()


def test_no_artifacts_flag_writes_reports_only(tmp_path, synthetic):
    output = tmp_path / "out"
    run_scan(synthetic, output, progress=False, signals=[StubSignal()], save_artifacts=False)
    assert (output / CSV_NAME).is_file()
    assert not (output / artifacts.DETECTED_DIR).exists()
    assert not (output / artifacts.CROPS_DIR).exists()


def test_a_signal_that_raises_costs_one_image_not_the_run(tmp_path, synthetic):
    output = tmp_path / "out"
    stub = StubSignal(crash_on=3)

    summary = run_scan(synthetic, output, progress=False, signals=[stub])

    assert summary["images"] == 10 and summary["errors"] == 1
    broken = [row for row in read_csv(output / CSV_NAME) if row.error]
    assert "signal exploded" in broken[0].error
    assert broken[0].band == "negative"


def test_unreadable_files_land_in_errors_csv(tmp_path, synthetic):
    (synthetic / "broken.png").write_bytes(b"\x89PNG\r\n\x1a\nnot a png")
    output = tmp_path / "out"

    summary = run_scan(synthetic, output, progress=False, signals=[StubSignal()])

    assert summary["errors"] == 1
    lines = (output / ERRORS_NAME).read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "filename,error"
    assert len(lines) == 2 and lines[1].startswith("broken.png,")


def test_errors_csv_holds_only_a_header_when_nothing_failed(tmp_path, synthetic):
    output = tmp_path / "out"
    run_scan(synthetic, output, progress=False, signals=[StubSignal()])
    assert (output / ERRORS_NAME).read_text(encoding="utf-8").strip() == "filename,error"


def test_report_names_the_artifact_folders(tmp_path, synthetic, capsys):
    exit_code = main([
        "scan", "--input", str(synthetic), "--output", str(tmp_path / "out"),
        "--no-progress", "--signals", "",
    ])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Duplicates" in out and "already journaled" in out


def test_restart_flag_reaches_the_driver(tmp_path, synthetic):
    output = tmp_path / "out"
    argv = ["scan", "--input", str(synthetic), "--output", str(output),
            "--no-progress", "--signals", ""]
    main(argv)
    before = (output / JOURNAL_NAME).read_text(encoding="utf-8").splitlines()

    main(argv + ["--restart"])
    after = (output / JOURNAL_NAME).read_text(encoding="utf-8").splitlines()

    # Replaced, not appended to: every image was scanned again, exactly once.
    assert len(after) == len(before) == 10
    assert len(journal.load(output / JOURNAL_NAME)) == 10


def test_a_hard_killed_process_loses_at_most_the_image_in_flight(tmp_path, dummy_logo_path):
    """The durability claim, tested the only way that proves it: kill the process.

    `TerminateProcess` runs no cleanup and flushes no buffer, so whatever
    survives in the journal survives because `Journal.append` fsynced it. The
    run is driven with `--signals ""` to keep it fast; the machinery under test
    is the journal, not the detectors.
    """
    input_dir = tmp_path / "in"
    output = tmp_path / "out"
    make_synthetic.generate(
        input_dir, count=200, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(64, 80), seed=23,
    )
    journal_path = output / JOURNAL_NAME

    process = subprocess.Popen(
        [sys.executable, "-m", "logoscanner", "scan", "--input", str(input_dir),
         "--output", str(output), "--no-progress", "--signals", ""],
        cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if journal_path.exists() and len(journal.load(journal_path)) >= 5:
                break
            if process.poll() is not None:
                break
            time.sleep(0.02)
    finally:
        process.kill()
        process.wait(timeout=30)

    survived = journal.load(journal_path)
    assert survived, "nothing survived the kill: entries are not being flushed"
    assert len(survived) < 200, "the process finished before it could be killed"
    # A killed run may leave a torn final line; loading it must not raise, and
    # every surviving entry must be a complete verdict.
    assert all(entry.band and entry.path for entry in survived.values())
    # No reports yet - the kill happened before consolidation.
    assert not (output / CSV_NAME).exists()

    resumed = run_scan(input_dir, output, progress=False, signals=[StubSignal()])

    assert resumed["images"] == 200
    assert resumed["processed"] == 200 - len(survived)
    assert len(read_csv(output / CSV_NAME)) == 200
