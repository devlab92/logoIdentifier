"""Crops and the detected/ review/ copies (phase07)."""

from __future__ import annotations

import numpy as np
import pytest

from logoscanner import artifacts, config


@pytest.fixture
def image() -> np.ndarray:
    rng = np.random.default_rng(4)
    return rng.integers(0, 255, (200, 300, 3), dtype=np.uint8)


def test_band_dir_maps_only_the_two_bands_worth_looking_at():
    assert artifacts.band_dir(config.BAND_POSITIVE) == artifacts.DETECTED_DIR
    assert artifacts.band_dir(config.BAND_REVIEW) == artifacts.REVIEW_DIR
    assert artifacts.band_dir(config.BAND_NEGATIVE) is None


def test_pad_box_grows_by_ten_percent_of_the_box(image):
    assert artifacts.pad_box((100, 100, 50, 40), image.shape) == (95, 96, 60, 48)


def test_pad_box_clips_to_the_image_edges(image):
    assert artifacts.pad_box((0, 0, 40, 40), image.shape) == (0, 0, 44, 44)
    x, y, w, h = artifacts.pad_box((280, 180, 20, 20), image.shape)
    assert x + w == 300 and y + h == 200


def test_pad_box_rejects_an_empty_box(image):
    assert artifacts.pad_box((10, 10, 0, 0), image.shape) is None


def test_crop_returns_the_padded_region(image):
    patch = artifacts.crop(image, (100, 100, 50, 40))
    assert patch.shape[:2] == (48, 60)
    assert np.array_equal(patch, image[96:144, 95:155])


def test_crop_of_nothing_is_none(image):
    assert artifacts.crop(image, None) is None
    assert artifacts.crop(None, (1, 2, 3, 4)) is None
    assert artifacts.crop(np.zeros((0, 0, 3), np.uint8), (1, 2, 3, 4)) is None


def test_write_image_handles_a_non_ascii_path(tmp_path, image):
    dest = tmp_path / "dossier café" / "logo é.jpg"
    artifacts.write_image(image, dest)
    assert dest.is_file() and dest.stat().st_size > 0


def test_save_writes_a_crop_and_copies_the_original(tmp_path, image):
    source = tmp_path / "in" / "2021-05" / "shot.png"
    artifacts.write_image(image, source)
    output = tmp_path / "out"

    problem = artifacts.save(image, source, output, "2021-05/shot.png",
                             config.BAND_POSITIVE, (100, 100, 50, 40))

    assert problem == ""
    crop = output / artifacts.CROPS_DIR / "2021-05" / "shot_crop.jpg"
    copy = output / artifacts.DETECTED_DIR / "2021-05" / "shot.png"
    assert crop.is_file() and copy.is_file()
    # The input tree is mirrored, so same-named files cannot collide.
    assert copy.read_bytes() == source.read_bytes()


def test_review_band_lands_in_the_review_folder(tmp_path, image):
    source = tmp_path / "in" / "shot.png"
    artifacts.write_image(image, source)
    output = tmp_path / "out"

    artifacts.save(image, source, output, "shot.png", config.BAND_REVIEW, (10, 10, 40, 30))

    assert (output / artifacts.REVIEW_DIR / "shot.png").is_file()
    assert not (output / artifacts.DETECTED_DIR).exists()


def test_negatives_produce_no_artifacts_at_all(tmp_path, image):
    source = tmp_path / "in" / "shot.png"
    artifacts.write_image(image, source)
    output = tmp_path / "out"

    assert artifacts.save(image, source, output, "shot.png", config.BAND_NEGATIVE, None) == ""
    assert not output.exists()


def test_a_flagged_image_without_a_box_is_still_copied(tmp_path, image):
    """A signal that cannot localise must not cost the human the image."""
    source = tmp_path / "in" / "shot.png"
    artifacts.write_image(image, source)
    output = tmp_path / "out"

    assert artifacts.save(image, source, output, "shot.png", config.BAND_POSITIVE, None) == ""
    assert (output / artifacts.DETECTED_DIR / "shot.png").is_file()
    assert not (output / artifacts.CROPS_DIR).exists()


def test_a_failed_copy_is_reported_not_raised(tmp_path, image):
    """Artifacts are a convenience; losing one must never end a scan."""
    output = tmp_path / "out"
    problem = artifacts.save(image, tmp_path / "gone.png", output, "gone.png",
                             config.BAND_POSITIVE, (10, 10, 40, 30))
    assert "copy failed" in problem
    assert (output / artifacts.CROPS_DIR / "gone_crop.jpg").is_file()
