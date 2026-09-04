"""Threshold search, the config rewrite and the gate verdict."""

from __future__ import annotations

import json
from pathlib import Path

import make_synthetic
import pytest

from logoscanner import config
from logoscanner.calibrate import (
    BLOCK_END,
    BLOCK_START,
    apply_to_config,
    gate_verdict,
    miss_reason,
    pair_grid,
    render_thresholds_block,
    run_calibration,
    search,
    write_gate_failures,
)
from logoscanner.metrics import Metrics, ScoredImage, evaluate
from logoscanner.signals import SignalResult

GRID = (0.1, 0.3, 0.5, 0.7, 0.9)


def record(filename, label, ocr=0.0, sift=0.0) -> ScoredImage:
    return ScoredImage(filename=filename, label=label, scores={"ocr": ocr, "sift": sift})


def separable(n: int = 10) -> list[ScoredImage]:
    """Positives score high on ocr, negatives score nothing: perfectly solvable."""
    return [record(f"p{i}.jpg", "positive", ocr=0.9) for i in range(n)] + [
        record(f"n{i}.jpg", "negative", ocr=0.1) for i in range(n)
    ]


class SilentSignal:
    """Never sees anything, so the gate can only fail - by construction."""

    name = "ocr"

    def run(self, image):
        return SignalResult(self.name, 0.0)


def test_pair_grid_only_emits_weak_below_strong():
    pairs = pair_grid(GRID)
    assert all(weak <= strong for weak, strong in pairs)
    assert len(pairs) == len(GRID) * (len(GRID) + 1) // 2


def test_search_finds_a_feasible_point_on_a_separable_set():
    result = search(separable(), ("ocr", "sift"), grid=GRID)
    assert result.feasible is True
    assert result.relaxed_to is None
    assert result.best.precision == pytest.approx(1.0)
    assert result.best.catch_recall == pytest.approx(1.0)
    assert result.best.review_share == 0.0
    assert result.evaluated == len(pair_grid(GRID)) ** 2


def test_the_reported_metrics_match_the_shipping_decision_path():
    result = search(separable(), ("ocr", "sift"), grid=GRID)
    metrics = evaluate(separable(), result.best.thresholds)
    assert metrics.precision == pytest.approx(result.best.precision)
    assert metrics.catch_recall == pytest.approx(result.best.catch_recall)
    assert metrics.review_share == pytest.approx(result.best.review_share)


def test_precision_is_maximised_among_the_points_that_meet_the_targets():
    # One negative scores 0.6, so a strong threshold of 0.5 would flag it. The
    # objective must lift `strong` above it rather than settle for 10/11.
    records = (
        [record(f"p{i}.jpg", "positive", ocr=0.9) for i in range(10)]
        + [record(f"n{i}.jpg", "negative", ocr=0.1) for i in range(9)]
        + [record("loud-negative.jpg", "negative", ocr=0.6)]
    )
    result = search(records, ("ocr",), grid=GRID)
    assert result.best.precision == pytest.approx(1.0)
    assert result.best.catch_recall == pytest.approx(1.0)
    assert result.best.thresholds["ocr"][1] > 0.6


def test_an_unreachable_recall_target_relaxes_to_what_the_scores_allow():
    records = separable(9) + [record("blind.jpg", "positive")]  # scores 0 everywhere
    result = search(records, ("ocr", "sift"), grid=GRID)
    assert result.feasible is False
    assert result.attainable_recall == pytest.approx(0.9)
    assert result.relaxed_to == pytest.approx(0.9)
    assert result.best.catch_recall == pytest.approx(0.9)


def test_search_on_an_empty_set_returns_nothing_rather_than_crashing():
    result = search([], ("ocr",), grid=GRID)
    assert result.best is None and result.evaluated == 0


def test_gate_verdict_names_every_target_that_failed():
    passed, failures = gate_verdict(
        Metrics(catch_recall=0.99, review_share=0.05, images=1, positives=1)
    )
    assert passed is True and failures == []

    passed, failures = gate_verdict(
        Metrics(catch_recall=0.90, review_share=0.30, images=1, positives=1)
    )
    assert passed is False and len(failures) == 2
    assert "catch-recall" in failures[0] and "review share" in failures[1]


def test_render_and_apply_round_trip_through_a_config_copy(tmp_path):
    source = tmp_path / "config.py"
    source.write_text(
        "BEFORE = 1\n" + render_thresholds_block({"ocr": (0.1, 0.2)}) + "\nAFTER = 2\n",
        encoding="utf-8",
    )
    apply_to_config({"ocr": (0.55, 0.95), "sift": (0.05, 0.65)}, source, stamp="2026-01-01")

    text = source.read_text(encoding="utf-8")
    assert text.startswith("BEFORE = 1\n") and text.endswith("AFTER = 2\n")
    assert text.count(BLOCK_START) == 1 and text.count(BLOCK_END) == 1
    assert '"ocr": (0.55, 0.95),' in text and '"sift": (0.05, 0.65),' in text
    assert "2026-01-01" in text

    namespace: dict = {}
    exec(compile(text, str(source), "exec"), namespace)
    assert namespace["SIGNAL_THRESHOLDS"] == {"ocr": (0.55, 0.95), "sift": (0.05, 0.65)}


def test_applying_to_a_file_without_the_markers_is_refused(tmp_path):
    source = tmp_path / "config.py"
    source.write_text("SIGNAL_THRESHOLDS = {}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        apply_to_config({"ocr": (0.1, 0.2)}, source)


def test_the_shipped_config_still_carries_the_markers():
    text = Path(config.__file__).read_text(encoding="utf-8")
    assert BLOCK_START in text and BLOCK_END in text


def test_miss_reasons_separate_blind_images_from_weak_ones():
    thresholds = {"ocr": (0.60, 0.95), "sift": (0.05, 0.65)}
    blind = miss_reason(record("a.jpg", "positive"), thresholds)
    assert "invisible to every signal" in blind

    weak = miss_reason(record("b.jpg", "positive", ocr=0.42), thresholds)
    assert "below threshold" in weak and "ocr=0.42" in weak and "0.60" in weak

    sift_only = miss_reason(record("c.jpg", "positive", sift=0.04), thresholds)
    assert "keypoints" in sift_only


def test_gate_failures_file_lists_every_miss_with_a_reason(tmp_path):
    records = [record("blind.jpg", "positive"), record("faint.jpg", "positive", ocr=0.42)]
    thresholds = {"ocr": (0.60, 0.95), "sift": (0.05, 0.65)}
    metrics = evaluate(records, thresholds)
    path = write_gate_failures(records, metrics, thresholds, tmp_path / "gate_failures.txt")

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("# gate FAILED")
    assert [line.split(" — ")[0] for line in lines if not line.startswith("#")] == [
        "blind.jpg",
        "faint.jpg",
    ]


def test_run_calibration_writes_json_config_and_the_gate_file(tmp_path, dummy_logo_path):
    labeled = tmp_path / "labeled"
    make_synthetic.generate(
        labeled, count=6, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(60, 80), seed=3,
    )
    config_copy = tmp_path / "config_copy.py"
    config_copy.write_text(render_thresholds_block({"ocr": (0.1, 0.2)}) + "\n", encoding="utf-8")
    output = tmp_path / "calibration.json"
    gate = tmp_path / "gate_failures.txt"

    before = dict(config.SIGNAL_THRESHOLDS)
    try:
        payload = run_calibration(
            labeled,
            [SilentSignal()],  # scores 0 everywhere: the gate cannot pass
            progress=False,
            grid=GRID,
            output_path=output,
            config_path=config_copy,
            gate_path=gate,
        )
    finally:
        config.SIGNAL_THRESHOLDS = before

    assert payload["gate"]["passed"] is False
    assert payload["metrics"]["catch_recall"] == 0.0
    assert json.loads(output.read_text(encoding="utf-8"))["thresholds"]["ocr"]["weak"] > 0
    assert '"ocr": (' in config_copy.read_text(encoding="utf-8")
    assert gate.exists() and "invisible to every signal" in gate.read_text(encoding="utf-8")


def test_run_calibration_can_leave_the_config_alone(tmp_path, dummy_logo_path):
    labeled = tmp_path / "labeled"
    make_synthetic.generate(
        labeled, count=4, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(60, 80), seed=3,
    )
    config_copy = tmp_path / "config_copy.py"
    original = render_thresholds_block({"ocr": (0.1, 0.2)}) + "\n"
    config_copy.write_text(original, encoding="utf-8")

    run_calibration(
        labeled,
        [SilentSignal()],
        progress=False,
        apply=False,
        grid=GRID,
        output_path=tmp_path / "calibration.json",
        config_path=config_copy,
        gate_path=tmp_path / "gate_failures.txt",
    )
    assert config_copy.read_text(encoding="utf-8") == original


def test_run_calibration_needs_readable_images(tmp_path):
    (tmp_path / "positive").mkdir()
    (tmp_path / "negative").mkdir()
    with pytest.raises(ValueError):
        run_calibration(tmp_path, [SilentSignal()], progress=False, apply=False, grid=GRID)
