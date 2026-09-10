"""Remembering per-image scores between calibration runs (D-035).

A stale cache is worse than no cache: it would calibrate the shipped thresholds
against numbers that no longer describe the signals. So every test here is
about the cache correctly refusing itself.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

import make_synthetic
from logoscanner import scorecache
from logoscanner.metrics import ScoredImage, score_images
from logoscanner.signals import SignalResult


class CountingSignal:
    """Scores by pixel mean and counts how many images it actually looked at."""

    def __init__(self, name="stub", offset=0.0):
        self.name = name
        self.calls = 0
        self.offset = offset

    def run(self, image: np.ndarray) -> SignalResult:
        self.calls += 1
        return SignalResult(name=self.name, score=min(1.0, float(image.mean()) / 255 + self.offset))


def _records():
    return [
        ScoredImage("a.png", "positive", {"stub": 0.9}),
        ScoredImage("b.png", "negative", {"stub": 0.1}),
    ]


def test_round_trip(tmp_path):
    path = scorecache.save(tmp_path / "scores.json", _records(), ("stub",))
    loaded = scorecache.load(path, ("stub",))
    assert set(loaded) == {"a.png", "b.png"}
    assert loaded["a.png"].label == "positive"
    assert loaded["a.png"].scores == {"stub": 0.9}


def test_a_different_signal_set_invalidates_everything(tmp_path):
    """Scores belong to the signal that produced them, and to no other."""
    path = scorecache.save(tmp_path / "scores.json", _records(), ("stub",))
    assert scorecache.load(path, ("stub", "other")) == {}
    assert scorecache.load(path, ("other",)) == {}


def test_missing_corrupt_and_foreign_caches_are_simply_empty(tmp_path):
    assert scorecache.load(tmp_path / "nope.json", ("stub",)) == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert scorecache.load(bad, ("stub",)) == {}
    old = tmp_path / "old.json"
    old.write_text(json.dumps({"format": 999, "signals": ["stub"], "images": []}), encoding="utf-8")
    assert scorecache.load(old, ("stub",)) == {}


def test_one_unreadable_row_does_not_discard_the_rest(tmp_path):
    path = tmp_path / "scores.json"
    scorecache.save(path, _records(), ("stub",))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["images"].append({"filename": "c.png"})  # no label, no scores
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = scorecache.load(path, ("stub",))
    assert set(loaded) == {"a.png", "b.png"}


def test_reuse_restamps_the_label_from_disk(tmp_path):
    """Re-judging an image must not cost a re-score, nor keep the old verdict."""
    cached = {r.filename: r for r in _records()}
    moved = scorecache.reuse(cached, "b.png", "positive")
    assert moved.label == "positive"
    assert moved.scores == {"stub": 0.1}  # the pixels did not change
    assert scorecache.reuse(cached, "unknown.png", "positive") is None


def test_score_images_pays_only_for_new_images(tmp_path, dummy_logo_path):
    labeled = tmp_path / "labeled"
    make_synthetic.generate(labeled, count=6, positive_ratio=0.5, logo_path=dummy_logo_path,
                            size=(60, 80), seed=3)
    cache = tmp_path / "scores.json"

    first = CountingSignal()
    records, meta = score_images(labeled, [first], progress=False, cache_path=cache)
    assert first.calls == 6
    assert meta["scored"] == 6 and meta["reused_from_cache"] == 0

    second = CountingSignal()
    again, meta = score_images(labeled, [second], progress=False, cache_path=cache)
    assert second.calls == 0, "cached images were scored a second time"
    assert meta["reused_from_cache"] == 6 and meta["scored"] == 0
    # Cached scores are stored rounded to 6 decimals - far finer than the 0.05
    # threshold grid they are judged against, so the choice cannot shift.
    before = {r.filename: r for r in records}
    for record in again:
        assert record.label == before[record.filename].label
        assert record.scores["stub"] == pytest.approx(
            before[record.filename].scores["stub"], abs=1e-6)


def test_adding_images_scores_only_the_additions(tmp_path, dummy_logo_path):
    labeled = tmp_path / "labeled"
    make_synthetic.generate(labeled, count=4, positive_ratio=0.5, logo_path=dummy_logo_path,
                            size=(60, 80), seed=5)
    cache = tmp_path / "scores.json"
    score_images(labeled, [CountingSignal()], progress=False, cache_path=cache)

    extra = tmp_path / "extra"
    make_synthetic.generate(extra, count=2, positive_ratio=1.0, logo_path=dummy_logo_path,
                            size=(60, 80), seed=9)
    for path in (extra / "positive").iterdir():
        (labeled / "positive" / f"new_{path.name}").write_bytes(path.read_bytes())

    signal = CountingSignal()
    _, meta = score_images(labeled, [signal], progress=False, cache_path=cache)

    assert signal.calls == 2, "the whole set was re-scored instead of just the additions"
    assert meta["reused_from_cache"] == 4


def test_a_changed_signal_is_the_users_job_to_declare(tmp_path, dummy_logo_path):
    """Same name, different behaviour: the cache cannot detect this, and says so.

    `--no-cache` exists precisely for it, so the test pins the hazard rather
    than pretending it is handled.
    """
    labeled = tmp_path / "labeled"
    make_synthetic.generate(labeled, count=4, positive_ratio=0.5, logo_path=dummy_logo_path,
                            size=(60, 80), seed=7)
    cache = tmp_path / "scores.json"
    score_images(labeled, [CountingSignal()], progress=False, cache_path=cache)

    changed = CountingSignal(offset=0.5)  # would score differently
    records, _ = score_images(labeled, [changed], progress=False, cache_path=cache)
    assert changed.calls == 0  # stale scores served silently

    records, meta = score_images(labeled, [CountingSignal(offset=0.5)], progress=False,
                                 cache_path=None)
    assert meta["scored"] == 4  # --no-cache is the escape hatch


def test_no_cache_path_means_no_file_and_no_reuse(tmp_path, dummy_logo_path):
    labeled = tmp_path / "labeled"
    make_synthetic.generate(labeled, count=4, positive_ratio=0.5, logo_path=dummy_logo_path,
                            size=(60, 80), seed=11)
    signal = CountingSignal()
    score_images(labeled, [signal], progress=False)
    score_images(labeled, [signal], progress=False)
    assert signal.calls == 8
    assert not list(tmp_path.glob("*.json"))
