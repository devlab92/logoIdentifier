"""Synthetic dataset generator."""

from __future__ import annotations

import numpy as np
import pytest

import make_synthetic
from logoscanner.io_utils import iter_images, load_image


def test_generator_produces_requested_split(tmp_path, dummy_logo_path):
    counts = make_synthetic.generate(
        tmp_path, count=10, positive_ratio=0.4, logo_path=dummy_logo_path,
        size=(240, 320), seed=7,
    )
    assert counts == {"positive": 4, "negative": 6}
    assert len(list(iter_images(tmp_path / "positive"))) == 4
    assert len(list(iter_images(tmp_path / "negative"))) == 6
    assert len(list(iter_images(tmp_path))) == 10


def test_generated_images_are_loadable_and_sized(tmp_path, dummy_logo_path):
    make_synthetic.generate(
        tmp_path, count=4, positive_ratio=0.5, logo_path=dummy_logo_path,
        size=(200, 300), seed=1,
    )
    for path in iter_images(tmp_path):
        image, error = load_image(path)
        assert error is None
        assert image.shape == (200, 300, 3)


def test_all_negative_split_needs_no_logo(tmp_path):
    counts = make_synthetic.generate(
        tmp_path, count=3, positive_ratio=0.0, logo_path=tmp_path / "absent.png",
        size=(120, 160), seed=2,
    )
    assert counts == {"positive": 0, "negative": 3}


def test_missing_logo_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        make_synthetic.generate(
            tmp_path, count=2, positive_ratio=1.0, logo_path=tmp_path / "absent.png",
        )


def test_positive_differs_from_its_background(tmp_path, dummy_logo_path):
    rng = np.random.default_rng(3)
    background = make_synthetic.make_background(rng, 200, 300)
    logo = np.dstack(
        [np.full((40, 60, 3), 255, np.uint8), np.full((40, 60), 255, np.uint8)]
    )
    pasted = make_synthetic.paste_logo(rng, background, logo)
    assert pasted.shape == background.shape
    assert not np.array_equal(pasted, background)
