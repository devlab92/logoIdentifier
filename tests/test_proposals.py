"""Region proposals: box algebra, each source, and the budgeted `propose`.

No OCR engine and no torch here - `propose` is called with `use_text=False`
throughout except in the one test that checks the hook exists, so this whole
file runs in the fast suite.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from logoscanner import config, proposals
from logoscanner.proposals import Region

SHAPE = (400, 600, 3)  # h, w, c


FONT = cv2.FONT_HERSHEY_SIMPLEX


def make_scene(origin=(250, 200), size=SHAPE, scale=1.6, colour=(25, 25, 25), bg=235):
    """A wordmark on a plain background, and the box it actually occupies.

    Deliberately stroke-based rather than a solid block: MSER keys on stable
    *stroke* regions, which is what a real wordmark is made of, and returns
    nothing for one flat rectangle nested inside another flat background.
    """
    image = np.full(size, bg, np.uint8)
    cv2.putText(image, "ACME", origin, FONT, scale, colour, 4)
    # The true box is the ink itself, not getTextSize's advance-width estimate.
    ink = np.argwhere(image[:, :, 0] != bg)
    (y0, x0), (y1, x1) = ink.min(axis=0), ink.max(axis=0)
    return image, (int(x0), int(y0), int(x1 - x0 + 1), int(y1 - y0 + 1))


# --- box algebra -----------------------------------------------------------


def test_clip_box_clamps_to_image():
    assert proposals.clip_box((-20, -10, 100, 50), SHAPE) == (0, 0, 80, 40)
    assert proposals.clip_box((580, 380, 100, 100), SHAPE) == (580, 380, 20, 20)


def test_clip_box_returns_none_when_nothing_survives():
    assert proposals.clip_box((700, 500, 50, 50), SHAPE) is None
    assert proposals.clip_box((10, 10, 0, 40), SHAPE) is None


def test_pad_box_grows_by_fraction_of_own_size():
    assert proposals.pad_box((100, 100, 200, 100), SHAPE, frac=0.10) == (80, 90, 240, 120)


def test_pad_box_is_clipped_at_the_border():
    padded = proposals.pad_box((0, 0, 100, 100), SHAPE, frac=0.5)
    assert padded == (0, 0, 150, 150)


def test_area_ok_rejects_specks_and_near_full_frames():
    assert proposals.area_ok((10, 10, 120, 80), SHAPE)
    assert not proposals.area_ok((10, 10, 2, 2), SHAPE)
    assert not proposals.area_ok((0, 0, 600, 400), SHAPE)


def test_area_ok_on_degenerate_image():
    assert not proposals.area_ok((0, 0, 10, 10), (0, 0, 3))


def test_iou_identical_disjoint_and_partial():
    box = (0, 0, 100, 100)
    assert proposals.iou(box, box) == pytest.approx(1.0)
    assert proposals.iou(box, (200, 200, 50, 50)) == 0.0
    # half-overlap: intersection 50x100, union 150x100
    assert proposals.iou(box, (50, 0, 100, 100)) == pytest.approx(5000 / 15000)


def test_union_box_covers_both():
    assert proposals.union_box((10, 10, 20, 20), (50, 40, 10, 10)) == (10, 10, 50, 40)


def test_merge_overlapping_folds_duplicates_and_keeps_priority():
    regions = [
        Region((100, 100, 100, 100), "mser"),
        Region((105, 105, 100, 100), "text"),
        Region((400, 300, 50, 50), "mser"),
    ]
    merged = proposals.merge_overlapping(regions, threshold=0.5)
    assert len(merged) == 2
    absorbed = next(r for r in merged if r.bbox[0] == 100)
    assert absorbed.source == "text"  # higher priority survives
    assert absorbed.bbox == (100, 100, 105, 105)  # union of the pair


def test_merge_overlapping_leaves_distinct_boxes_alone():
    regions = [Region((0, 0, 50, 50), "mser"), Region((300, 300, 50, 50), "mser")]
    assert len(proposals.merge_overlapping(regions, threshold=0.5)) == 2


# --- sources ---------------------------------------------------------------


def test_tile_regions_cover_the_frame_and_include_it():
    regions = proposals.tile_regions(SHAPE, grid=3)
    assert sum(1 for r in regions if r.source == "full") == 1
    full = next(r for r in regions if r.source == "full")
    assert full.bbox == (0, 0, 600, 400)
    assert all(r.bbox[0] >= 0 and r.bbox[1] >= 0 for r in regions)
    assert all(r.bbox[0] + r.bbox[2] <= 600 for r in regions)
    assert all(r.bbox[1] + r.bbox[3] <= 400 for r in regions)


def test_tile_regions_degenerate_grid_still_returns_the_frame():
    regions = proposals.tile_regions(SHAPE, grid=0)
    assert [r.source for r in regions] == ["full"]


def test_mser_lands_on_the_wordmark():
    """MSER need only overlap the mark; `propose` pads it out to a usable crop."""
    image, logo_box = make_scene()
    regions = proposals.mser_regions(image)
    assert regions, "MSER returned nothing on a high-contrast wordmark"
    assert max(proposals.iou(r.bbox, logo_box) for r in regions) > 0.25


def test_group_boxes_glues_letters_into_one_region():
    """Per-letter blobs are useless to the embedding; the word is not."""
    letters = [(100, 100, 20, 30), (128, 100, 20, 30), (156, 100, 20, 30)]
    grouped = proposals.group_boxes(letters, (400, 600))
    widest = max(grouped, key=lambda b: b[2])
    assert widest[2] > sum(b[2] for b in letters)
    assert all(box in grouped for box in letters)  # originals kept too


def test_group_boxes_on_empty_input():
    assert proposals.group_boxes([], (400, 600)) == []


def test_mser_accepts_grayscale_and_bgra():
    """OpenCV 5 silently returns nothing for 1-channel input (D-025)."""
    image, _ = make_scene()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    bgra = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    assert proposals.mser_regions(gray)
    assert proposals.mser_regions(bgra)


def test_text_regions_survive_a_missing_engine(monkeypatch):
    def boom(_image):
        raise RuntimeError("engine down")

    monkeypatch.setattr("logoscanner.ocr.read_text", boom)
    assert proposals.text_regions(np.zeros(SHAPE, np.uint8)) == []


# --- propose ---------------------------------------------------------------


def test_propose_puts_the_logo_region_among_the_candidates():
    image, logo_box = make_scene()
    regions = proposals.propose(image, use_text=False)
    assert max(proposals.iou(r.bbox, logo_box) for r in regions) > 0.3


def test_propose_respects_the_budget():
    image, _ = make_scene()
    regions = proposals.propose(image, use_text=False, max_regions=14)
    assert len(regions) <= 14 + len(proposals.tile_regions(image.shape))


def test_propose_always_keeps_the_full_frame():
    image, _ = make_scene()
    regions = proposals.propose(image, use_text=False, max_regions=1)
    assert any(r.source == "full" for r in regions)


def test_propose_accepts_hint_boxes_from_another_signal():
    image, _ = make_scene()
    hint = ((20, 20, 120, 90), "sift")
    regions = proposals.propose(image, extra=(hint,), use_text=False, use_mser=False)
    assert any(r.source == "sift" for r in regions)


def test_propose_hint_boxes_are_padded():
    image, _ = make_scene()
    hint = ((100, 100, 100, 100), "sift")
    regions = proposals.propose(image, extra=(hint,), use_text=False, use_mser=False)
    sift_box = next(r for r in regions if r.source == "sift").bbox
    assert sift_box[2] > 100 and sift_box[3] > 100


def test_propose_boxes_stay_inside_the_image():
    image, _ = make_scene()
    height, width = image.shape[:2]
    for region in proposals.propose(image, use_text=False):
        x, y, w, h = region.bbox
        assert 0 <= x and 0 <= y and w > 0 and h > 0
        assert x + w <= width and y + h <= height


def test_propose_on_a_tiny_image_does_not_crash():
    tiny = np.full((12, 12, 3), 200, np.uint8)
    assert proposals.propose(tiny, use_text=False)


def test_propose_uses_text_boxes_when_the_engine_answers(monkeypatch):
    image, _ = make_scene()
    monkeypatch.setattr(
        "logoscanner.ocr.read_text",
        lambda _image: [("ZPE", 0.9, (300, 160, 90, 40))],
    )
    regions = proposals.propose(image, use_mser=False)
    assert any(r.source == "text" for r in regions)


def test_region_area():
    assert Region((0, 0, 20, 5), "tile").area == 100
