"""Single source of tunables for LogoScanner.

Everything a human may want to adjust lives here; modules import from this file
rather than hard-coding constants. Threshold values are placeholders until
phase04 calibrates them on the labeled dataset.
"""

from __future__ import annotations

# --- Brand -----------------------------------------------------------------
# Set by the user in phase02. Add spellings the OCR is likely to produce.
# Order does not matter; matching is case-insensitive and fuzzy (phase02+).
BRAND_TERMS = ["ZPE", "ZPE Systems"]

# --- Input handling --------------------------------------------------------
# Extensions the walker accepts (lowercase, dot included). `.avif` needs the
# Pillow fallback in `io_utils.load_image` (D-016).
IMAGE_EXTS = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff", ".avif"}
)

# Longest side an image is downscaled to before any analysis. Keeps CPU cost
# predictable; large enough that a small logo survives.
MAX_SIDE = 1600

# --- Signals ---------------------------------------------------------------
# Detectors the pipeline runs, in order. Names come from the registry in
# `signals.py`; unknown names are rejected at startup.
ENABLED_SIGNALS = ("ocr",)

# OCR signal (phase02). A detected line must reach OCR_MIN_FUZZ similarity to a
# brand term to count at all, and strings shorter than OCR_MIN_TEXT_LEN letters
# are ignored — a two-letter fragment fuzzy-matches almost anything.
OCR_MIN_FUZZ = 80.0
OCR_MIN_TEXT_LEN = 3

# --- Confidence bands ------------------------------------------------------
# Recall first: anything uncertain lands in REVIEW, never silently in NEGATIVE.
BAND_POSITIVE = "positive"
BAND_REVIEW = "review"
BAND_NEGATIVE = "negative"
BANDS = (BAND_POSITIVE, BAND_REVIEW, BAND_NEGATIVE)

# Provisional (phase02) — calibrated on the labeled set in phase04.
# confidence >= POSITIVE_THRESHOLD          -> positive
# REVIEW_THRESHOLD <= confidence < POSITIVE -> review
# confidence <  REVIEW_THRESHOLD            -> negative
POSITIVE_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.60


def band_for(confidence: float) -> str:
    """Map a confidence score in [0, 1] to its band name."""
    if confidence >= POSITIVE_THRESHOLD:
        return BAND_POSITIVE
    if confidence >= REVIEW_THRESHOLD:
        return BAND_REVIEW
    return BAND_NEGATIVE
