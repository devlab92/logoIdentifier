"""Shared signal contract and the registry the pipeline iterates.

A *signal* is any detector that looks at one BGR image and returns a
`SignalResult` scored in [0, 1]. Signals never decide bands - that is the
pipeline's job (phase04 calibrates the thresholds) - they only report how
strongly they saw the brand and where.

Signals are registered by name so `config.ENABLED_SIGNALS` and
`benchmark --signals ocr,sift` can select them as plain strings, keeping the
decision layer pluggable (see ARCHITECTURE "Key principles").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

import numpy as np

BBox = tuple[int, int, int, int]  # x, y, w, h in pixels of the analysed image


@dataclass(frozen=True)
class SignalResult:
    """One signal's verdict on one image.

    `score` is always clamped to [0, 1]; `bbox` is the best match box or None
    when the signal found nothing (or cannot localise); `detail` is a short
    human-readable trace that ends up in reports and benchmark output.
    """

    name: str
    score: float
    bbox: BBox | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        score = float(self.score)
        if not 0.0 <= score <= 1.0:
            object.__setattr__(self, "score", min(1.0, max(0.0, score)))
        else:
            object.__setattr__(self, "score", score)
        if self.bbox is not None:
            object.__setattr__(self, "bbox", tuple(int(v) for v in self.bbox))


class Signal(Protocol):
    """What the pipeline needs from a detector."""

    name: str

    def run(self, image: np.ndarray) -> SignalResult: ...


_REGISTRY: dict[str, Callable[[], Signal]] = {}


def register(name: str) -> Callable[[Callable[[], Signal]], Callable[[], Signal]]:
    """Decorate a zero-argument factory to publish it under `name`."""

    def decorator(factory: Callable[[], Signal]) -> Callable[[], Signal]:
        if name in _REGISTRY:
            raise ValueError(f"signal already registered: {name}")
        _REGISTRY[name] = factory
        return factory

    return decorator


def available() -> tuple[str, ...]:
    """Registered signal names, sorted."""
    _load_builtins()
    return tuple(sorted(_REGISTRY))


def build(name: str) -> Signal:
    """Instantiate one signal by name (engines stay lazy until first `run`)."""
    _load_builtins()
    try:
        factory = _REGISTRY[name]
    except KeyError:
        raise KeyError(f"unknown signal {name!r}; available: {', '.join(available())}") from None
    return factory()


def build_all(names: Iterable) -> list[Signal]:
    """Instantiate signals in the given order, rejecting unknown names.

    Already-built signal objects pass through untouched, which is how tests and
    experiments inject a stub without polluting the global registry.
    """
    return [build(item) if isinstance(item, str) else item for item in names]


def _load_builtins() -> None:
    """Import the modules that register the built-in signals.

    Done lazily and inside the function to keep `signals` import-cheap and to
    avoid a circular import (`ocr` imports `SignalResult` from here).
    """
    if _REGISTRY:
        return
    from logoscanner import ocr  # noqa: F401  (import registers "ocr")
    from logoscanner import keypoints  # noqa: F401  (import registers "sift")
