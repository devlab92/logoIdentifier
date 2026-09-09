"""Turn hand-sorted `output/crops/` files into labels on the *full* images.

Reviewing crops is the fast way to judge a scan - a 200x80 mark takes a second
where the whole photo takes several. But a crop is not what the scanner sees at
scan time, so a labeled set made of crops calibrates the thresholds for a
distribution that never occurs in production (D-033). The judgement is still
good; only the file it was recorded against is wrong.

This script fixes that without asking anyone to look at anything twice: for
every `*_crop.*` file sitting in `data/labeled/positive|negative/`, it finds the
image the crop came from and copies **that** file into the same class, then
retires the crop into a backup folder.

Matching is by filename stem against `output/results.csv`. When a stem occurs in
several folders (a WordPress export reuses names across months) the crop is
matched by *content*: each candidate's crop is regenerated from its recorded box
and compared to the labeled file by perceptual hash, so the right month wins.

    python tools\\labels_from_crops.py --dry-run     # report, change nothing
    python tools\\labels_from_crops.py

Nothing is deleted: crops move to `--backup`, and a class disagreement with an
existing label is reported rather than resolved.
"""

from __future__ import annotations

import argparse
import collections
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from logoscanner import artifacts, dedup  # noqa: E402
from logoscanner.io_utils import load_image  # noqa: E402
from logoscanner.results import read_csv  # noqa: E402

CLASSES = ("positive", "negative")
CROP_MARKER = "_crop"


def is_crop(path: Path) -> bool:
    """True for a file produced by `artifacts.crop_path`, i.e. `<stem>_crop.jpg`.

    Anchored at the end on purpose: a substring test for `_crop` also matches a
    legitimate image called `cropped-flavicon.png`, and pulling that out of the
    labeled set is a silent label loss.
    """
    return path.stem.endswith(CROP_MARKER)


def flat_name(relative: str) -> str:
    """`wp_originals\\2020-08\\a.png` -> `2020-08__a.png`.

    The labeled folders are flat, and a WordPress export reuses filenames across
    months, so the immediate parent folder is kept as a prefix. Without it the
    second copy of `Lock.jpg` would silently overwrite the first - which is
    exactly how 21 crops were lost on the way into `data/labeled/`.
    """
    path = Path(relative)
    parent = path.parent.name
    return f"{parent}__{path.name}" if parent else path.name


def head_of(row) -> str:
    """The scanned original a row belongs to (itself, unless it is a copy)."""
    return row.duplicate_of or row.filename


def has_box(row) -> bool:
    """True when the row recorded a match box a crop could have come from."""
    return None not in (row.x, row.y, row.w, row.h)


def regenerated_hash(input_dir: Path, relative: str, row) -> int | None:
    """dHash of the crop this original *would* produce, for disambiguation."""
    if not has_box(row):
        return None
    image, error = load_image(input_dir / relative)
    if error:
        return None
    patch = artifacts.crop(image, (row.x, row.y, row.w, row.h))
    return None if patch is None else dedup.dhash(patch)


def choose_candidate(crop_path: Path, candidates: list[str], rows: dict,
                     input_dir: Path) -> tuple[str | None, str]:
    """Pick which of several same-stem originals this crop came from."""
    heads = {head_of(rows[name]) for name in candidates}
    if len(heads) == 1:
        # All copies of one picture - dedup already proved it. Either path is
        # the same image; use the one that was actually scanned.
        return heads.pop(), "single picture"

    image, error = load_image(crop_path)
    if error:
        return None, f"labeled crop unreadable: {error}"
    target = dedup.dhash(image)

    best, best_distance = None, None
    for name in sorted(heads):
        row = rows[name]
        if not has_box(row):
            continue
        candidate_hash = regenerated_hash(input_dir, name, row)
        if candidate_hash is None:
            continue
        distance = dedup.hamming(candidate_hash, target)
        if best_distance is None or distance < best_distance:
            best, best_distance = name, distance
    if best is None:
        return None, "no candidate could be re-cropped"
    return best, f"matched by content ({best_distance} bits)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labeled", default="data/labeled")
    parser.add_argument("--results", default="output/results.csv")
    parser.add_argument("--input", default="input")
    parser.add_argument("--backup", default=".crop_labels_backup",
                        help="where retired crop files are moved (never deleted)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    labeled, input_dir = Path(args.labeled), Path(args.input)
    rows = {row.filename: row for row in read_csv(args.results)}

    by_stem: dict[str, list[str]] = collections.defaultdict(list)
    for name in rows:
        by_stem[Path(name).stem].append(name)

    # What is already labeled, by the basename the file carries today.
    existing: dict[str, str] = {}
    for cls in CLASSES:
        for path in (labeled / cls).iterdir():
            if path.is_file() and path.name != ".gitkeep" and not is_crop(path):
                existing[path.name] = cls

    resolved: dict[str, dict[str, list[Path]]] = collections.defaultdict(
        lambda: collections.defaultdict(list))
    unmatched: list[Path] = []
    notes: dict[str, str] = {}

    for cls in CLASSES:
        for crop in sorted((labeled / cls).iterdir()):
            if not (crop.is_file() and is_crop(crop)):
                continue
            candidates = by_stem.get(crop.stem[: -len(CROP_MARKER)], [])
            if not candidates:
                unmatched.append(crop)
                continue
            if len(candidates) == 1:
                target, note = head_of(rows[candidates[0]]), "unique stem"
            else:
                target, note = choose_candidate(crop, candidates, rows, input_dir)
            if target is None:
                unmatched.append(crop)
                continue
            notes[target] = note
            resolved[target][cls].append(crop)

    conflicts = {t: c for t, c in resolved.items() if len(c) > 1}
    disagreements: list[tuple[str, str, str]] = []
    copies: list[tuple[str, str, str]] = []  # (relative, class, destination name)
    retire: list[tuple[Path, str]] = []

    for target, per_class in resolved.items():
        if len(per_class) > 1:
            continue  # the human has to settle these
        cls = next(iter(per_class))
        crops = per_class[cls]
        basename = Path(target).name
        if basename in existing:
            if existing[basename] != cls:
                disagreements.append((target, existing[basename], cls))
            else:
                retire.extend((crop, cls) for crop in crops)
            continue
        destination = flat_name(target)
        if destination in existing:
            retire.extend((crop, cls) for crop in crops)
            continue
        copies.append((target, cls, destination))
        existing[destination] = cls
        retire.extend((crop, cls) for crop in crops)

    examined = sum(len(crops) for per_class in resolved.values() for crops in per_class.values())
    print(f"crops examined             : {examined + len(unmatched)}")
    print(f"  -> originals to copy in  : {len(copies)}")
    print(f"  -> already labeled       : {len(retire) - sum(1 for _ in copies)}")
    print(f"  -> unmatched             : {len(unmatched)}")
    print(f"crops to retire into backup: {len(retire)}")
    print(f"labeled BOTH ways (skipped): {len(conflicts)}")
    print(f"disagrees with an existing label: {len(disagreements)}")
    for target, per_class in sorted(conflicts.items()):
        print(f"  CONFLICT {target}: " + ", ".join(
            f"{cls} ({len(crops)})" for cls, crops in sorted(per_class.items())))
    for target, was, now in sorted(disagreements):
        print(f"  DISAGREES {target}: already labeled {was}, crop says {now}")
    for crop in unmatched[:10]:
        print(f"  UNMATCHED {crop.name}")

    if args.dry_run:
        print("\ndry run: nothing changed")
        return 0

    backup = Path(args.backup)
    for relative, cls, destination in copies:
        source = input_dir / relative
        target_path = labeled / cls / destination
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifacts.long_path(source), artifacts.long_path(target_path))
    for crop, cls in retire:
        destination = backup / cls / crop.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(crop), str(destination))

    print(f"\ncopied {len(copies)} originals into {labeled}")
    print(f"moved {len(retire)} crops into {backup} (nothing deleted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
