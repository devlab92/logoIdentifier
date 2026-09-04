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
ENABLED_SIGNALS = ("ocr", "sift")

# OCR signal (phase02). A detected line must reach OCR_MIN_FUZZ similarity to a
# brand term to count at all, and strings shorter than OCR_MIN_TEXT_LEN letters
# are ignored — a two-letter fragment fuzzy-matches almost anything.
OCR_MIN_FUZZ = 80.0
OCR_MIN_TEXT_LEN = 3

# SIFT signal (phase03). Folder holding the real logo variants; local-only and
# gitignored. Empty or missing => the signal warns once and scores 0.
LOGO_DIR = "logo"

# Variants shorter than this on their short side are upscaled before their
# descriptors are computed — a 40 px mark yields almost no keypoints.
SIFT_MIN_SIDE = 300

# Lowe ratio test: a descriptor match counts only if it beats the runner-up by
# this factor. 0.75 is Lowe's own value; lower = stricter.
SIFT_RATIO = 0.75

# A match must clear SIFT_MIN_GOOD ratio-test survivors before a homography is
# even attempted, and SIFT_MIN_INLIERS of them must then agree on it. RANSAC
# reprojection tolerance is in pixels of the analysed (downscaled) image.
SIFT_MIN_GOOD = 8
SIFT_MIN_INLIERS = 8
SIFT_RANSAC_REPROJ = 5.0

# Score = min(1, inliers / SIFT_SCORE_NORM). With the provisional bands below,
# a match reaches `review` at 15 inliers and `positive` at 22 — the effective
# weak/strong thresholds of this signal until phase04 calibrates them.
SIFT_SCORE_NORM = 25.0

# Sanity checks on the projected logo quad (see `keypoints.plausible_box`):
# area as a fraction of the image, shortest edge in pixels, longest/shortest
# edge ratio. They reject the folded or off-canvas homographies RANSAC returns
# when the matches are really noise.
SIFT_MIN_AREA_FRAC = 0.0002
SIFT_MAX_AREA_FRAC = 4.0
SIFT_MIN_EDGE_PX = 8.0
SIFT_MAX_EDGE_RATIO = 12.0

# --- Confidence bands ------------------------------------------------------
# Recall first: anything uncertain lands in REVIEW, never silently in NEGATIVE.
BAND_POSITIVE = "positive"
BAND_REVIEW = "review"
BAND_NEGATIVE = "negative"
BANDS = (BAND_POSITIVE, BAND_REVIEW, BAND_NEGATIVE)

# Anchors of the *normalized* confidence scale (D-021). Raw signal scores are
# not comparable across signals, so `decision.normalize` maps each signal's
# score onto one common scale where its weak threshold lands on
# REVIEW_THRESHOLD and its strong threshold on POSITIVE_THRESHOLD. The mapping
# is monotonic, not a probability, and keeps `band_for(confidence)` in step
# with the band the decision engine actually assigned.
POSITIVE_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.50

# Per-signal decision thresholds: score >= strong -> positive, >= weak ->
# review, else negative (`decision.decide`). Signals with no entry here fall
# back to FALLBACK_THRESHOLDS.
# --- calibrated thresholds (written by `logoscanner calibrate`) ------------
# Calibrated on the labeled set, 2026-09-04.
SIGNAL_THRESHOLDS: dict[str, tuple[float, float]] = {
    # signal: (weak, strong)
    "ocr": (0.60, 0.95),
    "sift": (0.45, 0.45),
}
# --- end calibrated thresholds ---------------------------------------------

# Used for any signal missing from SIGNAL_THRESHOLDS (a brand-new detector
# benchmarked before its own calibration run).
FALLBACK_THRESHOLDS: tuple[float, float] = (0.60, 0.85)

# --- Calibration & the gate ------------------------------------------------
# `calibrate` maximises precision subject to these two constraints; the same
# two are the phase04 gate targets (met => the ML phases are unnecessary).
TARGET_CATCH_RECALL = 0.97
TARGET_REVIEW_SHARE = 0.10

# Threshold grid searched by `calibrate` (0.05 steps; 0 is excluded on purpose
# — a weak threshold of 0 would send every image to review).
CALIBRATION_GRID = tuple(round(0.05 * i, 2) for i in range(1, 21))


def band_for(confidence: float) -> str:
    """Map a *normalized* confidence in [0, 1] to its band name."""
    if confidence >= POSITIVE_THRESHOLD:
        return BAND_POSITIVE
    if confidence >= REVIEW_THRESHOLD:
        return BAND_REVIEW
    return BAND_NEGATIVE
