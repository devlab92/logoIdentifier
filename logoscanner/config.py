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
ENABLED_SIGNALS = ("ocr", "sift", "emb")

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

# --- Region proposals (phase05) --------------------------------------------
# The embedding signal cannot compare a whole photo against a logo variant: the
# mark is a few percent of the pixels and its signature drowns. `proposals.py`
# therefore cuts candidate boxes out of the image first. Sources, in priority
# order: OCR line boxes (a stylised wordmark is still *text* to the detector,
# even when it reads as gibberish), the SIFT projected quad, MSER stable
# regions, and a coarse tile grid that guarantees coverage when the others find
# nothing.
PROPOSAL_MAX_REGIONS = 24

# Each proposal is grown by this fraction of its own size: a tight text box
# clips the symbol sitting next to the words.
PROPOSAL_PAD_FRAC = 0.15

# Boxes outside this area range (fraction of the image) are dropped - specks
# carry no signal, and a near-full-frame crop is just the tile fallback again.
PROPOSAL_MIN_AREA_FRAC = 0.0004
PROPOSAL_MAX_AREA_FRAC = 0.90

# Two proposals overlapping by more than this IoU are merged into their union.
PROPOSAL_MERGE_IOU = 0.55

# Coarse fallback grid (N x N tiles, plus the whole frame).
PROPOSAL_TILE_GRID = 3

# MSER stable-region detector: a logo on a flat background is exactly the kind
# of blob it was built to find.
PROPOSAL_MSER_DELTA = 5
PROPOSAL_MSER_MIN_AREA = 120
PROPOSAL_MSER_MAX_AREA_FRAC = 0.25

# --- Embedding signal (phase05) --------------------------------------------
# DINOv2-small via timm, CPU, no fine-tuning: a self-supervised ViT whose
# features separate "this is the ZPE mark" from "this is some other logo"
# without us training anything (D-024).
EMB_MODEL = "vit_small_patch14_dinov2.lvd142m"
EMB_INPUT_SIZE = 126  # multiple of the model's patch size (14)
EMB_BATCH_SIZE = 24  # >= PROPOSAL_MAX_REGIONS: one forward pass per image
# Torch threads; 0 leaves torch's own default alone.
EMB_THREADS = 0
# Cosine similarity below this is not even worth reporting as a partial match.
EMB_MIN_SIMILARITY = 0.30

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
# Calibrated on the labeled set, 2026-09-10.
SIGNAL_THRESHOLDS: dict[str, tuple[float, float]] = {
    # signal: (weak, strong)
    "emb": (0.85, 0.90),
    "ocr": (0.65, 0.75),
    "sift": (0.30, 0.30),
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
