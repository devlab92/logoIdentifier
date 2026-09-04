"""Rule-based decision engine: per-signal thresholds -> band + confidence.

Two thresholds per signal (D-021):

    score >= strong  -> this signal says `positive`
    score >= weak    -> this signal says `review`
    else             -> this signal says `negative`

The image takes the *best* band any signal claims (an OR rule, D-003), so one
conclusive detector is never diluted by silent ones. Raw scores are not
comparable across signals - OCR 0.6 and SIFT 0.6 mean different things - so the
reported `confidence` is each score *normalized* against its own thresholds:
weak lands on `config.REVIEW_THRESHOLD`, strong on `config.POSITIVE_THRESHOLD`,
piecewise-linear in between. The result is monotonic in the raw score and
comparable across signals; it is not a probability.

Thresholds live in `config.SIGNAL_THRESHOLDS` and are written there by
`logoscanner calibrate`. Every function accepts an explicit `thresholds`
override so calibration can evaluate candidates without touching the config.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from logoscanner import config
from logoscanner.results import ResultRow
from logoscanner.signals import SignalResult

Thresholds = Mapping[str, tuple[float, float]]  # signal -> (weak, strong)

# Band ordering used to pick the winner; higher wins.
_BAND_RANK = {
    config.BAND_NEGATIVE: 0,
    config.BAND_REVIEW: 1,
    config.BAND_POSITIVE: 2,
}


@dataclass(frozen=True)
class Decision:
    """The verdict for one image, plus every signal's raw output."""

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


def thresholds_for(name: str, thresholds: Thresholds | None = None) -> tuple[float, float]:
    """`(weak, strong)` for `name`, falling back to `config.FALLBACK_THRESHOLDS`."""
    table = config.SIGNAL_THRESHOLDS if thresholds is None else thresholds
    weak, strong = table.get(name, config.FALLBACK_THRESHOLDS)
    return float(weak), float(strong)


def band_of(score: float, weak: float, strong: float) -> str:
    """The band one signal claims at `score`."""
    if score >= strong:
        return config.BAND_POSITIVE
    if score >= weak:
        return config.BAND_REVIEW
    return config.BAND_NEGATIVE


def normalize(score: float, weak: float, strong: float) -> float:
    """Map a raw score onto the shared confidence scale (see module docstring).

    Monotonic and continuous: `weak` -> `REVIEW_THRESHOLD`, `strong` ->
    `POSITIVE_THRESHOLD`, 0 -> 0 and 1 -> 1. Degenerate spans (weak == 0,
    strong == weak, strong == 1) collapse to the anchor itself.
    """
    review, positive = config.REVIEW_THRESHOLD, config.POSITIVE_THRESHOLD
    if score >= strong:
        span = 1.0 - strong
        frac = (score - strong) / span if span > 0 else 0.0
        value = positive + (1.0 - positive) * frac
    elif score >= weak:
        span = strong - weak
        frac = (score - weak) / span if span > 0 else 0.0
        value = review + (positive - review) * frac
    else:
        frac = score / weak if weak > 0 else 0.0
        value = review * frac
    return min(1.0, max(0.0, value))


def decide_scores(
    scores: Mapping[str, float], thresholds: Thresholds | None = None
) -> tuple[str, float, tuple[str, ...]]:
    """`(band, confidence, winners)` from raw per-signal scores.

    `winners` are the signals claiming the winning band, strongest first; the
    confidence is the strongest winner's normalized score.
    """
    if not scores:
        return config.BAND_NEGATIVE, 0.0, ()
    ranked = []
    for name, score in scores.items():
        weak, strong = thresholds_for(name, thresholds)
        ranked.append((band_of(score, weak, strong), normalize(score, weak, strong), name))
    band = max(ranked, key=lambda item: _BAND_RANK[item[0]])[0]
    winners = sorted(
        (item for item in ranked if item[0] == band),
        key=lambda item: (-item[1], item[2]),
    )
    return band, winners[0][1], tuple(name for _, _, name in winners)


def decide(results, thresholds: Thresholds | None = None) -> Decision:
    """Band an image from its `SignalResult`s (the OR rule over per-signal bands)."""
    results = tuple(results)
    if not results:
        return Decision(
            confidence=0.0,
            band=config.BAND_NEGATIVE,
            method="none",
            bbox=None,
            detail="no signals enabled",
            results=results,
        )

    by_name = {result.name: result for result in results}
    band, confidence, winners = decide_scores(
        {name: result.score for name, result in by_name.items()}, thresholds
    )
    top = by_name[winners[0]]
    # A localised winner is worth more than a stronger blind one: keep the best
    # box any winning signal produced.
    bbox = next((by_name[name].bbox for name in winners if by_name[name].bbox), None)
    return Decision(
        confidence=confidence,
        band=band,
        method="+".join(winners) if band != config.BAND_NEGATIVE else "none",
        bbox=bbox if band != config.BAND_NEGATIVE else None,
        detail=top.detail,
        results=results,
    )
