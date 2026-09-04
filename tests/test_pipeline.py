"""Signal orchestration and the OR decision rule."""

from __future__ import annotations

import numpy as np

from logoscanner import config
from logoscanner.pipeline import Pipeline, build_pipeline, decide
from logoscanner.signals import SignalResult


class StubSignal:
    def __init__(self, name: str, score: float, bbox=None):
        self.name = name
        self.result = SignalResult(name, score, bbox, f"stub {score}")

    def run(self, image):
        return self.result


BLANK = np.zeros((8, 8, 3), dtype=np.uint8)


def test_no_signals_means_a_clean_negative():
    decision = decide([])
    assert decision.confidence == 0.0
    assert decision.band == config.BAND_NEGATIVE
    assert decision.method == "none"
    assert decision.bbox is None
    assert decision.contains_logo is False


def test_strongest_signal_wins_and_is_not_diluted_by_silent_ones():
    decision = decide([
        SignalResult("quiet", 0.0),
        SignalResult("loud", 0.95, (1, 2, 3, 4), "found it"),
        SignalResult("meh", 0.2),
    ])
    assert decision.method == "loud"
    assert decision.confidence == 0.95
    assert decision.bbox == (1, 2, 3, 4)
    assert decision.detail == "found it"
    assert len(decision.results) == 3


def test_all_zero_scores_report_no_method():
    decision = decide([SignalResult("ocr", 0.0, None, "no brand text")])
    assert decision.method == "none"
    assert decision.band == config.BAND_NEGATIVE
    assert decision.detail == "no brand text"


def test_bands_follow_the_config_thresholds():
    assert decide([SignalResult("s", config.POSITIVE_THRESHOLD)]).band == config.BAND_POSITIVE
    assert decide([SignalResult("s", config.REVIEW_THRESHOLD)]).band == config.BAND_REVIEW
    below = config.REVIEW_THRESHOLD - 0.01
    assert decide([SignalResult("s", below)]).band == config.BAND_NEGATIVE


def test_only_the_positive_band_sets_contains_logo():
    assert decide([SignalResult("s", 1.0)]).contains_logo is True
    assert decide([SignalResult("s", config.REVIEW_THRESHOLD)]).contains_logo is False


def test_to_row_carries_box_and_method_into_the_csv_schema():
    row = decide([SignalResult("ocr", 0.9, (5, 6, 70, 8))]).to_row("sub/img.png")
    assert (row.filename, row.method, row.contains_logo) == ("sub/img.png", "ocr", True)
    assert (row.x, row.y, row.w, row.h) == (5, 6, 70, 8)
    assert row.error == ""


def test_to_row_leaves_the_box_empty_when_the_signal_cannot_localise():
    row = decide([SignalResult("ocr", 0.9)]).to_row("img.png")
    assert (row.x, row.y, row.w, row.h) == (None, None, None, None)


def test_pipeline_runs_every_signal():
    pipeline = Pipeline([StubSignal("a", 0.1), StubSignal("b", 0.7, (0, 0, 2, 2))])
    assert pipeline.names == ("a", "b")
    decision = pipeline.run(BLANK)
    assert decision.method == "b" and decision.confidence == 0.7


def test_build_pipeline_defaults_to_the_configured_signals():
    assert build_pipeline().names == tuple(config.ENABLED_SIGNALS)
    assert build_pipeline([]).names == ()
