"""Filesystem walking and safe image loading.

Nothing in here raises on bad input: a file that cannot be decoded comes back
as an error string so the scan can record it and keep going.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

from logoscanner.config import IMAGE_EXTS, MAX_SIDE

# Files that look like images to a human but never are.
_JUNK_NAMES = frozenset({"thumbs.db", "desktop.ini", ".ds_store"})


def iter_images(root: str | Path) -> Iterator[Path]:
    """Yield image files under `root`, recursively, in a stable sorted order.

    Filters on `IMAGE_EXTS` (case-insensitive), skips known junk files and
    dot-files. A missing or non-directory `root` yields nothing.
    """
    root = Path(root)
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.lower() in _JUNK_NAMES or path.name.startswith("."):
            continue
        if path.suffix.lower() not in IMAGE_EXTS:
            continue
        yield path


def load_image(path: str | Path, max_side: int | None = MAX_SIDE):
    """Load `path` as a BGR array, downscaled so its longest side <= max_side.

    Returns `(image, None)` on success and `(None, "reason")` on failure —
    never raises. `max_side=None` disables downscaling.
    """
    path = Path(path)
    try:
        # np.fromfile + imdecode instead of cv2.imread: imread cannot open
        # non-ASCII paths on Windows.
        buf = np.fromfile(str(path), dtype=np.uint8)
    except OSError as exc:
        return None, f"read failed: {exc.strerror or exc}"

    if buf.size == 0:
        return None, "empty file"

    image = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if image is None:
        return None, "decode failed (corrupt or unsupported format)"

    if max_side:
        image = downscale(image, max_side)
    return image, None


def downscale(image: np.ndarray, max_side: int = MAX_SIDE) -> np.ndarray:
    """Shrink `image` so its longest side is `max_side`. Never upscales."""
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_side:
        return image
    scale = max_side / longest
    new_size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)
