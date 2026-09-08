"""Byte-identical and near-identical duplicate detection (phase07)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from logoscanner.dedup import (
    DHASH_MAX_DISTANCE,
    DuplicateIndex,
    dhash,
    format_hash,
    hamming,
    parse_hash,
    sha256_file,
)


def _picture(seed: int = 3, size=(160, 240)) -> np.ndarray:
    """A textured image: flat noise would make every dHash bit a coin flip."""
    rng = np.random.default_rng(seed)
    height, width = size
    base = np.zeros((height, width, 3), np.uint8)
    for i in range(6):
        x, y = int(rng.integers(0, width - 40)), int(rng.integers(0, height - 40))
        color = [int(v) for v in rng.integers(30, 230, 3)]
        cv2.rectangle(base, (x, y), (x + 40, y + 40), color, -1)
    cv2.circle(base, (width // 2, height // 2), 30, (250, 250, 250), -1)
    return base


def test_sha256_matches_for_identical_bytes_and_differs_otherwise(tmp_path):
    first = tmp_path / "a.bin"
    first.write_bytes(b"logo" * 1000)
    same = tmp_path / "b.bin"
    same.write_bytes(b"logo" * 1000)
    other = tmp_path / "c.bin"
    other.write_bytes(b"logo" * 1000 + b"!")

    assert sha256_file(first) == sha256_file(same)
    assert sha256_file(first) != sha256_file(other)
    assert len(sha256_file(first)) == 64


def test_sha256_raises_on_a_missing_file(tmp_path):
    with pytest.raises(OSError):
        sha256_file(tmp_path / "nope.bin")


def test_dhash_is_stable_and_64_bits():
    image = _picture()
    value = dhash(image)
    assert value == dhash(image.copy())
    assert 0 <= value < 1 << 64
    assert len(format_hash(value)) == 16


def test_dhash_survives_recompression_and_rescaling(tmp_path):
    """The whole point: a re-encode is the same picture, a few bits aside."""
    image = _picture(seed=7)
    path = tmp_path / "q40.jpg"
    cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, 40])
    recompressed = cv2.imread(str(path))
    rescaled = cv2.resize(image, (image.shape[1] // 2, image.shape[0] // 2))

    assert hamming(dhash(image), dhash(recompressed)) <= DHASH_MAX_DISTANCE
    assert hamming(dhash(image), dhash(rescaled)) <= DHASH_MAX_DISTANCE


def test_dhash_separates_different_pictures():
    assert hamming(dhash(_picture(seed=1)), dhash(_picture(seed=99))) > DHASH_MAX_DISTANCE


def test_dhash_of_nothing_is_zero():
    assert dhash(None) == 0
    assert dhash(np.zeros((0, 0, 3), np.uint8)) == 0


def test_hash_text_round_trip():
    value = dhash(_picture(seed=5))
    assert parse_hash(format_hash(value)) == value
    assert format_hash(None) == ""
    assert parse_hash("") is None
    assert parse_hash("not hex") is None


def test_index_finds_exact_bytes():
    index = DuplicateIndex()
    index.add("first.png", sha="abc", image_hash=dhash(_picture()))
    assert index.find_by_sha("abc") == "first.png"
    assert index.find_by_sha("other") is None
    assert index.find_by_sha(None) is None


def test_index_finds_a_near_duplicate_but_not_a_different_image():
    original, other = _picture(seed=2), _picture(seed=42)
    index = DuplicateIndex()
    index.add("first.png", sha="abc", image_hash=dhash(original))

    nudged = dhash(original) ^ 0b1011  # three bits of difference
    assert index.find_by_hash(nudged) == "first.png"
    assert index.find_by_hash(dhash(other)) is None
    assert index.find_by_hash(None) is None


def test_index_respects_its_distance_budget():
    strict = DuplicateIndex(max_distance=0)
    value = dhash(_picture(seed=8))
    strict.add("first.png", sha="abc", image_hash=value)
    assert strict.find_by_hash(value) == "first.png"
    assert strict.find_by_hash(value ^ 0b1) is None


def test_flat_images_never_match_each_other():
    """All-black and all-white both hash to 0; that is not a similarity."""
    black = np.zeros((80, 80, 3), np.uint8)
    white = np.full((80, 80, 3), 255, np.uint8)
    assert dhash(black) == dhash(white) == 0

    index = DuplicateIndex()
    index.add("black.png", sha="a", image_hash=dhash(black))
    assert index.find_by_hash(dhash(white)) is None
    assert len(index) == 1  # registered by bytes only


def test_index_returns_the_closest_match():
    value = dhash(_picture(seed=11))
    index = DuplicateIndex()
    index.add("far.png", sha="a", image_hash=value ^ 0b1110)
    index.add("near.png", sha="b", image_hash=value)
    assert index.find_by_hash(value) == "near.png"
