"""Single source of tunables for LogoScanner.

Everything a human may want to adjust lives here; modules import from this file
rather than hard-coding constants. Threshold values are placeholders until
phase04 calibrates them on the labeled dataset.
"""

from __future__ import annotations

# --- Brand -----------------------------------------------------------------
# TODO(user): set the real terms before running on company images.
# Order does not matter; matching is case-insensitive and fuzzy (phase02+).
BRAND_TERMS = ["ACME", "ACME Systems"]

# --- Input handling --------------------------------------------------------
# Extensions the walker accepts (lowercase, dot included).
IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"})

# Longest side an image is downscaled to before any analysis. Keeps CPU cost
# predictable; large enough that a small logo survives.
MAX_SIDE = 1600

# --- Confidence bands ------------------------------------------------------
# Recall first: anything uncertain lands in REVIEW, never silently in NEGATIVE.
BAND_POSITIVE = "positive"
BAND_REVIEW = "review"
BAND_NEGATIVE = "negative"
BANDS = (BAND_POSITIVE, BAND_REVIEW, BAND_NEGATIVE)

# Placeholders — calibrated in phase04.
# confidence >= POSITIVE_THRESHOLD          -> positive
# REVIEW_THRESHOLD <= confidence < POSITIVE -> review
# confidence <  REVIEW_THRESHOLD            -> negative
POSITIVE_THRESHOLD = 0.75
REVIEW_THRESHOLD = 0.35


def band_for(confidence: float) -> str:
    """Map a confidence score in [0, 1] to its band name."""
    if confidence >= POSITIVE_THRESHOLD:
        return BAND_POSITIVE
    if confidence >= REVIEW_THRESHOLD:
        return BAND_REVIEW
    return BAND_NEGATIVE
