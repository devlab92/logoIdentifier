"""SIFT signal: match the logo *symbol* by keypoints, at any scale or rotation.

The OCR signal (phase02) is blind to a logo that carries no legible text - a
bare mark, a heavily stylised wordmark, a tiny corner watermark. This signal
covers that case: SIFT descriptors are computed once per variant found in
`config.LOGO_DIR`, matched against every scanned image with a Lowe ratio test,
and the surviving matches must agree on a single homography (RANSAC) before
anything is reported. That geometric step is what keeps precision usable -
texture-rich photos produce plenty of stray descriptor matches, but they do not
line up into a consistent projection of the logo's rectangle.

Scoring is `inliers / SIFT_SCORE_NORM`, clamped to 1: a match is only as strong
as the number of keypoints that survived verification.

The signal degrades quietly: an empty or missing `logo/` warns once and then
scores 0 for every image, so a scan still runs on OCR alone.
"""

from __future__ import annotations

import threading
import warnings
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from logoscanner import config
from logoscanner.signals import BBox, SignalResult, register

SIGNAL_NAME = "sift"

_cache_lock = threading.Lock()
_template_cache: dict[str, tuple["Template", ...]] = {}


@dataclass(frozen=True)
class Template:
    """One logo variant: its grayscale size and its precomputed descriptors."""

    name: str
    shape: tuple[int, int]  # height, width of the (possibly upscaled) variant
    keypoints: tuple
    descriptors: np.ndarray

    @property
    def corners(self) -> np.ndarray:
        """The variant's own four corners, ready for `perspectiveTransform`."""
        height, width = self.shape
        return np.float32(
            [[0, 0], [width, 0], [width, height], [0, height]]
        ).reshape(-1, 1, 2)


def make_detector():
    """A fresh SIFT detector (OpenCV detectors are not safe to share)."""
    return cv2.SIFT_create()


def to_gray(image: np.ndarray) -> np.ndarray:
    """Grayscale view of a BGR, BGRA or already-gray array.

    Transparent pixels are filled with the extreme opposite of the mark's own
    brightness (black behind a white logo, white behind a dark one) instead of
    a fixed colour, which would erase a white-on-transparent variant.
    """
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        alpha = image[:, :, 3]
        gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
        opaque = alpha > 0
        fill = 0 if opaque.any() and float(gray[opaque].mean()) > 127 else 255
        gray = gray.copy()
        gray[~opaque] = fill
        return gray
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _upscale_to(gray: np.ndarray, min_side: int) -> np.ndarray:
    """Enlarge a small variant so SIFT has enough pixels to find keypoints."""
    height, width = gray.shape[:2]
    shortest = min(height, width)
    if shortest <= 0 or shortest >= min_side:
        return gray
    scale = min_side / shortest
    size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
    return cv2.resize(gray, size, interpolation=cv2.INTER_CUBIC)


def load_variant(path: Path) -> np.ndarray | None:
    """Read one logo file as grayscale with alpha handled, or None on failure."""
    try:
        buf = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if buf.size == 0:
        return None
    image = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    if image is None:
        return None
    return to_gray(image)


def build_templates(logo_dir: str | Path, detector=None) -> tuple[Template, ...]:
    """Compute descriptors for every readable image in `logo_dir`.

    Variants that yield too few descriptors (a flat colour block, an unreadable
    file) are dropped rather than carried as dead weight.
    """
    logo_dir = Path(logo_dir)
    detector = detector or make_detector()
    templates: list[Template] = []
    if not logo_dir.is_dir():
        return ()
    for path in sorted(logo_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in config.IMAGE_EXTS:
            continue
        gray = load_variant(path)
        if gray is None or gray.size == 0:
            continue
        gray = _upscale_to(gray, config.SIFT_MIN_SIDE)
        keypoints, descriptors = detector.detectAndCompute(gray, None)
        if descriptors is None or len(descriptors) < config.SIFT_MIN_GOOD:
            continue
        templates.append(
            Template(
                name=path.name,
                shape=(gray.shape[0], gray.shape[1]),
                keypoints=tuple(keypoints),
                descriptors=descriptors,
            )
        )
    return tuple(templates)


def get_templates(logo_dir: str | Path) -> tuple[Template, ...]:
    """`build_templates`, memoised per directory (descriptors cost real time)."""
    key = str(Path(logo_dir).resolve())
    cached = _template_cache.get(key)
    if cached is None:
        with _cache_lock:
            cached = _template_cache.get(key)
            if cached is None:
                cached = build_templates(logo_dir)
                _template_cache[key] = cached
    return cached


def clear_cache() -> None:
    """Forget memoised templates (tests, or a logo folder edited mid-session)."""
    with _cache_lock:
        _template_cache.clear()


def good_matches(
    template_descriptors: np.ndarray, image_descriptors: np.ndarray, image_keypoints=None
) -> list:
    """Lowe ratio test over k=2 nearest neighbours, template -> image.

    Kept one match per image *location*: a logo built from repeated geometry (a
    symbol whose corners all look alike) sends many template descriptors to the
    same spot in the image, and RANSAC then happily "verifies" the transform
    that folds the whole logo onto that one point — dozens of inliers, no real
    match. Collapsing those duplicates removes the degenerate consensus at the
    source. Locations are rounded to a pixel because SIFT reports several
    keypoints (different scale or orientation) at one position.
    """
    if image_descriptors is None or len(image_descriptors) < 2:
        return []
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    pairs = matcher.knnMatch(template_descriptors, image_descriptors, k=2)
    best_per_spot: dict[tuple, cv2.DMatch] = {}
    for pair in pairs:
        if len(pair) != 2:
            continue
        match, runner_up = pair
        if match.distance >= config.SIFT_RATIO * runner_up.distance:
            continue
        if image_keypoints is None:
            spot = (match.trainIdx,)
        else:
            x, y = image_keypoints[match.trainIdx].pt
            spot = (round(x), round(y))
        current = best_per_spot.get(spot)
        if current is None or match.distance < current.distance:
            best_per_spot[spot] = match
    return list(best_per_spot.values())


def plausible_box(corners: np.ndarray, image_shape) -> bool:
    """Is this projected quad a believable placement of the logo?

    RANSAC will happily return a homography that folds the logo into a sliver
    or throws it off the canvas. Cheap checks reject those: the quad must be
    convex (no bow-tie), have real area, keep sane edge lengths and aspect, and
    be centred inside the image. Partial visibility is still allowed - the quad
    may extend past the border, it just may not live outside it.
    """
    points = np.asarray(corners, dtype=np.float32).reshape(-1, 2)
    if points.shape[0] != 4 or not np.isfinite(points).all():
        return False

    height, width = image_shape[:2]
    image_area = float(height * width)
    if image_area <= 0:
        return False

    contour = points.reshape(-1, 1, 2)
    if not cv2.isContourConvex(contour.astype(np.int32)):
        return False

    area = abs(cv2.contourArea(contour))
    if not (
        config.SIFT_MIN_AREA_FRAC * image_area
        <= area
        <= config.SIFT_MAX_AREA_FRAC * image_area
    ):
        return False

    edges = [float(np.linalg.norm(points[i] - points[(i + 1) % 4])) for i in range(4)]
    if min(edges) < config.SIFT_MIN_EDGE_PX:
        return False
    if max(edges) / min(edges) > config.SIFT_MAX_EDGE_RATIO:
        return False

    center = points.mean(axis=0)
    return 0 <= center[0] < width and 0 <= center[1] < height


def _bbox_from(corners: np.ndarray, scale: float, image_shape) -> BBox:
    """Axis-aligned box of the quad, back in original-image coordinates."""
    points = np.asarray(corners, dtype=np.float32).reshape(-1, 2) / max(scale, 1e-6)
    height, width = image_shape[:2]
    x0 = int(max(0, np.floor(points[:, 0].min())))
    y0 = int(max(0, np.floor(points[:, 1].min())))
    x1 = int(min(width, np.ceil(points[:, 0].max())))
    y1 = int(min(height, np.ceil(points[:, 1].max())))
    return x0, y0, max(1, x1 - x0), max(1, y1 - y0)


class SiftSignal:
    """Keypoint-match signal. Templates and detector load on first `run`."""

    name = SIGNAL_NAME

    def __init__(self, logo_dir: str | Path | None = None):
        self.logo_dir = Path(config.LOGO_DIR if logo_dir is None else logo_dir)
        self._detector = None
        self._warned = False

    @property
    def detector(self):
        if self._detector is None:
            self._detector = make_detector()
        return self._detector

    def templates(self) -> tuple[Template, ...]:
        """Cached templates for this signal's logo folder; warns once if empty."""
        found = get_templates(self.logo_dir)
        if not found and not self._warned:
            self._warned = True
            warnings.warn(
                f"no usable logo variants in {self.logo_dir}: "
                f"the {self.name!r} signal will score 0 for every image",
                RuntimeWarning,
                stacklevel=2,
            )
        return found

    def run(self, image: np.ndarray) -> SignalResult:
        templates = self.templates()
        if not templates:
            return SignalResult(self.name, 0.0, None, f"no logo variants in {self.logo_dir}")
        try:
            return self._match(image, templates)
        except Exception as exc:  # a bad frame must never abort a 10k-image scan
            return SignalResult(self.name, 0.0, None, f"error: {type(exc).__name__}: {exc}")

    def _match(self, image: np.ndarray, templates) -> SignalResult:
        gray = to_gray(image)
        height, width = gray.shape[:2]
        scale = min(1.0, config.MAX_SIDE / max(height, width, 1))
        if scale < 1.0:
            gray = cv2.resize(
                gray,
                (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
                interpolation=cv2.INTER_AREA,
            )
        keypoints, descriptors = self.detector.detectAndCompute(gray, None)
        if descriptors is None or len(descriptors) < 2:
            return SignalResult(self.name, 0.0, None, "no keypoints")

        best_score, best_box, best_detail, best_good = 0.0, None, "", 0
        for template in templates:
            matches = good_matches(template.descriptors, descriptors, keypoints)
            best_good = max(best_good, len(matches))
            if len(matches) < config.SIFT_MIN_GOOD:
                continue
            source = np.float32(
                [template.keypoints[m.queryIdx].pt for m in matches]
            ).reshape(-1, 1, 2)
            target = np.float32(
                [keypoints[m.trainIdx].pt for m in matches]
            ).reshape(-1, 1, 2)
            homography, mask = cv2.findHomography(
                source, target, cv2.RANSAC, config.SIFT_RANSAC_REPROJ
            )
            if homography is None or mask is None:
                continue
            inliers = int(mask.sum())
            if inliers < config.SIFT_MIN_INLIERS:
                continue
            corners = cv2.perspectiveTransform(template.corners, homography)
            if not plausible_box(corners, gray.shape):
                continue
            score = min(1.0, inliers / config.SIFT_SCORE_NORM)
            if score > best_score:
                best_score = score
                best_box = _bbox_from(corners, scale, image.shape)
                best_detail = f"{template.name} good={len(matches)} inliers={inliers}"
        if best_score == 0.0:
            best_detail = (
                f"no verified match ({len(descriptors)} keypoints, "
                f"best {best_good} good matches)"
            )
        return SignalResult(self.name, best_score, best_box, best_detail)


@register(SIGNAL_NAME)
def _build() -> SiftSignal:
    return SiftSignal()
