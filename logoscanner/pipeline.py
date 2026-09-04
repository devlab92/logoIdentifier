"""Runs the enabled signals over one image and hands them to the decision engine.

The pipeline exists to hold instantiated signals so their engines load once per
process; banding lives in `decision.decide` (per-signal calibrated thresholds,
OR rule over the bands they claim). `Decision` and `decide` are re-exported here
because callers think of them as "what the pipeline returned".
"""

from __future__ import annotations

import numpy as np

from logoscanner import config
from logoscanner.decision import Decision, decide  # noqa: F401  (re-exported)
from logoscanner.signals import Signal, build_all


class Pipeline:
    """Holds instantiated signals so their engines load once per process."""

    def __init__(self, signals: list[Signal]):
        self.signals = signals

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(signal.name for signal in self.signals)

    def run(self, image: np.ndarray) -> Decision:
        """Score `image` with every signal and band the result."""
        return decide(tuple(signal.run(image) for signal in self.signals))


def build_pipeline(names=None) -> Pipeline:
    """Build the pipeline for `names` (default `config.ENABLED_SIGNALS`)."""
    return Pipeline(build_all(config.ENABLED_SIGNALS if names is None else names))
