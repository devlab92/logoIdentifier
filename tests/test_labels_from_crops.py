"""Repairing a labeled set that had `output/crops/` files sorted into it (D-033).

This tool moves files inside `data/labeled/`, which is hand-curated data, so the
cases that matter are the ones where it must *refuse* to guess: two originals
sharing a filename, a label that already exists, and a judgement that
contradicts one.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

import labels_from_crops
from logoscanner import artifacts
from logoscanner.results import ResultRow, write_csv

BOX = (20, 20, 60, 40)


def _picture(seed: int, size=(120, 160)) -> np.ndarray:
    """A textured image; the box region has to be distinctive to be matchable."""
    rng = np.random.default_rng(seed)
    image = np.zeros((*size, 3), np.uint8)
    for _ in range(8):
        x, y = int(rng.integers(0, size[1] - 30)), int(rng.integers(0, size[0] - 30))
        cv2.rectangle(image, (x, y), (x + 30, y + 30),
                      [int(v) for v in rng.integers(20, 240, 3)], -1)
    cv2.rectangle(image, (BOX[0], BOX[1]), (BOX[0] + BOX[2], BOX[1] + BOX[3]),
                  [int(v) for v in rng.integers(0, 255, 3)], -1)
    cv2.circle(image, (BOX[0] + 30, BOX[1] + 20), 12, (255, 255, 255), -1)
    return image


@pytest.fixture
def workspace(tmp_path):
    """An input tree, a results.csv describing it, and empty labeled folders."""
    (tmp_path / "input").mkdir()
    for cls in ("positive", "negative"):
        (tmp_path / "labeled" / cls).mkdir(parents=True)
    return tmp_path


def _write_original(workspace, relative: str, seed: int) -> np.ndarray:
    path = workspace / "input" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    image = _picture(seed)
    artifacts.write_image(image, path)
    return image


def _write_crop(workspace, cls: str, stem: str, image: np.ndarray) -> None:
    """Put the crop of `image` into the labeled folder, as the human did."""
    patch = artifacts.crop(image, BOX)
    artifacts.write_image(patch, workspace / "labeled" / cls / f"{stem}_crop.jpg")


def _results(workspace, rows: list[ResultRow]) -> None:
    write_csv(rows, workspace / "results.csv")


def _run(workspace, *extra) -> int:
    return labels_from_crops.main([
        "--labeled", str(workspace / "labeled"),
        "--results", str(workspace / "results.csv"),
        "--input", str(workspace / "input"),
        "--backup", str(workspace / "backup"),
        *extra,
    ])


def _labeled(workspace, cls: str) -> set[str]:
    return {p.name for p in (workspace / "labeled" / cls).iterdir() if p.is_file()}


def test_a_crop_is_replaced_by_the_full_image_it_came_from(workspace):
    image = _write_original(workspace, "2020-01/pic.png", seed=1)
    _results(workspace, [ResultRow("2020-01/pic.png", True, "positive", 0.9, *BOX, "ocr")])
    _write_crop(workspace, "positive", "pic", image)

    assert _run(workspace) == 0

    assert _labeled(workspace, "positive") == {"2020-01__pic.png"}
    assert (workspace / "backup" / "positive" / "pic_crop.jpg").is_file()
    # The label is now the original file, byte for byte.
    assert (workspace / "labeled" / "positive" / "2020-01__pic.png").read_bytes() == (
        workspace / "input" / "2020-01" / "pic.png"
    ).read_bytes()


def test_same_filename_in_two_months_is_settled_by_content(workspace):
    """The crop must land on the month it was actually cut from, not the first."""
    first = _write_original(workspace, "2020-01/pic.png", seed=2)
    _write_original(workspace, "2020-02/pic.png", seed=99)
    _results(workspace, [
        ResultRow("2020-01/pic.png", True, "positive", 0.9, *BOX, "ocr"),
        ResultRow("2020-02/pic.png", True, "positive", 0.9, *BOX, "ocr"),
    ])
    _write_crop(workspace, "positive", "pic", first)

    _run(workspace)

    assert _labeled(workspace, "positive") == {"2020-01__pic.png"}


def test_copies_of_one_picture_resolve_to_the_scanned_original(workspace):
    """A duplicate row is not a separate candidate: it points at its original."""
    image = _write_original(workspace, "2020-01/pic.png", seed=3)
    _write_original(workspace, "2021-05/pic.png", seed=3)
    _results(workspace, [
        ResultRow("2020-01/pic.png", True, "positive", 0.9, *BOX, "ocr"),
        ResultRow("2021-05/pic.png", True, "positive", 0.9, *BOX, "ocr",
                  duplicate_of="2020-01/pic.png"),
    ])
    _write_crop(workspace, "positive", "pic", image)

    _run(workspace)

    assert _labeled(workspace, "positive") == {"2020-01__pic.png"}


def test_an_already_labeled_original_is_not_copied_twice(workspace):
    image = _write_original(workspace, "2020-01/pic.png", seed=4)
    _results(workspace, [ResultRow("2020-01/pic.png", True, "positive", 0.9, *BOX, "ocr")])
    _write_crop(workspace, "positive", "pic", image)
    # The same image was already labeled by hand in an earlier phase.
    artifacts.write_image(image, workspace / "labeled" / "positive" / "pic.png")

    _run(workspace)

    assert _labeled(workspace, "positive") == {"pic.png"}
    assert (workspace / "backup" / "positive" / "pic_crop.jpg").is_file()


def test_a_contradicted_label_is_reported_and_left_alone(workspace, capsys):
    """The old label wins by default; a human settles it, not this script."""
    image = _write_original(workspace, "2020-01/pic.png", seed=5)
    _results(workspace, [ResultRow("2020-01/pic.png", True, "positive", 0.9, *BOX, "ocr")])
    _write_crop(workspace, "negative", "pic", image)
    artifacts.write_image(image, workspace / "labeled" / "positive" / "pic.png")

    _run(workspace)
    out = capsys.readouterr().out

    assert "DISAGREES" in out
    assert _labeled(workspace, "positive") == {"pic.png"}
    assert "pic.png" not in _labeled(workspace, "negative")
    # The crop stays put: nothing was decided, so nothing was retired.
    assert (workspace / "labeled" / "negative" / "pic_crop.jpg").is_file()


def test_one_original_labeled_both_ways_is_skipped(workspace, capsys):
    image = _write_original(workspace, "2020-01/pic.png", seed=6)
    _results(workspace, [ResultRow("2020-01/pic.png", True, "positive", 0.9, *BOX, "ocr")])
    _write_crop(workspace, "positive", "pic", image)
    _write_crop(workspace, "negative", "pic", image)

    _run(workspace)

    assert "CONFLICT" in capsys.readouterr().out
    assert _labeled(workspace, "positive") == {"pic_crop.jpg"}
    assert _labeled(workspace, "negative") == {"pic_crop.jpg"}


def test_a_crop_with_no_matching_original_is_reported_not_guessed(workspace, capsys):
    _results(workspace, [ResultRow("2020-01/other.png", True, "positive", 0.9, *BOX, "ocr")])
    blank = _picture(seed=7)
    artifacts.write_image(artifacts.crop(blank, BOX),
                          workspace / "labeled" / "positive" / "unknown_crop.jpg")

    _run(workspace)

    assert "UNMATCHED" in capsys.readouterr().out
    assert _labeled(workspace, "positive") == {"unknown_crop.jpg"}


def test_dry_run_changes_nothing(workspace):
    image = _write_original(workspace, "2020-01/pic.png", seed=8)
    _results(workspace, [ResultRow("2020-01/pic.png", True, "positive", 0.9, *BOX, "ocr")])
    _write_crop(workspace, "positive", "pic", image)

    _run(workspace, "--dry-run")

    assert _labeled(workspace, "positive") == {"pic_crop.jpg"}
    assert not (workspace / "backup").exists()


def test_flat_name_keeps_the_month_and_survives_a_flat_path():
    assert labels_from_crops.flat_name("wp_originals/2020-08/a.png") == "2020-08__a.png"
    assert labels_from_crops.flat_name("a.png") == "a.png"


def test_a_file_named_cropped_is_not_mistaken_for_a_crop(workspace):
    """`cropped-flavicon.png` contains `_crop` but is a label, not a crop.

    A substring test for `_crop` would both retire this legitimate image and
    fail to register it as already labeled - which then copies the same picture
    in a second time under its prefixed name.
    """
    image = _write_original(workspace, "2020-07/cropped-flavicon.png", seed=9)
    _results(workspace, [
        ResultRow("2020-07/cropped-flavicon.png", True, "positive", 0.9, *BOX, "ocr")])
    artifacts.write_image(image, workspace / "labeled" / "positive" / "cropped-flavicon.png")
    # ...and its crop, which *is* a crop and must be the only thing retired.
    _write_crop(workspace, "positive", "cropped-flavicon", image)

    _run(workspace)

    assert _labeled(workspace, "positive") == {"cropped-flavicon.png"}, (
        "the legitimate label was retired, or copied in a second time"
    )
    assert (workspace / "backup" / "positive" / "cropped-flavicon_crop.jpg").is_file()


def test_is_crop_anchors_at_the_end_of_the_stem():
    from pathlib import Path as P

    assert labels_from_crops.is_crop(P("a/pic_crop.jpg"))
    assert not labels_from_crops.is_crop(P("a/cropped-flavicon.png"))
    assert not labels_from_crops.is_crop(P("a/_cropland.png"))
    assert not labels_from_crops.is_crop(P("a/pic.png"))


def test_rows_without_a_box_cannot_disambiguate_but_do_not_crash(workspace, capsys):
    first = _write_original(workspace, "2020-01/pic.png", seed=10)
    _write_original(workspace, "2020-02/pic.png", seed=11)
    _results(workspace, [
        ResultRow("2020-01/pic.png", False, "negative", 0.0, method="none"),
        ResultRow("2020-02/pic.png", False, "negative", 0.0, method="none"),
    ])
    _write_crop(workspace, "positive", "pic", first)

    _run(workspace)

    assert "UNMATCHED" in capsys.readouterr().out
    assert _labeled(workspace, "positive") == {"pic_crop.jpg"}
