"""Embedding signal: preprocessing, templates, graceful degradation, matching.

Everything that needs the DINOv2 checkpoint is marked `slow` - those tests need
a model on disk (a one-off download), so the fast suite skips them with
`-m "not slow"`. The unmarked tests cover the parts that must work whether or
not torch is installed at all, including the "no model, no crash" path that a
scan depends on.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from logoscanner import config, embeddings
from logoscanner.embeddings import EmbeddingSignal, Templates
from logoscanner.proposals import Region

pytest_plugins = ()


@pytest.fixture(autouse=True)
def _clear_template_cache():
    embeddings.clear_cache()
    yield
    embeddings.clear_cache()


# --- preprocessing ---------------------------------------------------------


def test_letterbox_is_square_and_preserves_aspect():
    wide = np.zeros((50, 200, 3), np.uint8)
    wide[:] = (10, 20, 30)
    boxed = embeddings.letterbox(wide, 100)
    assert boxed.shape == (100, 100, 3)
    # A 4:1 crop becomes 100x25 of content, centred, with padding above/below.
    assert (boxed[0] == 255).all() and (boxed[-1] == 255).all()
    assert (boxed[50] == (10, 20, 30)).all()


def test_letterbox_does_not_stretch_a_wordmark():
    """A squashed wordmark reads as a different mark to the model."""
    wide = np.full((40, 400, 3), 200, np.uint8)
    cv2.putText(wide, "ACME", (10, 32), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    boxed = embeddings.letterbox(wide, 126)
    ink = np.argwhere(boxed[:, :, 0] < 128)
    height = ink[:, 0].max() - ink[:, 0].min()
    width = ink[:, 1].max() - ink[:, 1].min()
    assert width > height * 3  # aspect survived the resize


def test_letterbox_handles_a_degenerate_crop():
    assert embeddings.letterbox(np.zeros((0, 10, 3), np.uint8), 32).shape == (32, 32, 3)


def test_preprocess_shape_and_normalisation():
    crops = [np.full((60, 60, 3), 128, np.uint8) for _ in range(3)]
    batch = embeddings.preprocess(crops, size=28)
    assert batch.shape == (3, 3, 28, 28)
    assert batch.dtype == np.float32
    # 128/255 normalised by the ImageNet statistics. The batch is RGB-ordered,
    # matching the constants, even though the crops came in as BGR.
    expected = (128 / 255 - embeddings.IMAGENET_MEAN) / embeddings.IMAGENET_STD
    assert batch[0, :, 14, 14] == pytest.approx(expected, abs=1e-4)


def test_preprocess_converts_bgr_to_rgb():
    """Crops arrive BGR from OpenCV; the model was trained on RGB."""
    blue_in_bgr = np.zeros((20, 20, 3), np.uint8)
    blue_in_bgr[:, :, 0] = 255
    batch = embeddings.preprocess([blue_in_bgr], size=28)
    channels = batch[0, :, 14, 14]
    assert channels.argmax() == 2  # blue must land in the last (B) channel


# --- crops -----------------------------------------------------------------


def test_crop_regions_cuts_the_right_pixels():
    image = np.zeros((100, 100, 3), np.uint8)
    image[20:40, 30:60] = 200
    crops, kept = embeddings.crop_regions(image, [Region((30, 20, 30, 20), "mser")])
    assert len(crops) == 1 and len(kept) == 1
    assert crops[0].shape == (20, 30, 3)
    assert (crops[0] == 200).all()


def test_crop_regions_drops_empty_boxes():
    image = np.zeros((50, 50, 3), np.uint8)
    regions = [Region((10, 10, 20, 20), "mser"), Region((60, 60, 10, 10), "mser")]
    crops, kept = embeddings.crop_regions(image, regions)
    assert len(crops) == 1 and kept[0].bbox == (10, 10, 20, 20)


def test_crop_regions_normalises_channels():
    gray = np.zeros((50, 50), np.uint8)
    bgra = np.zeros((50, 50, 4), np.uint8)
    for image in (gray, bgra):
        crops, _ = embeddings.crop_regions(image, [Region((5, 5, 20, 20), "mser")])
        assert crops[0].ndim == 3 and crops[0].shape[2] == 3


# --- degradation (no model / no logo) --------------------------------------


def test_signal_without_logo_variants_scores_zero_and_warns(tmp_path):
    signal = EmbeddingSignal(logo_dir=tmp_path)
    with pytest.warns(RuntimeWarning, match="will score 0"):
        signal.templates()
    result = signal.run(np.zeros((80, 80, 3), np.uint8))
    assert result.score == 0.0 and result.bbox is None


def test_signal_warns_only_once(tmp_path, recwarn):
    signal = EmbeddingSignal(logo_dir=tmp_path)
    with pytest.warns(RuntimeWarning):
        signal.templates()
    recwarn.clear()
    signal.templates()
    assert not [w for w in recwarn if issubclass(w.category, RuntimeWarning)]


def test_signal_survives_a_missing_model(monkeypatch, tmp_path, dummy_logo_path):
    """No torch, no checkpoint, no network: score 0, never an exception."""
    import shutil

    shutil.copy(dummy_logo_path, tmp_path / dummy_logo_path.name)
    monkeypatch.setattr(embeddings, "load_model", lambda: None)
    signal = EmbeddingSignal(logo_dir=tmp_path)
    with pytest.warns(RuntimeWarning):
        result = signal.run(np.zeros((80, 80, 3), np.uint8))
    assert result.score == 0.0


def test_signal_survives_a_broken_match(monkeypatch, tmp_path):
    signal = EmbeddingSignal(logo_dir=tmp_path)
    monkeypatch.setattr(
        signal, "templates", lambda: Templates(("x",), np.ones((1, 4), np.float32))
    )
    monkeypatch.setattr(
        embeddings, "propose", lambda _image: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    result = signal.run(np.zeros((80, 80, 3), np.uint8))
    assert result.score == 0.0 and "RuntimeError" in result.detail


def test_build_templates_on_an_empty_folder(tmp_path):
    assert len(embeddings.build_templates(tmp_path)) == 0


def test_embed_of_nothing_is_empty():
    assert embeddings.embed([]).shape[0] == 0


def test_variant_views_splits_a_transparent_logo(dummy_logo_path):
    """An alpha variant is flattened onto white *and* black (D-024)."""
    views = embeddings._variant_views(dummy_logo_path)
    assert len(views) == 2
    assert all(view.ndim == 3 and view.shape[2] == 3 for view in views)
    assert not np.array_equal(views[0], views[1])


def test_variant_views_on_an_unreadable_file(tmp_path):
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"not an image")
    assert embeddings._variant_views(bad) == []


# --- the real model --------------------------------------------------------


@pytest.mark.slow
def test_templates_embed_the_fake_logo(fake_logo_dir):
    templates = embeddings.get_templates(fake_logo_dir)
    assert len(templates) == 2  # white- and black-composited views
    assert templates.vectors.shape[1] > 0
    norms = np.linalg.norm(templates.vectors, axis=1)
    assert norms == pytest.approx(np.ones_like(norms), abs=1e-4)


@pytest.mark.slow
def test_a_logo_crop_beats_an_unrelated_crop(fake_logo_dir, dummy_logo_path):
    """The whole point of the signal: the mark scores above things that aren't."""
    logo = cv2.imread(str(dummy_logo_path), cv2.IMREAD_UNCHANGED)
    flat = logo[:, :, :3].copy()
    noise = np.random.default_rng(0).integers(0, 255, flat.shape, dtype=np.uint8)
    templates = embeddings.get_templates(fake_logo_dir)
    vectors = embeddings.embed([flat, noise])
    similarity = vectors @ templates.vectors.T
    assert similarity[0].max() > similarity[1].max()
    assert similarity[0].max() > 0.9  # the variant against itself


@pytest.mark.slow
def test_signal_finds_a_pasted_mark(fake_logo_dir, dummy_logo_path):
    logo = cv2.imread(str(dummy_logo_path), cv2.IMREAD_UNCHANGED)
    scene = np.full((600, 900, 3), 180, np.uint8)
    cv2.circle(scene, (700, 450), 120, (90, 120, 60), -1)
    small = cv2.resize(logo, (300, 100))
    alpha = small[:, :, 3:4] / 255.0
    scene[80:180, 100:400] = (
        small[:, :, :3] * alpha + scene[80:180, 100:400] * (1 - alpha)
    ).astype(np.uint8)

    signal = EmbeddingSignal(logo_dir=fake_logo_dir)
    with_logo = signal.run(scene)
    without = signal.run(np.full((600, 900, 3), 180, np.uint8))
    assert with_logo.score > without.score
    assert with_logo.bbox is not None


@pytest.mark.slow
def test_below_the_floor_reports_no_box(monkeypatch, fake_logo_dir):
    monkeypatch.setattr(config, "EMB_MIN_SIMILARITY", 0.999)
    signal = EmbeddingSignal(logo_dir=fake_logo_dir)
    result = signal.run(np.full((300, 300, 3), 200, np.uint8))
    assert result.score == 0.0 and result.bbox is None
    assert "below floor" in result.detail
