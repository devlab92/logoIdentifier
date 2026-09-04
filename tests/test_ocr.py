"""Brand-term matching rules and one end-to-end OCR smoke test."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from logoscanner import config, ocr
from logoscanner.ocr import OcrSignal, compact, match_text, normalize

TERMS = ["ZPE", "ZPE Systems"]


def render_text(text: str, size=(200, 640), scale: float = 2.0) -> np.ndarray:
    """White canvas with black text - the easiest possible case for OCR."""
    image = np.full((size[0], size[1], 3), 255, dtype=np.uint8)
    cv2.putText(
        image, text, (30, size[0] // 2 + 20), cv2.FONT_HERSHEY_SIMPLEX,
        scale, (0, 0, 0), 4, cv2.LINE_AA,
    )
    return image


def test_normalize_folds_case_punctuation_and_whitespace():
    assert normalize("  ZPE,  Systems!  ") == "zpe systems"
    assert normalize("Z.P.E.") == "z p e"
    assert normalize("") == ""


def test_compact_drops_the_spaces_normalize_introduces():
    assert compact("Z.P.E. Systems") == "zpesystems"


@pytest.mark.parametrize(
    "text",
    [
        "ZPE",
        "zpe",
        "  ZPE  ",
        "Z.P.E.",  # letter-spaced lockup
        "ZPESystems",  # glued
        "ZPE Systems, Inc.",  # brand inside a longer line
        "Welcome to ZPE Systems",
    ],
)
def test_brand_spellings_match(text):
    score, term = match_text(text, TERMS)
    assert score >= 90 and term in TERMS


def test_ocr_typos_are_tolerated_up_to_the_floor():
    # One misread glyph in a long term still matches...
    assert match_text("2PE Systems", TERMS)[0] >= config.OCR_MIN_FUZZ
    # ...an unrelated word of the same shape does not.
    assert match_text("AC1VIE", TERMS) == (0.0, "")
    assert match_text("ACME", TERMS) == (0.0, "")


@pytest.mark.parametrize("text", ["ems", "stems", "systs", "the size of it", "SUPPORT"])
def test_fragments_of_a_term_do_not_score_as_the_brand(text):
    # `partial_ratio` would call "ems" a perfect substring of "zpe systems";
    # the length rule in `_pair_ratio` is what stops it.
    assert match_text(text, TERMS)[0] < config.OCR_MIN_FUZZ


@pytest.mark.parametrize("text", ["", "z", "zp", "  ,  "])
def test_trivially_short_text_is_ignored(text):
    assert match_text(text, TERMS) == (0.0, "")


def test_terms_shorter_than_the_minimum_are_skipped():
    assert match_text("some heading", ["Z"]) == (0.0, "")


def test_min_fuzz_is_the_only_gate(monkeypatch):
    monkeypatch.setattr(config, "OCR_MIN_FUZZ", 100.0)
    assert match_text("2PE Systems", TERMS) == (0.0, "")
    monkeypatch.setattr(config, "OCR_MIN_FUZZ", 50.0)
    assert match_text("2PE Systems", TERMS)[0] > 50.0


def test_ocr_signal_reads_brand_text_and_localises_it():
    """Smoke test: the real engine on a rendered brand term."""
    result = OcrSignal().run(render_text(config.BRAND_TERMS[0]))
    assert result.name == "ocr"
    assert result.score > 0.7
    x, y, w, h = result.bbox
    assert w > 20 and h > 10 and 0 <= x < 640 and 0 <= y < 200


def test_ocr_signal_stays_silent_on_unrelated_text():
    result = OcrSignal().run(render_text("QUARTERLY"))
    assert result.score == 0.0 and result.bbox is None


def test_engine_failures_become_a_zero_score_not_an_exception(monkeypatch):
    def boom(image):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(ocr, "read_text", boom)
    result = OcrSignal().run(np.zeros((10, 10, 3), dtype=np.uint8))
    assert result.score == 0.0
    assert result.detail.startswith("error: RuntimeError")


def test_engine_is_built_once_per_process():
    assert ocr.get_engine() is ocr.get_engine()
