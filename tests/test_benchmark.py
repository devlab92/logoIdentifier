"""Threshold sweep metrics and the `benchmark` driver."""

from __future__ import annotations

import make_synthetic
import pytest

from logoscanner.benchmark import (
    GRID,
    PHASE,
    Point,
    SignalScores,
    append_rows,
    benchmark_row,
    best_point,
    combine,
    evaluate,
    run_benchmark,
    score_labeled,
    sweep,
)
from logoscanner.signals import SignalResult


class ConstantSignal:
    """Scores every image the same, so metrics are exactly predictable."""

    def __init__(self, score: float = 0.9, name: str = "constant"):
        self.name = name
        self.score = score

    def run(self, image):
        return SignalResult(self.name, self.score, (1, 2, 3, 4))


def scores(positive, negative, name="s") -> SignalScores:
    return SignalScores(name=name, positive=list(positive), negative=list(negative))


def test_evaluate_counts_precision_recall_and_the_review_pile():
    # 4 positives, 4 negatives; review >= 0.4, positive >= 0.8.
    point = evaluate(scores([0.9, 0.85, 0.5, 0.1], [0.9, 0.3, 0.2, 0.0]), 0.4, 0.8)
    assert point.precision == pytest.approx(2 / 3)  # 2 true, 1 false above 0.8
    assert point.catch_recall == pytest.approx(3 / 4)  # 0.1 falls through
    assert point.review_share == pytest.approx(1 / 8)  # only the 0.5 positive
    assert point.missed == 1


def test_a_positive_below_the_review_threshold_is_a_miss():
    assert evaluate(scores([0.2], [0.0]), 0.5, 0.9).missed == 1
    assert evaluate(scores([0.2], [0.0]), 0.1, 0.9).missed == 0


def test_empty_classes_do_not_divide_by_zero():
    point = evaluate(scores([], []), 0.5, 0.9)
    assert (point.precision, point.catch_recall, point.review_share) == (0.0, 0.0, 0.0)


def test_sweep_only_emits_pairs_where_positive_is_at_least_review():
    points = sweep(scores([0.9], [0.1]))
    assert points and all(p.positive_threshold >= p.review_threshold for p in points)
    assert len(points) == len(GRID) * (len(GRID) + 1) // 2


def test_best_point_puts_catch_recall_first():
    stingy = Point(0.9, 0.9, precision=1.0, catch_recall=0.5, review_share=0.0, missed=5)
    generous = Point(0.2, 0.9, precision=0.4, catch_recall=1.0, review_share=0.5, missed=0)
    assert best_point([stingy, generous]) is generous


def test_best_point_breaks_ties_on_precision_then_review_size():
    loose = Point(0.2, 0.5, precision=0.6, catch_recall=1.0, review_share=0.4, missed=0)
    tight = Point(0.2, 0.7, precision=0.9, catch_recall=1.0, review_share=0.4, missed=0)
    assert best_point([loose, tight]) is tight
    small = Point(0.3, 0.7, precision=0.9, catch_recall=1.0, review_share=0.1, missed=0)
    assert best_point([tight, small]) is small


def test_best_point_of_nothing_is_none():
    assert best_point([]) is None


def test_benchmark_row_has_the_documented_columns():
    entry = scores([0.9] * 3, [0.1] * 2, name="ocr")
    entry.seconds = 5.0
    row = benchmark_row("ocr", entry, best_point(sweep(entry)), note="hello")
    cells = [cell.strip() for cell in row.strip("|").split("|")]
    assert len(cells) == 9
    assert cells[1] == PHASE and cells[2] == "3/2" and cells[3] == "ocr"
    assert cells[7] == "1.00"  # 5 images / 5 s
    assert "hello" in cells[8] and "t_rev=" in cells[8]


def test_benchmark_row_survives_an_empty_dataset():
    row = benchmark_row("ocr", scores([], []), None)
    assert "n/a" in row


def test_append_rows_only_appends(tmp_path):
    path = tmp_path / "BENCHMARKS.md"
    path.write_text("| header |\n", encoding="utf-8")
    append_rows(["| a |"], path)
    append_rows(["| b |"], path)
    assert path.read_text(encoding="utf-8") == "| header |\n| a |\n| b |\n"


def test_score_labeled_reads_both_classes_and_reports_errors(tmp_path, dummy_logo_path):
    labeled = tmp_path / "labeled"
    make_synthetic.generate(
        labeled, count=6, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(60, 80), seed=3,
    )
    (labeled / "positive" / "broken.png").write_bytes(b"not a png")

    result, meta = score_labeled(labeled, [ConstantSignal(0.42)], progress=False)

    entry = result["constant"]
    assert entry.positive == [0.42] * 3 and entry.negative == [0.42] * 3
    assert meta["images"] == 6 and meta["positives"] == 3 and meta["negatives"] == 3
    assert len(meta["errors"]) == 1 and "broken.png" in meta["errors"][0]
    assert meta["signals"] == ["constant"]


def test_limit_applies_per_class(tmp_path, dummy_logo_path):
    labeled = tmp_path / "labeled"
    make_synthetic.generate(
        labeled, count=8, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(60, 80), seed=3,
    )
    _, meta = score_labeled(labeled, [ConstantSignal()], limit=2, progress=False)
    assert (meta["positives"], meta["negatives"]) == (2, 2)


def test_run_benchmark_prints_a_report_and_records_one_row(tmp_path, dummy_logo_path, capsys):
    labeled = tmp_path / "labeled"
    make_synthetic.generate(
        labeled, count=4, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(60, 80), seed=3,
    )
    docs = tmp_path / "BENCHMARKS.md"

    summary = run_benchmark(
        labeled, [ConstantSignal(0.9)], progress=False, docs_path=docs, note="unit test",
    )

    out = capsys.readouterr().out
    assert "signal: constant" in out and "best pair" in out
    best = summary["signals"]["constant"]["best"]
    assert best["catch_recall"] == 1.0
    assert best["precision"] == 0.5  # constant scorer cannot separate the classes
    assert docs.read_text(encoding="utf-8").count("unit test |") == 1


def test_run_benchmark_can_skip_the_docs_row(tmp_path, dummy_logo_path):
    labeled = tmp_path / "labeled"
    make_synthetic.generate(
        labeled, count=2, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(60, 80), seed=3,
    )
    docs = tmp_path / "BENCHMARKS.md"
    run_benchmark(labeled, [ConstantSignal()], progress=False, write_docs=False, docs_path=docs)
    assert not docs.exists()


def test_combine_takes_the_strongest_signal_per_image():
    weak = scores([0.9, 0.1], [0.2, 0.0], name="ocr")
    other = scores([0.2, 0.8], [0.0, 0.5], name="sift")
    weak.seconds, other.seconds = 1.0, 2.0

    merged = combine([weak, other])

    assert merged.name == "ocr+sift"
    assert merged.positive == [0.9, 0.8]
    assert merged.negative == [0.2, 0.5]
    assert merged.seconds == 3.0  # the human waits for both signals


def test_run_benchmark_adds_a_combined_row_for_several_signals(tmp_path, dummy_logo_path):
    labeled = tmp_path / "labeled"
    make_synthetic.generate(
        labeled, count=4, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(60, 80), seed=3,
    )
    docs = tmp_path / "BENCHMARKS.md"

    summary = run_benchmark(
        labeled,
        [ConstantSignal(0.3, "quiet"), ConstantSignal(0.9, "loud")],
        progress=False,
        docs_path=docs,
    )

    assert set(summary["signals"]) == {"quiet", "loud", "quiet+loud"}
    text = docs.read_text(encoding="utf-8")
    assert text.count("| quiet+loud |") == 1 and "naive OR" in text
