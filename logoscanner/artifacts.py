r"""Review artifacts: the crops, and the copies of the images worth looking at.

A CSV with 3,000 rows is not a review tool. What a human actually needs after a
scan is two folders they can flip through in Explorer - `output/detected/` and
`output/review/` - plus `output/crops/`, which holds just the matched box out
of each flagged image. The crop is the fast path: judging a 200x80 pixel mark
takes a second, opening the full photo takes several.

Everything here mirrors the input's folder structure under the output root, so
two images called `logo.png` in different months cannot overwrite each other,
and every artifact path leads straight back to the source path in the CSV.

Nothing in here is allowed to break a scan: a crop that fails to encode or a
copy that hits a locked file is reported as a string and the run continues.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

CROPS_DIR = "crops"
DETECTED_DIR = "detected"
REVIEW_DIR = "review"

# Grown by this fraction of the box on each side: a tight box cuts the mark's
# edges off, and a little context makes the crop far easier to judge.
CROP_PAD_FRAC = 0.10
# Crops are written as JPEG - they are a human's contact sheet, not evidence.
CROP_SUFFIX = ".jpg"
CROP_QUALITY = 92


def long_path(path: Path) -> str:
    r"""Windows caps plain paths at 260 chars; the \\?\ prefix lifts that."""
    resolved = str(Path(path).resolve())
    if sys.platform == "win32" and not resolved.startswith("\\\\"):
        return rf"\\?\{resolved}"
    return resolved


def band_dir(band: str) -> str | None:
    """Folder a band's images are copied into, or None for negatives."""
    from logoscanner import config

    if band == config.BAND_POSITIVE:
        return DETECTED_DIR
    if band == config.BAND_REVIEW:
        return REVIEW_DIR
    return None


def pad_box(bbox, shape, pad_frac: float = CROP_PAD_FRAC):
    """Grow `bbox` by `pad_frac` of its own size, clipped to the image."""
    height, width = shape[:2]
    x, y, w, h = (int(v) for v in bbox)
    pad_x, pad_y = int(round(w * pad_frac)), int(round(h * pad_frac))
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(width, x + w + pad_x)
    y1 = min(height, y + h + pad_y)
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1 - x0, y1 - y0


def crop(image: np.ndarray, bbox, pad_frac: float = CROP_PAD_FRAC) -> np.ndarray | None:
    """The padded `bbox` region of `image`, or None if there is nothing to cut."""
    if image is None or image.size == 0 or not bbox:
        return None
    padded = pad_box(bbox, image.shape, pad_frac)
    if padded is None:
        return None
    x, y, w, h = padded
    patch = image[y : y + h, x : x + w]
    return patch if patch.size else None


def write_image(image: np.ndarray, dest: Path) -> Path:
    r"""Encode and write `image`, tolerating non-ASCII and long Windows paths.

    `cv2.imwrite` cannot open either, exactly as `cv2.imread` cannot, so the
    image is encoded in memory and the bytes are written by Python's own `open`
    - `ndarray.tofile` rejects the \\?\ prefix, `open` accepts it.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    params = [cv2.IMWRITE_JPEG_QUALITY, CROP_QUALITY] if dest.suffix.lower() in {".jpg", ".jpeg"} else []
    ok, buffer = cv2.imencode(dest.suffix, image, params)
    if not ok:  # pragma: no cover - encoder refusing a valid BGR array
        raise ValueError(f"could not encode {dest.suffix} image")
    with open(long_path(dest), "wb") as handle:
        handle.write(buffer.tobytes())
    return dest


def crop_path(output_dir: Path, relative: str) -> Path:
    """Where the crop of `relative` goes: same folders, `.jpg`, `_crop` suffix."""
    rel = Path(relative)
    return Path(output_dir) / CROPS_DIR / rel.parent / f"{rel.stem}_crop{CROP_SUFFIX}"


def copy_path(output_dir: Path, band: str, relative: str) -> Path | None:
    """Where the full image of `relative` is copied, or None for negatives."""
    folder = band_dir(band)
    if folder is None:
        return None
    return Path(output_dir) / folder / relative


def save(image: np.ndarray, source: Path, output_dir: Path, relative: str,
         band: str, bbox) -> str:
    """Write the crop and copy the original for a flagged image.

    Returns an empty string on success, or a short reason when an artifact
    could not be written - the caller records it and keeps scanning.
    """
    folder = band_dir(band)
    if folder is None:
        return ""
    problems = []
    if bbox:
        patch = crop(image, bbox)
        if patch is not None:
            try:
                write_image(patch, crop_path(output_dir, relative))
            except Exception as exc:
                problems.append(f"crop failed: {exc}")
    destination = copy_path(output_dir, band, relative)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(long_path(source), long_path(destination))
    except Exception as exc:
        problems.append(f"copy failed: {exc}")
    return "; ".join(problems)
