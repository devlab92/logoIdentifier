"""Signal orchestration. The banding rules themselves live in test_decision.py."""

from __future__ import annotations

import numpy as np

from logoscanner import config
from logoscanner.pipeline import Decision, Pipeline, build_pipeline, decide
from logoscanner.signals import SignalResult


class StubSignal:
    def __init__(self, name: str, score: float, bbox=None):
        self.name = name
        self.result = SignalResult(name, score, bbox, f"stub {score}")

    def run(self, image):
        return self.result


BLANK = np.zeros((8, 8, 3), dtype=np.uint8)


def test_pipeline_runs_every_signal_and_returns_a_decision():
    strong = config.SIGNAL_THRESHOLDS["ocr"][1]
    pipeline = Pipeline([StubSignal("sift", 0.0), StubSignal("ocr", strong, (0, 0, 2, 2))])
    assert pipeline.names == ("sift", "ocr")

    decision = pipeline.run(BLANK)
    assert isinstance(decision, Decision)
    assert decision.method == "ocr"
    assert decision.band == config.BAND_POSITIVE
    assert decision.bbox == (0, 0, 2, 2)
    assert len(decision.results) == 2


def test_pipeline_reports_a_negative_when_nothing_fires():
    decision = Pipeline([StubSignal("ocr", 0.0), StubSignal("sift", 0.0)]).run(BLANK)
    assert decision.band == config.BAND_NEGATIVE
    assert decision.contains_logo is False


def test_build_pipeline_defaults_to_the_configured_signals():
    assert build_pipeline().names == tuple(config.ENABLED_SIGNALS)
    assert build_pipeline([]).names == ()


def test_decide_is_re_exported_for_callers_who_think_in_pipelines():
    from logoscanner import decision as decision_module

    assert decide is decision_module.decide
