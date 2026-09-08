"""Threshold calibration: pick the four numbers the decision engine runs on.

One scoring pass over the labeled set (`metrics.score_images`), then an
exhaustive grid search over every signal's `(weak, strong)` pair. The objective
is the phase04 contract:

    maximise precision  subject to  catch-recall >= TARGET_CATCH_RECALL
                                    review share <= TARGET_REVIEW_SHARE

ties broken by higher catch-recall, then smaller review pile. When no point on
the grid satisfies both constraints the search *relaxes the recall target to
what the scores can actually reach* (D-022) and reports `feasible=False`, which
is what fails the phase04 gate: a dataset whose positives score 0 on every
signal cannot be rescued by any threshold.

The search itself is vectorised (band vectors per candidate pair, elementwise
max across signals = the OR rule); the winner is then re-measured with the
ordinary `metrics.evaluate` path so the numbers that get published come from
the same code the scanner uses.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from itertools import product
from pathlib import Path

import numpy as np

from logoscanner import config
from logoscanner.metrics import Metrics, evaluate, format_metrics, score_images

EPS = 1e-9
CONFIG_PATH = Path("logoscanner/config.py")
CALIBRATION_PATH = Path("output/calibration.json")
GATE_FAILURES_PATH = Path("output/gate_failures.txt")

# Markers delimiting the block `apply_to_config` rewrites.
BLOCK_START = "# --- calibrated thresholds (written by `logoscanner calibrate`) ------------"
BLOCK_END = "# --- end calibrated thresholds ---------------------------------------------"


@dataclass(frozen=True)
class Candidate:
    """One threshold set and the metrics it produces."""

    thresholds: dict[str, tuple[float, float]]
    precision: float
    catch_recall: float
    review_share: float

    def feasible(
        self,
        target_recall: float = config.TARGET_CATCH_RECALL,
        target_review: float = config.TARGET_REVIEW_SHARE,
    ) -> bool:
        return (
            self.catch_recall >= target_recall - EPS
            and self.review_share <= target_review + EPS
        )


@dataclass
class SearchResult:
    """Outcome of the grid search."""

    best: Candidate | None
    feasible: bool  # the winner meets both targets
    attainable_recall: float  # best catch-recall anywhere on the grid
    evaluated: int
    relaxed_to: float | None = None  # recall target actually used, when relaxed
    grid: tuple[float, ...] = field(default_factory=tuple)


def pair_grid(grid=config.CALIBRATION_GRID) -> list[tuple[float, float]]:
    """Every `(weak, strong)` pair on the grid with `strong >= weak`."""
    return [(weak, strong) for weak in grid for strong in grid if strong >= weak]


def _band_matrix(scores: np.ndarray, pairs) -> np.ndarray:
    """`(len(pairs), len(scores))` band codes: 0 negative, 1 review, 2 positive."""
    weak = np.array([pair[0] for pair in pairs], dtype=float)[:, None]
    strong = np.array([pair[1] for pair in pairs], dtype=float)[:, None]
    row = scores[None, :]
    return (row >= weak - EPS).astype(np.int8) + (row >= strong - EPS).astype(np.int8)


def search(
    records,
    signal_names=None,
    grid=config.CALIBRATION_GRID,
    target_recall: float = config.TARGET_CATCH_RECALL,
    target_review: float = config.TARGET_REVIEW_SHARE,
) -> SearchResult:
    """Grid-search every signal's `(weak, strong)` pair; return the winner."""
    records = list(records)
    if signal_names is None:
        signal_names = tuple(records[0].scores) if records else ()
    signal_names = tuple(signal_names)
    if not records or not signal_names:
        return SearchResult(None, False, 0.0, 0, grid=tuple(grid))

    is_positive = np.array([r.label == "positive" for r in records])
    n_positive = int(is_positive.sum())
    n_images = len(records)
    pairs = pair_grid(grid)
    matrices = [
        _band_matrix(
            np.array([r.scores.get(name, 0.0) for r in records], dtype=float), pairs
        )
        for name in signal_names
    ]

    # Fold every signal but the last into one band vector, then let the last
    # signal's whole pair matrix broadcast against it.
    # Results are kept as three flat float32 vectors, one entry per threshold
    # combination, and the combination *index* is decoded arithmetically at the
    # end. Materialising the index as a list of tuples costs ~1 GB once a third
    # signal takes the grid to 9.3 M combinations (D-027).
    head, tail = matrices[:-1], matrices[-1]
    precision_all, catch_all, review_all = [], [], []
    for head_index in product(range(len(pairs)), repeat=len(head)):
        base = np.zeros(n_images, dtype=np.int8)
        for matrix, index in zip(head, head_index):
            np.maximum(base, matrix[index], out=base)
        bands = np.maximum(tail, base[None, :])

        positive_band = bands == 2
        flagged = positive_band.sum(axis=1)
        true_positive = (positive_band & is_positive[None, :]).sum(axis=1)
        caught = ((bands >= 1) & is_positive[None, :]).sum(axis=1)
        in_review = (bands == 1).sum(axis=1)

        with np.errstate(invalid="ignore", divide="ignore"):
            precision = np.where(flagged > 0, true_positive / np.maximum(flagged, 1), 0.0)
        precision_all.append(precision.astype(np.float32))
        catch_all.append(
            (caught / n_positive if n_positive else np.zeros(len(pairs))).astype(np.float32)
        )
        review_all.append((in_review / n_images).astype(np.float32))

    precision = np.concatenate(precision_all)
    catch = np.concatenate(catch_all)
    review = np.concatenate(review_all)
    attainable = float(catch.max())

    feasible_mask = (catch >= target_recall - EPS) & (review <= target_review + EPS)
    relaxed_to = None
    if feasible_mask.any():
        mask = feasible_mask
    else:
        # Nothing meets the recall target. Keep the review-share cap and aim at
        # the best recall the scores allow (D-022).
        under_cap = review <= target_review + EPS
        if under_cap.any():
            relaxed_to = float(catch[under_cap].max())
            mask = under_cap & (catch >= relaxed_to - EPS)
        else:  # not even the review cap is reachable: recall first, as always
            relaxed_to = attainable
            mask = catch >= attainable - EPS

    indices = np.flatnonzero(mask)
    # maximise precision, then catch-recall, then the smaller review pile
    # (np.lexsort's last key is the primary one; the winner is the last row)
    order = np.lexsort((-review[indices], catch[indices], precision[indices]))
    winner = int(indices[order[-1]])
    # Decode the flat index: each head combination contributes len(pairs)
    # entries, laid out in `product(...)` order.
    block, tail_index = divmod(winner, len(pairs))
    head_index = (
        tuple(int(i) for i in np.unravel_index(block, (len(pairs),) * len(head)))
        if head
        else ()
    )
    thresholds = {
        name: pairs[index]
        for name, index in zip(signal_names, tuple(head_index) + (tail_index,))
    }
    best = Candidate(
        thresholds=thresholds,
        precision=float(precision[winner]),
        catch_recall=float(catch[winner]),
        review_share=float(review[winner]),
    )
    return SearchResult(
        best=best,
        feasible=bool(feasible_mask.any()) and best.feasible(target_recall, target_review),
        attainable_recall=attainable,
        evaluated=int(catch.size),
        relaxed_to=relaxed_to,
        grid=tuple(grid),
    )


def render_thresholds_block(thresholds, stamp: str | None = None) -> str:
    """The `SIGNAL_THRESHOLDS` source block, markers included."""
    stamp = stamp or date.today().isoformat()
    lines = [
        BLOCK_START,
        f"# Calibrated on the labeled set, {stamp}.",
        "SIGNAL_THRESHOLDS: dict[str, tuple[float, float]] = {",
        "    # signal: (weak, strong)",
    ]
    for name, (weak, strong) in sorted(thresholds.items()):
        lines.append(f'    "{name}": ({weak:.2f}, {strong:.2f}),')
    lines.append("}")
    lines.append(BLOCK_END)
    return "\n".join(lines)


def apply_to_config(thresholds, path: str | Path = CONFIG_PATH, stamp: str | None = None) -> Path:
    """Rewrite the calibrated-thresholds block in `config.py` in place."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(BLOCK_START) + ".*?" + re.escape(BLOCK_END), re.DOTALL
    )
    if not pattern.search(text):
        raise ValueError(f"calibrated-thresholds markers not found in {path}")
    path.write_text(
        pattern.sub(lambda _: render_thresholds_block(thresholds, stamp), text),
        encoding="utf-8",
    )
    return path


def miss_reason(record, thresholds) -> str:
    """Why this positive was banded negative, from its own signal scores."""
    scores = {name: record.scores.get(name, 0.0) for name in sorted(record.scores)}
    detail = " ".join(f"{name}={score:.2f}" for name, score in scores.items())
    if all(score <= 0.0 for score in scores.values()):
        return (
            f"invisible to every signal ({detail}): no readable brand text and no "
            "matchable symbol geometry"
        )
    loudest = max(scores, key=lambda name: scores[name])
    weak = thresholds.get(loudest, config.FALLBACK_THRESHOLDS)[0]
    hint = {
        "ocr": "brand text seen but too stylized/small to read",
        "sift": "symbol partially matched, too few verified keypoints",
    }.get(loudest, "signal fired below its weak threshold")
    return f"below threshold ({detail}; {loudest} weak>={weak:.2f}): {hint}"


def write_gate_failures(records, metrics: Metrics, thresholds, path=GATE_FAILURES_PATH) -> Path:
    """One line per false negative with a categorised reason."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    by_name = {record.filename: record for record in records}
    lines = [
        f"# gate FAILED {date.today().isoformat()} — "
        f"catch-recall {metrics.catch_recall:.3f} "
        f"(target {config.TARGET_CATCH_RECALL:.2f}), "
        f"review share {metrics.review_share * 100:.1f}% "
        f"(target {config.TARGET_REVIEW_SHARE * 100:.0f}%)",
        f"# {metrics.missed} positive(s) banded negative:",
    ]
    for name in sorted(metrics.false_negatives):
        lines.append(f"{name} — {miss_reason(by_name[name], thresholds)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def gate_verdict(metrics: Metrics) -> tuple[bool, list[str]]:
    """`(passed, failed_target_descriptions)` for the phase04 gate."""
    failures = []
    if metrics.catch_recall < config.TARGET_CATCH_RECALL - EPS:
        failures.append(
            f"catch-recall {metrics.catch_recall:.3f} < target "
            f"{config.TARGET_CATCH_RECALL:.2f}"
        )
    if metrics.review_share > config.TARGET_REVIEW_SHARE + EPS:
        failures.append(
            f"review share {metrics.review_share * 100:.1f}% > target "
            f"{config.TARGET_REVIEW_SHARE * 100:.0f}%"
        )
    return not failures, failures


def run_calibration(
    labeled_dir: str | Path,
    signal_names=None,
    limit: int | None = None,
    progress: bool = True,
    apply: bool = True,
    grid=config.CALIBRATION_GRID,
    output_path: str | Path = CALIBRATION_PATH,
    config_path: str | Path = CONFIG_PATH,
    gate_path: str | Path = GATE_FAILURES_PATH,
) -> dict:
    """Score, search, publish. Returns the dict written to `calibration.json`."""
    records, meta = score_images(
        labeled_dir, signal_names or config.ENABLED_SIGNALS, limit=limit, progress=progress
    )
    # Names come back from the scorer: callers may pass built signal objects.
    names = tuple(meta["signals"])
    if not records:
        raise ValueError(f"no readable images under {labeled_dir}")

    result = search(records, names, grid=grid)
    thresholds = result.best.thresholds
    # Re-measure through the shipping code path, not the vectorised search.
    metrics = evaluate(records, thresholds)
    passed, failures = gate_verdict(metrics)

    print()
    print(format_metrics(metrics, thresholds))
    print(f"searched     : {result.evaluated} threshold combinations")
    if result.relaxed_to is not None:
        print(
            f"note         : no combination reached catch-recall "
            f"{config.TARGET_CATCH_RECALL:.2f}; relaxed to the attainable "
            f"{result.relaxed_to:.3f}"
        )
    print(f"GATE         : {'PASSED' if passed else 'FAILED'}")
    for line in failures:
        print(f"  - {line}")

    payload = {
        "date": date.today().isoformat(),
        "labeled": str(labeled_dir),
        "signals": list(names),
        "images": meta["images"],
        "positives": meta["positives"],
        "negatives": meta["negatives"],
        "unreadable": meta["errors"],
        "seconds": round(meta["seconds"], 2),
        "images_per_second": round(meta["images_per_second"], 3),
        "grid": list(result.grid),
        "combinations": result.evaluated,
        "objective": {
            "target_catch_recall": config.TARGET_CATCH_RECALL,
            "target_review_share": config.TARGET_REVIEW_SHARE,
            "feasible": result.feasible,
            "relaxed_to": result.relaxed_to,
            "attainable_catch_recall": round(result.attainable_recall, 4),
        },
        "thresholds": {
            name: {"weak": weak, "strong": strong}
            for name, (weak, strong) in sorted(thresholds.items())
        },
        "metrics": metrics.as_dict(),
        "gate": {"passed": passed, "failed_targets": failures},
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote        : {output_path}")

    if apply:
        apply_to_config(thresholds, config_path)
        config.SIGNAL_THRESHOLDS = dict(thresholds)  # this process, too
        print(f"updated      : {config_path}")

    if not passed:
        written = write_gate_failures(records, metrics, thresholds, gate_path)
        print(f"wrote        : {written}")
    else:
        # A file left over from an earlier failing run would still say FAILED,
        # which is exactly the sort of stale artifact someone acts on.
        stale = Path(gate_path)
        if stale.exists():
            stale.unlink()
            print(f"removed      : {stale} (stale, the gate now passes)")

    return payload
