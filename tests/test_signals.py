"""Signal contract and registry."""

from __future__ import annotations

import numpy as np
import pytest

from logoscanner import signals
from logoscanner.signals import SignalResult, available, build, build_all


class StubSignal:
    name = "stub"

    def __init__(self, score: float = 0.5):
        self.score = score

    def run(self, image: np.ndarray) -> SignalResult:
        return SignalResult(self.name, self.score)


def test_score_is_clamped_to_unit_interval():
    assert SignalResult("s", 1.4).score == 1.0
    assert SignalResult("s", -0.2).score == 0.0
    assert SignalResult("s", 0.42).score == pytest.approx(0.42)


def test_bbox_is_coerced_to_ints_and_stays_optional():
    assert SignalResult("s", 0.1, (1.7, 2.2, 30.9, 9.5)).bbox == (1, 2, 30, 9)
    assert SignalResult("s", 0.1).bbox is None


def test_ocr_is_registered_and_builds_lazily():
    assert "ocr" in available()
    signal = build("ocr")
    assert signal.name == "ocr"  # engine not touched yet


def test_unknown_signal_name_is_rejected():
    with pytest.raises(KeyError):
        build("does-not-exist")


def test_registering_a_duplicate_name_fails():
    with pytest.raises(ValueError):
        signals.register("ocr")(lambda: StubSignal())


def test_build_all_mixes_names_and_instances():
    stub = StubSignal()
    built = build_all(["ocr", stub])
    assert [s.name for s in built] == ["ocr", "stub"]
    assert built[1] is stub  # instances pass through untouched
