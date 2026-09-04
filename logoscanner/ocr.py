"""OCR signal: read the text in an image and fuzzy-match it to `BRAND_TERMS`.

RapidOCR (ONNX Runtime, models bundled with the wheel - see D-002) detects text
lines; each line is normalised and compared against every brand term with
RapidFuzz. The score of a line is `fuzz/100 x ocr_confidence`, and the signal
reports the best line plus its box.

Matching notes:
- Two normalisations are compared and the better one wins: a *spaced* form
  ("z.p.e. systems" -> "z p e systems") and a *compact* form ("zpesystems").
  Logos routinely letter-space or glue the brand name together.
- `partial_ratio` is used only when the detected text is at least as long as
  the term, i.e. when asking "does this line contain the brand?". If the line
  is shorter, plain `ratio` is used so a three-letter fragment of a longer
  line cannot claim a perfect score (see D-013).
"""

from __future__ import annotations

import re
import threading

import numpy as np
from rapidfuzz import fuzz

from logoscanner import config
from logoscanner.signals import BBox, SignalResult, register

SIGNAL_NAME = "ocr"

_NON_ALNUM = re.compile(r"[^0-9a-z]+")
_WHITESPACE = re.compile(r"\s+")

_engine_lock = threading.Lock()
_engine = None


def get_engine():
    """Build the RapidOCR engine once per process (init costs ~2 s)."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from rapidocr_onnxruntime import RapidOCR  # heavy import, kept lazy

                _engine = RapidOCR()
    return _engine


def normalize(text: str) -> str:
    """Casefold, turn punctuation into spaces, collapse runs of whitespace."""
    return _WHITESPACE.sub(" ", _NON_ALNUM.sub(" ", (text or "").casefold())).strip()


def compact(text: str) -> str:
    """`normalize` with every space removed ("Z P E" -> "zpe")."""
    return normalize(text).replace(" ", "")


def _pair_ratio(term: str, candidate: str) -> float:
    """Fuzzy similarity of `term` against `candidate`, 0..100.

    Substring search only when the candidate is the longer string; otherwise a
    whole-string ratio, which penalises the length gap.
    """
    if not term or not candidate:
        return 0.0
    if len(candidate) >= len(term):
        return fuzz.partial_ratio(term, candidate)
    return fuzz.ratio(term, candidate)


def match_text(text: str, terms=None) -> tuple[float, str]:
    """Best fuzzy match of `text` against the brand terms.

    Returns `(fuzz 0..100, matched term)`; `(0.0, "")` when nothing clears
    `config.OCR_MIN_FUZZ` or the strings are too short to judge.
    """
    terms = config.BRAND_TERMS if terms is None else terms
    spaced, glued = normalize(text), compact(text)
    if len(glued) < config.OCR_MIN_TEXT_LEN:
        return 0.0, ""

    best, best_term = 0.0, ""
    for term in terms:
        term_spaced, term_glued = normalize(term), compact(term)
        if len(term_glued) < config.OCR_MIN_TEXT_LEN:
            continue  # a one- or two-letter term matches everything
        score = max(
            _pair_ratio(term_spaced, spaced),
            _pair_ratio(term_glued, glued),
        )
        if score > best:
            best, best_term = score, term
    if best < config.OCR_MIN_FUZZ:
        return 0.0, ""
    return float(best), best_term


def _to_bbox(polygon) -> BBox:
    """Axis-aligned box of RapidOCR's 4-point polygon."""
    points = np.asarray(polygon, dtype=np.float32).reshape(-1, 2)
    x0, y0 = points.min(axis=0)
    x1, y1 = points.max(axis=0)
    return int(x0), int(y0), max(1, int(round(x1 - x0))), max(1, int(round(y1 - y0)))


def read_text(image: np.ndarray) -> list[tuple[str, float, BBox]]:
    """Run OCR and return `(text, confidence, bbox)` per detected line."""
    result, _elapse = get_engine()(image)
    if not result:
        return []
    return [(str(text), float(conf), _to_bbox(poly)) for poly, text, conf in result]


class OcrSignal:
    """Brand-name-in-text signal. Engine loads on first `run`."""

    name = SIGNAL_NAME

    def run(self, image: np.ndarray) -> SignalResult:
        try:
            lines = read_text(image)
        except Exception as exc:  # OCR must never abort a 10k-image scan
            return SignalResult(self.name, 0.0, None, f"error: {type(exc).__name__}: {exc}")

        best_score, best_box, best_detail = 0.0, None, ""
        for text, confidence, bbox in lines:
            ratio, term = match_text(text)
            if not ratio:
                continue
            score = (ratio / 100.0) * confidence
            if score > best_score:
                best_score = score
                best_box = bbox
                best_detail = f"{text!r}~{term} fuzz={ratio:.0f} conf={confidence:.2f}"
        if best_score == 0.0:
            best_detail = f"no brand text ({len(lines)} lines read)"
        return SignalResult(self.name, best_score, best_box, best_detail)


@register(SIGNAL_NAME)
def _build() -> OcrSignal:
    return OcrSignal()
