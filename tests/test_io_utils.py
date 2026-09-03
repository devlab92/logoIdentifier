"""Walker and safe-loader behaviour."""

from __future__ import annotations

import cv2
import numpy as np

from logoscanner.io_utils import downscale, iter_images, load_image


def _write_png(path, height=40, width=60):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((height, width, 3), 128, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", image)
    assert ok
    buf.tofile(str(path))
    return path


def test_walker_finds_images_recursively_and_skips_junk(tmp_path):
    _write_png(tmp_path / "a.png")
    _write_png(tmp_path / "nested" / "b.JPG")  # uppercase extension counts
    (tmp_path / "notes.txt").write_text("not an image", encoding="utf-8")
    (tmp_path / "Thumbs.db").write_bytes(b"junk")
    (tmp_path / ".hidden.png").write_bytes(b"junk")
    (tmp_path / "emptydir").mkdir()

    names = sorted(path.name for path in iter_images(tmp_path))
    assert names == ["a.png", "b.JPG"]


def test_walker_on_missing_root_yields_nothing(tmp_path):
    assert list(iter_images(tmp_path / "does_not_exist")) == []


def test_load_image_returns_bgr_array(tmp_path):
    path = _write_png(tmp_path / "ok.png", height=30, width=50)
    image, error = load_image(path)
    assert error is None
    assert image.shape == (30, 50, 3)


def test_corrupt_file_is_reported_not_raised(tmp_path):
    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"\x89PNG\r\n\x1a\n" + b"garbage" * 10)
    image, error = load_image(corrupt)
    assert image is None
    assert "decode failed" in error


def test_empty_file_is_reported(tmp_path):
    empty = tmp_path / "empty.jpg"
    empty.write_bytes(b"")
    image, error = load_image(empty)
    assert image is None
    assert error == "empty file"


def test_missing_file_is_reported(tmp_path):
    image, error = load_image(tmp_path / "nope.png")
    assert image is None
    assert error


def test_downscale_caps_longest_side_and_never_upscales():
    big = np.zeros((900, 3000, 3), dtype=np.uint8)
    assert max(downscale(big, 1600).shape[:2]) == 1600
    small = np.zeros((10, 20, 3), dtype=np.uint8)
    assert downscale(small, 1600).shape == small.shape


def test_load_image_downscales_large_input(tmp_path):
    path = _write_png(tmp_path / "big.png", height=500, width=2400)
    image, error = load_image(path, max_side=1000)
    assert error is None
    assert max(image.shape[:2]) == 1000
