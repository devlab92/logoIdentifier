"""Labeled-set metrics: a mini-set whose answers are known by hand."""

from __future__ import annotations

import make_synthetic
import pytest

from logoscanner import config
from logoscanner.metrics import (
    Metrics,
    ScoredImage,
    evaluate,
    format_metrics,
    score_images,
)
from logoscanner.signals import SignalResult

THRESHOLDS = {"ocr": (0.60, 0.95), "sift": (0.05, 0.65)}


class ConstantSignal:
    """Scores every image the same, so metrics are exactly predictable."""

    def __init__(self, score: float = 0.9, name: str = "constant"):
        self.name = name
        self.score = score

    def run(self, image):
        return SignalResult(self.name, self.score, (1, 2, 3, 4))


def record(filename, label, ocr=0.0, sift=0.0) -> ScoredImage:
    return ScoredImage(filename=filename, label=label, scores={"ocr": ocr, "sift": sift})


# 5 positives, 5 negatives, hand-checked against THRESHOLDS:
#   p1 positive band (ocr strong)      p2 positive band (sift strong)
#   p3 review (ocr weak)               p4 review (sift weak)
#   p5 negative  <- the only miss
#   n1 positive band  <- the only false positive
#   n2 review, n3..n5 negative
MINI = [
    record("p1.jpg", "positive", ocr=0.98),
    record("p2.jpg", "positive", sift=0.80),
    record("p3.jpg", "positive", ocr=0.70),
    record("p4.jpg", "positive", sift=0.20),
    record("p5.jpg", "positive", ocr=0.10, sift=0.02),
    record("n1.jpg", "negative", ocr=0.96),
    record("n2.jpg", "negative", ocr=0.65),
    record("n3.jpg", "negative"),
    record("n4.jpg", "negative", ocr=0.30),
    record("n5.jpg", "negative", sift=0.04),
]


def test_metrics_on_a_mini_set_with_known_answers():
    metrics = evaluate(MINI, THRESHOLDS)
    assert (metrics.images, metrics.positives, metrics.negatives) == (10, 5, 5)
    assert metrics.precision == pytest.approx(2 / 3)  # p1, p2 right; n1 wrong
    assert metrics.catch_recall == pytest.approx(4 / 5)  # p5 falls through
    assert metrics.review_share == pytest.approx(3 / 10)  # p3, p4, n2
    assert metrics.false_negatives == ["p5.jpg"]
    assert metrics.false_positives == ["n1.jpg"]
    assert metrics.missed == 1


def test_confusion_counts_cover_every_band_of_every_label():
    counts = evaluate(MINI, THRESHOLDS).counts
    assert counts["positive"] == {"positive": 2, "review": 2, "negative": 1}
    assert counts["negative"] == {"positive": 1, "review": 1, "negative": 3}
    assert sum(sum(row.values()) for row in counts.values()) == len(MINI)


def test_wins_credit_the_signal_that_set_the_band():
    wins = evaluate(MINI, THRESHOLDS).wins
    # p1 ocr, p2 sift, p3 ocr, p4 sift, n1 ocr, n2 ocr — negatives band nothing.
    assert wins == {"ocr": 4, "sift": 2}


def test_thresholds_change_the_verdict_not_the_scores():
    strict = evaluate(MINI, {"ocr": (0.90, 0.99), "sift": (0.90, 0.99)})
    assert strict.catch_recall == pytest.approx(1 / 5)  # only p1 survives
    generous = evaluate(MINI, {"ocr": (0.05, 0.99), "sift": (0.01, 0.99)})
    assert generous.catch_recall == pytest.approx(1.0)
    assert generous.review_share > strict.review_share


def test_an_empty_set_does_not_divide_by_zero():
    metrics = evaluate([], THRESHOLDS)
    assert (metrics.precision, metrics.catch_recall, metrics.review_share) == (0.0, 0.0, 0.0)


def test_score_images_reads_both_classes_and_reports_errors(tmp_path, dummy_logo_path):
    labeled = tmp_path / "labeled"
    make_synthetic.generate(
        labeled, count=6, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(60, 80), seed=3,
    )
    (labeled / "positive" / "broken.png").write_bytes(b"not a png")

    records, meta = score_images(labeled, [ConstantSignal(0.42)], progress=False)

    assert len(records) == 6
    assert {r.label for r in records} == {"positive", "negative"}
    assert all(r.scores == {"constant": 0.42} for r in records)
    assert all(r.filename and "/" not in r.filename for r in records)
    assert (meta["images"], meta["positives"], meta["negatives"]) == (6, 3, 3)
    assert len(meta["errors"]) == 1 and "broken.png" in meta["errors"][0]
    assert meta["signals"] == ["constant"]
    assert meta["signal_seconds"]["constant"] >= 0.0


def test_score_images_limit_applies_per_class(tmp_path, dummy_logo_path):
    labeled = tmp_path / "labeled"
    make_synthetic.generate(
        labeled, count=8, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(60, 80), seed=3,
    )
    _, meta = score_images(labeled, [ConstantSignal()], limit=2, progress=False)
    assert (meta["positives"], meta["negatives"]) == (2, 2)


def test_as_dict_is_json_ready():
    payload = evaluate(MINI, THRESHOLDS).as_dict()
    assert payload["false_negatives"] == ["p5.jpg"]
    assert payload["counts"]["positive"]["review"] == 2
    assert set(payload) >= {"precision", "catch_recall", "review_share", "wins", "missed"}


def test_format_metrics_mentions_the_headline_numbers_and_the_misses():
    text = format_metrics(evaluate(MINI, THRESHOLDS), THRESHOLDS)
    assert "catch-recall : 0.800" in text
    assert "p5.jpg" in text
    for band in config.BANDS:
        assert band in text


def test_metrics_defaults_are_a_clean_empty_report():
    assert Metrics().as_dict()["images"] == 0
