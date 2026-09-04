"""SIFT signal: multi-scale/rotation detection, geometry checks, graceful skip.

Everything here runs on the committed fake mark (`tests/assets/dummy_logo.png`)
pasted onto synthetic backgrounds — the real logo never enters the test suite.
"""

from __future__ import annotations

import shutil
import warnings

import cv2
import make_synthetic
import numpy as np
import pytest

from logoscanner import config, keypoints
from logoscanner.keypoints import (
    SiftSignal,
    build_templates,
    good_matches,
    plausible_box,
    to_gray,
)

BACKGROUND = (900, 1200)  # height, width — room for the logo at 1.5x


@pytest.fixture
def logo_dir(tmp_path, dummy_logo_path):
    """A `logo/`-shaped folder holding only the fake mark."""
    folder = tmp_path / "logo"
    folder.mkdir()
    shutil.copy(dummy_logo_path, folder / dummy_logo_path.name)
    keypoints.clear_cache()
    yield folder
    keypoints.clear_cache()


@pytest.fixture
def logo_rgba(dummy_logo_path):
    return cv2.imread(str(dummy_logo_path), cv2.IMREAD_UNCHANGED)


def background(seed: int = 0, size=BACKGROUND) -> np.ndarray:
    return make_synthetic.make_background(np.random.default_rng(seed), *size)


def compose(logo_rgba, scale: float, degrees: float, seed: int = 0, size=BACKGROUND):
    """Paste the mark at a known scale/rotation, centred; return image + box."""
    image = background(seed, size)
    resized = cv2.resize(
        logo_rgba,
        (int(logo_rgba.shape[1] * scale), int(logo_rgba.shape[0] * scale)),
        interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR,
    )
    patch = make_synthetic._rotate_rgba(resized, degrees)
    height, width = patch.shape[:2]
    y, x = (size[0] - height) // 2, (size[1] - width) // 2
    alpha = patch[:, :, 3:4].astype(np.float32) / 255.0
    region = image[y : y + height, x : x + width].astype(np.float32)
    image[y : y + height, x : x + width] = (
        patch[:, :, :3].astype(np.float32) * alpha + region * (1 - alpha)
    ).astype(np.uint8)
    return image, (x, y, width, height)


def overlaps(box, expected, tolerance: float = 0.35) -> bool:
    """Is `box` roughly where the logo was pasted (centre inside, size sane)?"""
    x, y, w, h = box
    ex, ey, ew, eh = expected
    centre_x, centre_y = x + w / 2, y + h / 2
    if not (ex <= centre_x <= ex + ew and ey <= centre_y <= ey + eh):
        return False
    return (1 - tolerance) * ew <= w <= (1 + tolerance) * ew


@pytest.mark.parametrize("scale", [0.4, 1.0, 1.5])
@pytest.mark.parametrize("degrees", [-10, 0, 10])
def test_the_logo_is_found_at_any_scale_and_small_rotations(
    logo_dir, logo_rgba, scale, degrees
):
    image, expected = compose(logo_rgba, scale, degrees)

    result = SiftSignal(logo_dir).run(image)

    assert result.score > 0.0, result.detail
    assert result.bbox is not None
    assert overlaps(result.bbox, expected), (result.bbox, expected)


def test_a_background_without_the_logo_scores_zero(logo_dir):
    signal = SiftSignal(logo_dir)
    for seed in range(6):
        result = signal.run(background(seed))
        assert result.score == 0.0, (seed, result.detail)
        assert result.bbox is None


def test_the_reported_box_is_inside_the_original_image(logo_dir, logo_rgba):
    image, _ = compose(logo_rgba, 1.0, 0)

    x, y, w, h = SiftSignal(logo_dir).run(image).bbox

    assert 0 <= x < x + w <= image.shape[1]
    assert 0 <= y < y + h <= image.shape[0]


def test_a_scan_sized_image_is_matched_after_downscaling(logo_dir, logo_rgba):
    """An image larger than MAX_SIDE still reports a box in its own coordinates."""
    image, expected = compose(
        logo_rgba, 1.5, 0, size=(config.MAX_SIDE + 600, config.MAX_SIDE + 900)
    )

    result = SiftSignal(logo_dir).run(image)

    assert result.score > 0.0, result.detail
    assert overlaps(result.bbox, expected), (result.bbox, expected)


def test_plausible_box_rejects_degenerate_homographies():
    shape = (600, 800)
    sane = np.float32([[100, 100], [400, 110], [395, 300], [95, 290]])
    assert plausible_box(sane, shape)

    collapsed = np.float32([[400, 300], [402, 301], [401, 303], [399, 302]])
    assert not plausible_box(collapsed, shape)  # folded onto a point

    bowtie = np.float32([[100, 100], [400, 300], [400, 100], [100, 300]])
    assert not plausible_box(bowtie, shape)  # self-intersecting

    sliver = np.float32([[10, 300], [700, 302], [700, 306], [10, 304]])
    assert not plausible_box(sliver, shape)  # aspect ratio far past any logo

    off_canvas = np.float32([[900, 700], [1200, 700], [1200, 900], [900, 900]])
    assert not plausible_box(off_canvas, shape)  # centre outside the image

    assert not plausible_box(np.float32([[np.nan, 0], [1, 0], [1, 1], [0, 1]]), shape)


def test_a_missing_logo_folder_warns_once_and_scores_zero(tmp_path):
    keypoints.clear_cache()
    signal = SiftSignal(tmp_path / "does-not-exist")

    with pytest.warns(RuntimeWarning, match="no usable logo variants"):
        first = signal.run(background(0, (120, 160)))
    with warnings.catch_warnings():  # a second warning here would raise
        warnings.simplefilter("error")
        second = signal.run(background(1, (120, 160)))

    assert first.score == 0.0 and second.score == 0.0
    assert "no logo variants" in first.detail
    keypoints.clear_cache()


def test_an_empty_logo_folder_yields_no_templates(tmp_path):
    (tmp_path / "notes.txt").write_text("not an image", encoding="utf-8")
    assert build_templates(tmp_path) == ()


def test_a_featureless_variant_is_dropped(tmp_path, dummy_logo_path):
    """A flat colour block has no descriptors; it must not become a template."""
    flat = np.full((200, 200, 3), 128, dtype=np.uint8)
    cv2.imencode(".png", flat)[1].tofile(str(tmp_path / "flat.png"))
    shutil.copy(dummy_logo_path, tmp_path / dummy_logo_path.name)

    names = [template.name for template in build_templates(tmp_path)]

    assert names == [dummy_logo_path.name]


def test_a_tiny_variant_is_upscaled_before_descriptors(tmp_path, logo_rgba):
    small = cv2.resize(logo_rgba, (120, 40), interpolation=cv2.INTER_AREA)
    cv2.imencode(".png", small)[1].tofile(str(tmp_path / "small.png"))

    template = build_templates(tmp_path)[0]

    assert min(template.shape) >= config.SIFT_MIN_SIDE
    assert len(template.descriptors) >= config.SIFT_MIN_GOOD


def test_to_gray_keeps_a_white_mark_visible(logo_rgba):
    """Transparent pixels must not be filled with the mark's own brightness."""
    white = logo_rgba.copy()
    white[:, :, :3] = 255

    gray = to_gray(white)

    assert gray[white[:, :, 3] > 0].mean() > gray[white[:, :, 3] == 0].mean() + 100


def test_good_matches_keeps_one_match_per_image_location(logo_dir, logo_rgba):
    """Many template descriptors landing on one spot would fake a consensus."""
    template = build_templates(logo_dir)[0]
    image, _ = compose(logo_rgba, 1.0, 0)
    detector = keypoints.make_detector()
    image_keypoints, descriptors = detector.detectAndCompute(to_gray(image), None)

    matches = good_matches(template.descriptors, descriptors, image_keypoints)

    spots = [tuple(round(v) for v in image_keypoints[m.trainIdx].pt) for m in matches]
    assert len(spots) == len(set(spots))


def test_templates_are_computed_once_per_folder(logo_dir):
    first = keypoints.get_templates(logo_dir)
    assert keypoints.get_templates(logo_dir) is first


def test_the_signal_is_registered_and_survives_a_broken_image(logo_dir):
    from logoscanner.signals import available, build

    assert "sift" in available()
    assert build("sift").name == "sift"

    signal = SiftSignal(logo_dir)
    result = signal.run(np.zeros((0, 0, 3), dtype=np.uint8))
    assert result.score == 0.0  # empty frame reported, not raised
