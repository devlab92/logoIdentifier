"""Duplicate detection: exact bytes (SHA-256) and near-identical pixels (dHash).

A collection assembled from a website is full of the same picture saved twice:
byte-identical copies in two folders, and re-encodes that differ in a handful
of JPEG artifacts. Both cost a full signal pass (~2 s each) and, worse, they
pad the review pile with images the human already judged. So every file is
hashed twice - once over its bytes, once over its downscaled pixels - and a hit
copies the original's verdict instead of re-running the pipeline (D-030).

The perceptual hash is the classic 64-bit dHash, written here with OpenCV
rather than pulled in as a dependency: resize to 9x8 grayscale, then one bit
per horizontal neighbour pair saying "brighter than the pixel to its right".
Small edits (recompression, mild resizing) leave almost every bit alone, so a
Hamming distance of a few bits still means "the same picture".
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np

# dHash geometry: (width + 1) x height, one bit per horizontal neighbour pair.
DHASH_SIZE = 8
# Bits that may differ and still count as the same image. 4/64 tolerates
# recompression and small rescales without merging genuinely different photos.
DHASH_MAX_DISTANCE = 4
# Read size for the byte hash; large enough that 10k files cost seconds.
_CHUNK = 1 << 20

# A flat image (all black, all white, a solid colour placeholder) produces no
# "brighter than" bit at all, so *every* flat image hashes to 0 regardless of
# its colour. Those two hashes therefore prove nothing and are never matched.
_DEGENERATE = frozenset({0, (1 << (DHASH_SIZE * DHASH_SIZE)) - 1})


def sha256_file(path: str | Path) -> str:
    """Hex SHA-256 of the file's bytes, read in chunks. Raises on IO errors."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dhash(image: np.ndarray, size: int = DHASH_SIZE) -> int:
    """64-bit difference hash of a BGR (or gray) image, as an int."""
    if image is None or image.size == 0:
        return 0
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (size + 1, size), interpolation=cv2.INTER_AREA)
    bits = small[:, :-1] > small[:, 1:]
    value = 0
    for bit in bits.flatten():
        value = (value << 1) | int(bit)
    return value


def hamming(left: int, right: int) -> int:
    """Number of differing bits between two hashes."""
    return int(left ^ right).bit_count()


def format_hash(value: int | None, size: int = DHASH_SIZE) -> str:
    """Fixed-width hex, so journal lines stay aligned and parseable."""
    if value is None:
        return ""
    return f"{value:0{size * size // 4}x}"


def parse_hash(text: str) -> int | None:
    """Inverse of `format_hash`; empty or unparseable text becomes None."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return int(text, 16)
    except ValueError:
        return None


class DuplicateIndex:
    """Remembers what has been seen so a repeat can borrow the first verdict.

    `find` returns the path of the earlier image, or None. Byte-identical hits
    are answered from a dict; near hits need a scan over the stored perceptual
    hashes, which is linear but costs microseconds against the ~2 s a signal
    pass takes, so it never shows up in the throughput.
    """

    def __init__(self, max_distance: int = DHASH_MAX_DISTANCE):
        self.max_distance = int(max_distance)
        self._by_sha: dict[str, str] = {}
        self._by_dhash: list[tuple[int, str]] = []

    def __len__(self) -> int:
        return len(self._by_sha) + len(self._by_dhash)

    def add(self, path: str, sha: str | None = None, image_hash: int | None = None) -> None:
        """Register `path` as an original future files may be duplicates of."""
        if sha:
            self._by_sha.setdefault(sha, path)
        if image_hash is not None and image_hash not in _DEGENERATE:
            self._by_dhash.append((image_hash, path))

    def find_by_sha(self, sha: str | None) -> str | None:
        """Path of the first file with these exact bytes, if any."""
        return self._by_sha.get(sha) if sha else None

    def find_by_hash(self, image_hash: int | None) -> str | None:
        """Path of the closest earlier image within `max_distance` bits."""
        if image_hash is None or image_hash in _DEGENERATE:
            return None
        best, best_distance = None, self.max_distance + 1
        for stored, path in self._by_dhash:
            distance = hamming(stored, image_hash)
            if distance < best_distance:
                best, best_distance = path, distance
                if distance == 0:
                    break
        return best
