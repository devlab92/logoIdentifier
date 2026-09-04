"""Quality metrics for the decision engine on a labeled folder.

Layout is the dataset protocol (`data/labeled/positive|negative`). Scoring and
judging are deliberately separate: `score_images` runs the signals once and
keeps every image's raw per-signal scores, then `evaluate` bands those scores
with any threshold set. That is what makes calibration cheap - the expensive
OCR/SIFT pass happens once and thousands of candidate thresholds are judged on
the stored numbers.

The metric that matters is **catch-recall** (D-014): positives landing in
`positive` OR `review`, i.e. what a human would still see. Precision is
measured on the `positive` band alone, and review share counts *all* images a
human must eyeball.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from tqdm import tqdm

from logoscanner import config
from logoscanner.decision import Thresholds, decide_scores
from logoscanner.io_utils import iter_images, load_image
from logoscanner.signals import build_all

CLASS_DIRS = ("positive", "negative")


@dataclass(frozen=True)
class ScoredImage:
    """One labeled image and what every signal scored on it."""

    filename: str
    label: str  # "positive" | "negative"
    scores: dict[str, float]


@dataclass
class Metrics:
    """Decision quality for one threshold set on one labeled dataset."""

    precision: float = 0.0  # of the positive band
    catch_recall: float = 0.0  # positives landing in positive OR review
    review_share: float = 0.0  # share of ALL images a human must eyeball
    images: int = 0
    positives: int = 0
    negatives: int = 0
    counts: dict[str, dict[str, int]] = field(default_factory=dict)  # label -> band -> n
    wins: dict[str, int] = field(default_factory=dict)  # signal -> images it decided
    false_negatives: list[str] = field(default_factory=list)  # the costly error
    false_positives: list[str] = field(default_factory=list)  # positive band, wrong

    @property
    def missed(self) -> int:
        return len(self.false_negatives)

    def as_dict(self) -> dict:
        """JSON-ready view (rounded, file lists sorted)."""
        return {
            "precision": round(self.precision, 4),
            "catch_recall": round(self.catch_recall, 4),
            "review_share": round(self.review_share, 4),
            "images": self.images,
            "positives": self.positives,
            "negatives": self.negatives,
            "counts": self.counts,
            "wins": self.wins,
            "missed": self.missed,
            "false_negatives": sorted(self.false_negatives),
            "false_positives": sorted(self.false_positives),
        }


def score_images(
    labeled_dir: str | Path,
    signal_names,
    limit: int | None = None,
    progress: bool = True,
) -> tuple[list[ScoredImage], dict]:
    """Run every signal over `positive/` + `negative/`, keeping per-file scores.

    Images are loaded once and shown to every signal, so adding a signal costs
    only that signal's own time. Unreadable files are collected in the meta
    rather than raised.
    """
    labeled_dir = Path(labeled_dir)
    signals = build_all(signal_names)
    names = tuple(signal.name for signal in signals)

    jobs: list[tuple[Path, str]] = []
    for label in CLASS_DIRS:
        paths = list(iter_images(labeled_dir / label))
        if limit is not None:
            paths = paths[:limit]
        jobs.extend((path, label) for path in paths)

    records: list[ScoredImage] = []
    errors: list[str] = []
    signal_seconds = {name: 0.0 for name in names}
    start = time.perf_counter()
    for path, label in tqdm(jobs, desc="scoring", unit="img", disable=not progress):
        image, error = load_image(path)
        if error:
            errors.append(f"{path.name}: {error}")
            continue
        scores: dict[str, float] = {}
        for signal in signals:
            signal_start = time.perf_counter()
            scores[signal.name] = signal.run(image).score
            signal_seconds[signal.name] += time.perf_counter() - signal_start
        records.append(ScoredImage(filename=path.name, label=label, scores=scores))
    seconds = time.perf_counter() - start

    meta = {
        "labeled": str(labeled_dir),
        "signals": list(names),
        "images": len(records),
        "positives": sum(1 for r in records if r.label == "positive"),
        "negatives": sum(1 for r in records if r.label == "negative"),
        "errors": errors,
        "seconds": seconds,
        "signal_seconds": signal_seconds,
        "images_per_second": len(records) / seconds if seconds > 0 else 0.0,
    }
    return records, meta


def evaluate(records, thresholds: Thresholds | None = None) -> Metrics:
    """Band every record with `thresholds` and summarise the outcome."""
    records = list(records)
    metrics = Metrics(
        images=len(records),
        positives=sum(1 for r in records if r.label == "positive"),
        negatives=sum(1 for r in records if r.label == "negative"),
        counts={label: {band: 0 for band in config.BANDS} for label in CLASS_DIRS},
    )

    flagged = caught = in_review = 0
    for record in records:
        band, _, winners = decide_scores(record.scores, thresholds)
        metrics.counts.setdefault(record.label, {band: 0 for band in config.BANDS})
        metrics.counts[record.label][band] += 1
        if band != config.BAND_NEGATIVE and winners:
            # The signal that set the band; ties broken by normalized score.
            metrics.wins[winners[0]] = metrics.wins.get(winners[0], 0) + 1
        if band == config.BAND_REVIEW:
            in_review += 1
        if band == config.BAND_POSITIVE:
            flagged += 1
            if record.label != "positive":
                metrics.false_positives.append(record.filename)
        if record.label == "positive":
            if band == config.BAND_NEGATIVE:
                metrics.false_negatives.append(record.filename)
            else:
                caught += 1

    true_positive = metrics.counts["positive"][config.BAND_POSITIVE]
    metrics.precision = true_positive / flagged if flagged else 0.0
    metrics.catch_recall = caught / metrics.positives if metrics.positives else 0.0
    metrics.review_share = in_review / metrics.images if metrics.images else 0.0
    return metrics


def format_metrics(metrics: Metrics, thresholds: Thresholds | None = None) -> str:
    """Human-readable block for the CLI."""
    table = config.SIGNAL_THRESHOLDS if thresholds is None else thresholds
    lines = [
        f"images       : {metrics.images} "
        f"({metrics.positives} positive / {metrics.negatives} negative)",
        "thresholds   : "
        + "  ".join(
            f"{name} weak>={weak:.2f} strong>={strong:.2f}"
            for name, (weak, strong) in sorted(table.items())
        ),
        f"precision    : {metrics.precision:.3f}  (positive band)",
        f"catch-recall : {metrics.catch_recall:.3f}  (positive + review)",
        f"review share : {metrics.review_share * 100:.1f}%  of all images",
        f"missed       : {metrics.missed} positive(s) banded negative",
        "confusion    : label -> " + " / ".join(config.BANDS),
    ]
    for label in CLASS_DIRS:
        row = metrics.counts.get(label, {})
        lines.append(
            f"  {label:<8} : " + " / ".join(str(row.get(band, 0)) for band in config.BANDS)
        )
    if metrics.wins:
        lines.append(
            "signal wins  : "
            + "  ".join(f"{name}={count}" for name, count in sorted(metrics.wins.items()))
        )
    if metrics.false_negatives:
        lines.append("false negatives:")
        for name in sorted(metrics.false_negatives):
            lines.append(f"  {name}")
    return "\n".join(lines)
