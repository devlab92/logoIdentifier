"""Measure per-signal quality on a labeled folder and sweep the band thresholds.

Input layout is the dataset protocol (`data/labeled/positive|negative`). Every
image is loaded once and scored by every requested signal, then each signal's
score distribution is swept over a coarse grid of (review, positive) threshold
pairs. The chosen operating point is *recall-first* (D-014): maximise
catch-recall (positives landing in positive OR review), and only then prefer
precision and a smaller review pile.

phase04 replaces this manual read with real calibration; phase02 only needs the
numbers on the table.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from tqdm import tqdm

from logoscanner import config
from logoscanner.io_utils import iter_images, load_image
from logoscanner.signals import build_all

CLASS_DIRS = ("positive", "negative")
# Coarse grid, 0.05 steps. Fine enough to see the shape, cheap enough to print.
GRID = tuple(round(0.05 * i, 2) for i in range(1, 20))


@dataclass
class SignalScores:
    """One signal's scores over the labeled set."""

    name: str
    positive: list[float] = field(default_factory=list)
    negative: list[float] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def images(self) -> int:
        return len(self.positive) + len(self.negative)


@dataclass
class Point:
    """Metrics for one (review, positive) threshold pair."""

    review_threshold: float
    positive_threshold: float
    precision: float  # of the positive band
    catch_recall: float  # positives landing in positive OR review
    review_share: float  # share of ALL images a human must eyeball
    missed: int  # positives falling into negative - the costly error

    @property
    def rank_key(self) -> tuple[float, float, float]:
        """Recall first, then precision, then a smaller review pile."""
        return (self.catch_recall, self.precision, -self.review_share)


def score_labeled(
    labeled_dir: str | Path,
    signal_names,
    limit: int | None = None,
    progress: bool = True,
) -> tuple[dict[str, SignalScores], dict]:
    """Score `positive/` and `negative/` with each signal; return scores + meta.

    Images are loaded once and shown to every signal, so adding a signal costs
    only that signal's own time.
    """
    labeled_dir = Path(labeled_dir)
    signals = build_all(signal_names)
    names = tuple(signal.name for signal in signals)
    scores = {name: SignalScores(name) for name in names}

    jobs: list[tuple[Path, str]] = []
    for label in CLASS_DIRS:
        paths = list(iter_images(labeled_dir / label))
        if limit is not None:
            paths = paths[:limit]
        jobs.extend((path, label) for path in paths)

    errors: list[str] = []
    start = time.perf_counter()
    for path, label in tqdm(jobs, desc="benchmark", unit="img", disable=not progress):
        image, error = load_image(path)
        if error:
            errors.append(f"{path.name}: {error}")
            continue
        for signal in signals:
            signal_start = time.perf_counter()
            result = signal.run(image)
            entry = scores[signal.name]
            entry.seconds += time.perf_counter() - signal_start
            getattr(entry, label).append(result.score)
    seconds = time.perf_counter() - start

    scored = len(jobs) - len(errors)
    first = scores[names[0]] if names else None
    meta = {
        "labeled": str(labeled_dir),
        "signals": list(names),
        "images": scored,
        "positives": len(first.positive) if first else 0,
        "negatives": len(first.negative) if first else 0,
        "errors": errors,
        "seconds": seconds,
        "images_per_second": scored / seconds if seconds > 0 else 0.0,
    }
    return scores, meta


def evaluate(scores: SignalScores, review_threshold: float, positive_threshold: float) -> Point:
    """Metrics for one threshold pair on one signal's score distribution."""
    positives, negatives = scores.positive, scores.negative
    n_pos, n_all = len(positives), len(positives) + len(negatives)

    true_positive = sum(1 for s in positives if s >= positive_threshold)
    false_positive = sum(1 for s in negatives if s >= positive_threshold)
    flagged = true_positive + false_positive
    caught = sum(1 for s in positives if s >= review_threshold)
    in_review = sum(
        1 for s in positives + negatives if review_threshold <= s < positive_threshold
    )
    return Point(
        review_threshold=review_threshold,
        positive_threshold=positive_threshold,
        precision=true_positive / flagged if flagged else 0.0,
        catch_recall=caught / n_pos if n_pos else 0.0,
        review_share=in_review / n_all if n_all else 0.0,
        missed=n_pos - caught,
    )


def sweep(scores: SignalScores, grid=GRID) -> list[Point]:
    """Every (review <= positive) pair on the grid."""
    return [
        evaluate(scores, review, positive)
        for review in grid
        for positive in grid
        if positive >= review
    ]


def best_point(points) -> Point | None:
    """Recall-first pick among swept points."""
    points = list(points)
    return max(points, key=lambda p: p.rank_key) if points else None


def format_report(scores: SignalScores, best: Point | None) -> str:
    """Human-readable block: cost, single-threshold sweep, best pair."""
    lines = [f"signal: {scores.name}"]
    lines.append(
        f"  images   : {scores.images} "
        f"({len(scores.positive)} positive / {len(scores.negative)} negative)"
    )
    if scores.seconds:
        lines.append(
            f"  cost     : {scores.seconds:.1f} s "
            f"({scores.images / scores.seconds:.2f} img/s for this signal)"
        )
    lines.append("  threshold  pos>=t  neg>=t  recall  precision")
    for threshold in GRID:
        hit_pos = sum(1 for s in scores.positive if s >= threshold)
        hit_neg = sum(1 for s in scores.negative if s >= threshold)
        recall = hit_pos / len(scores.positive) if scores.positive else 0.0
        precision = hit_pos / (hit_pos + hit_neg) if (hit_pos + hit_neg) else 0.0
        lines.append(
            f"  {threshold:>9.2f}  {hit_pos:>6d}  {hit_neg:>6d}  "
            f"{recall:>6.3f}  {precision:>9.3f}"
        )
    if best is not None:
        lines.append(
            f"  best pair: review>={best.review_threshold:.2f} "
            f"positive>={best.positive_threshold:.2f} -> "
            f"precision={best.precision:.3f} catch-recall={best.catch_recall:.3f} "
            f"review-share={best.review_share:.3f} missed={best.missed}"
        )
    return "\n".join(lines)


def benchmark_row(
    signal_name: str,
    scores: SignalScores,
    best: Point | None,
    phase: str = "phase02",
    note: str = "",
) -> str:
    """One markdown table row for docs/BENCHMARKS.md."""
    rate = scores.images / scores.seconds if scores.seconds else 0.0
    precision = f"{best.precision:.3f}" if best else "n/a"
    catch = f"{best.catch_recall:.3f}" if best else "n/a"
    review = f"{best.review_share * 100:.1f}%" if best else "n/a"
    thresholds = (
        f"t_rev={best.review_threshold:.2f} t_pos={best.positive_threshold:.2f}"
        if best
        else ""
    )
    detail = "; ".join(part for part in (thresholds, note) if part)
    return (
        f"| {date.today().isoformat()} | {phase} | "
        f"{len(scores.positive)}/{len(scores.negative)} | {signal_name} | "
        f"{precision} | {catch} | {review} | {rate:.2f} | {detail} |"
    )


def append_rows(rows, path: str | Path = "docs/BENCHMARKS.md") -> Path:
    """Append markdown rows to the benchmarks table (append-only file)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def run_benchmark(
    labeled_dir: str | Path,
    signal_names=None,
    limit: int | None = None,
    progress: bool = True,
    write_docs: bool = True,
    docs_path: str | Path = "docs/BENCHMARKS.md",
    note: str = "",
) -> dict:
    """Score, sweep, print and (optionally) record. Returns a summary dict."""
    scores, meta = score_labeled(
        labeled_dir, signal_names or config.ENABLED_SIGNALS, limit=limit, progress=progress
    )

    rows, summary = [], {}
    for name in meta["signals"]:
        entry = scores[name]
        best = best_point(sweep(entry))
        print()
        print(format_report(entry, best))
        rows.append(benchmark_row(name, entry, best, note=note))
        summary[name] = {
            "images": entry.images,
            "seconds": round(entry.seconds, 3),
            "best": None
            if best is None
            else {
                "review_threshold": best.review_threshold,
                "positive_threshold": best.positive_threshold,
                "precision": round(best.precision, 4),
                "catch_recall": round(best.catch_recall, 4),
                "review_share": round(best.review_share, 4),
                "missed": best.missed,
            },
        }

    if meta["errors"]:
        print(f"\nunreadable: {len(meta['errors'])} file(s)")
        for line in meta["errors"][:10]:
            print(f"  {line}")
    if write_docs and rows:
        append_rows(rows, docs_path)
        print(f"\nappended {len(rows)} row(s) to {docs_path}")
    return {"meta": meta, "signals": summary, "rows": rows}
