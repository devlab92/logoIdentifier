"""Per-signal thresholds, the OR rule and the normalized confidence scale."""

from __future__ import annotations

import pytest

from logoscanner import config
from logoscanner.decision import (
    band_of,
    decide,
    decide_scores,
    normalize,
    thresholds_for,
)
from logoscanner.signals import SignalResult

# Two signals with deliberately different scales: 0.7 is a strong SIFT match
# but only a lukewarm OCR read.
THRESHOLDS = {"ocr": (0.60, 0.95), "sift": (0.05, 0.65)}


def test_truth_table_of_one_signal():
    weak, strong = THRESHOLDS["ocr"]
    assert band_of(strong, weak, strong) == config.BAND_POSITIVE
    assert band_of(1.0, weak, strong) == config.BAND_POSITIVE
    assert band_of(weak, weak, strong) == config.BAND_REVIEW
    assert band_of(strong - 0.01, weak, strong) == config.BAND_REVIEW
    assert band_of(weak - 0.01, weak, strong) == config.BAND_NEGATIVE
    assert band_of(0.0, weak, strong) == config.BAND_NEGATIVE


def test_thresholds_are_per_signal_not_a_single_scale():
    # Same raw score, opposite verdicts.
    assert decide_scores({"ocr": 0.70}, THRESHOLDS)[0] == config.BAND_REVIEW
    assert decide_scores({"sift": 0.70}, THRESHOLDS)[0] == config.BAND_POSITIVE


def test_the_best_band_wins_even_when_another_signal_scores_higher():
    band, confidence, winners = decide_scores({"ocr": 0.90, "sift": 0.70}, THRESHOLDS)
    assert band == config.BAND_POSITIVE  # sift is over its strong threshold
    assert winners == ("sift",)
    assert confidence >= config.POSITIVE_THRESHOLD


def test_every_signal_in_the_winning_band_is_reported_strongest_first():
    band, _, winners = decide_scores({"ocr": 0.96, "sift": 1.00}, THRESHOLDS)
    assert band == config.BAND_POSITIVE
    assert winners == ("sift", "ocr")  # sift is further above its own threshold


def test_a_silent_signal_never_dilutes_a_loud_one():
    band, _, winners = decide_scores({"ocr": 0.0, "sift": 0.70}, THRESHOLDS)
    assert (band, winners) == (config.BAND_POSITIVE, ("sift",))


def test_unknown_signals_fall_back_to_the_configured_defaults():
    assert thresholds_for("brand-new", THRESHOLDS) == config.FALLBACK_THRESHOLDS
    weak, strong = config.FALLBACK_THRESHOLDS
    assert decide_scores({"brand-new": strong}, THRESHOLDS)[0] == config.BAND_POSITIVE
    assert decide_scores({"brand-new": weak}, THRESHOLDS)[0] == config.BAND_REVIEW


def test_normalize_anchors_thresholds_on_the_shared_scale():
    weak, strong = THRESHOLDS["sift"]
    assert normalize(0.0, weak, strong) == 0.0
    assert normalize(weak, weak, strong) == pytest.approx(config.REVIEW_THRESHOLD)
    assert normalize(strong, weak, strong) == pytest.approx(config.POSITIVE_THRESHOLD)
    assert normalize(1.0, weak, strong) == pytest.approx(1.0)


def test_normalize_is_monotonic_and_bounded():
    weak, strong = THRESHOLDS["ocr"]
    values = [normalize(i / 100, weak, strong) for i in range(101)]
    assert values == sorted(values)
    assert all(0.0 <= value <= 1.0 for value in values)


def test_degenerate_thresholds_do_not_explode():
    assert normalize(0.0, 0.0, 0.0) == pytest.approx(config.POSITIVE_THRESHOLD)
    assert normalize(1.0, 1.0, 1.0) == pytest.approx(config.POSITIVE_THRESHOLD)
    assert normalize(0.0, 0.0, 1.0) == pytest.approx(config.REVIEW_THRESHOLD)


def test_confidence_and_band_never_disagree():
    for score in (0.0, 0.04, 0.05, 0.4, 0.64, 0.65, 0.9, 1.0):
        band, confidence, _ = decide_scores({"sift": score}, THRESHOLDS)
        assert config.band_for(confidence) == band


def test_no_signals_means_a_clean_negative():
    decision = decide([])
    assert decision.confidence == 0.0
    assert decision.band == config.BAND_NEGATIVE
    assert decision.method == "none"
    assert decision.bbox is None
    assert decision.contains_logo is False
    assert decision.detail == "no signals enabled"


def test_a_negative_decision_reports_no_method_and_no_box():
    decision = decide(
        [SignalResult("ocr", 0.0, (1, 2, 3, 4), "no brand text")], THRESHOLDS
    )
    assert (decision.method, decision.bbox) == ("none", None)
    assert decision.band == config.BAND_NEGATIVE
    assert decision.detail == "no brand text"


def test_the_decision_keeps_a_box_from_any_winning_signal():
    decision = decide(
        [
            SignalResult("sift", 1.00, None, "matched but unlocalised"),
            SignalResult("ocr", 0.96, (5, 6, 70, 8), "read ZPE"),
        ],
        THRESHOLDS,
    )
    assert decision.method == "sift+ocr"
    assert decision.bbox == (5, 6, 70, 8)
    assert decision.detail == "matched but unlocalised"  # strongest winner's trace


def test_only_the_positive_band_sets_contains_logo():
    assert decide([SignalResult("ocr", 0.95)], THRESHOLDS).contains_logo is True
    assert decide([SignalResult("ocr", 0.60)], THRESHOLDS).contains_logo is False
    assert decide([SignalResult("ocr", 0.10)], THRESHOLDS).contains_logo is False


def test_to_row_carries_box_band_and_method_into_the_csv_schema():
    row = decide([SignalResult("ocr", 0.99, (5, 6, 70, 8))], THRESHOLDS).to_row("sub/img.png")
    assert (row.filename, row.method, row.contains_logo) == ("sub/img.png", "ocr", True)
    assert (row.x, row.y, row.w, row.h) == (5, 6, 70, 8)
    assert row.band == config.BAND_POSITIVE and row.error == ""


def test_to_row_leaves_the_box_empty_when_the_signal_cannot_localise():
    row = decide([SignalResult("ocr", 0.99)], THRESHOLDS).to_row("img.png")
    assert (row.x, row.y, row.w, row.h) == (None, None, None, None)


def test_the_live_config_thresholds_are_used_by_default():
    weak, strong = config.SIGNAL_THRESHOLDS["ocr"]
    assert decide([SignalResult("ocr", strong)]).band == config.BAND_POSITIVE
    assert decide([SignalResult("ocr", weak)]).band == config.BAND_REVIEW
    assert decide([SignalResult("ocr", weak - 0.01)]).band == config.BAND_NEGATIVE
