"""Runs the enabled signals over one image and turns them into a decision.

The decision is deliberately an OR rule over signals (D-003): the strongest
single signal wins, so one conclusive detector cannot be diluted by silent
ones. Banding uses `config.band_for`; the thresholds behind it are provisional
until phase04 calibrates them on the labeled set.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from logoscanner import config
from logoscanner.results import ResultRow
from logoscanner.signals import Signal, SignalResult, build_all


@dataclass(frozen=True)
class Decision:
    """The pipeline's verdict for one image, plus every signal's raw output."""

    confidence: float
    band: str
    method: str
    bbox: tuple[int, int, int, int] | None
    detail: str
    results: tuple[SignalResult, ...]

    @property
    def contains_logo(self) -> bool:
        """True for the positive band only; review is 'look at this yourself'."""
        return self.band == config.BAND_POSITIVE

    def to_row(self, filename: str) -> ResultRow:
        """Render as the CSV row for this image."""
        x, y, w, h = self.bbox if self.bbox else (None, None, None, None)
        return ResultRow(
            filename=filename,
            contains_logo=self.contains_logo,
            band=self.band,
            confidence=self.confidence,
            x=x, y=y, w=w, h=h,
            method=self.method,
        )


class Pipeline:
    """Holds instantiated signals so their engines load once per process."""

    def __init__(self, signals: list[Signal]):
        self.signals = signals

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(signal.name for signal in self.signals)

    def run(self, image: np.ndarray) -> Decision:
        """Score `image` with every signal and pick the strongest."""
        results = tuple(signal.run(image) for signal in self.signals)
        return decide(results)


def build_pipeline(names=None) -> Pipeline:
    """Build the pipeline for `names` (default `config.ENABLED_SIGNALS`)."""
    return Pipeline(build_all(config.ENABLED_SIGNALS if names is None else names))


def decide(results) -> Decision:
    """OR rule: the highest-scoring signal decides confidence, box and band."""
    results = tuple(results)
    best = max(results, key=lambda r: r.score, default=None)
    if best is None or best.score <= 0.0:
        return Decision(
            confidence=0.0,
            band=config.BAND_NEGATIVE,
            method="none",
            bbox=None,
            detail=best.detail if best else "no signals enabled",
            results=results,
        )
    return Decision(
        confidence=best.score,
        band=config.band_for(best.score),
        method=best.name,
        bbox=best.bbox,
        detail=best.detail,
        results=results,
    )
