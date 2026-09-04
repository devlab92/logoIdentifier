"""Collect original images from a WordPress uploads tree.

WordPress stores one upload as many files: the original plus generated
thumbnails (``name-150x150.jpg``), alternate formats (``.webp``/``.avif``
from optimizer plugins) and optimizer backups (``name.bak.jpg``).
This tool walks ``uploads/<year>/<month>/`` and copies **one** file per
logical image into ``<dest>/<YYYY-MM>/<original name>``, ready for
LogoScanner (which walks recursively).

Filenames are never rewritten: the month folder keeps same-named uploads
from different months apart, so the WordPress name survives untouched for
later work that needs to match a file back to its post.

Selection rule, per group of files that share a stem:
  1. the file with no ``-WIDTHxHEIGHT`` suffix wins (the true original);
  2. otherwise ``-scaled`` wins;
  3. otherwise the largest ``WIDTHxHEIGHT`` wins.
Ties are broken by format preference (png/jpg > webp > avif > gif) and
then by file size.

Usage (see docs/SETUP.md):
    python tools/wp_collect.py --dry-run
    python tools/wp_collect.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif", ".bmp", ".tif", ".tiff"}

# Format preference: lower is better. Originals are almost always jpg/png;
# webp/avif in a WP tree are plugin-generated conversions.
FORMAT_RANK = {".png": 0, ".jpg": 0, ".jpeg": 0, ".tif": 1, ".tiff": 1, ".bmp": 1,
               ".gif": 2, ".webp": 3, ".avif": 4}

SIZE_SUFFIX = re.compile(r"^(?P<stem>.+)-(?P<w>\d{1,5})x(?P<h>\d{1,5})$")
SCALED_SUFFIX = re.compile(r"^(?P<stem>.+)-scaled$", re.IGNORECASE)
MONTH_DIR = re.compile(r"^\d{1,2}$")


@dataclass
class Candidate:
    path: Path
    stem: str          # grouping key (size/scaled suffix removed)
    area: int          # 0 when the file carries no size suffix
    scaled: bool
    ext: str
    size: int

    def rank(self) -> tuple:
        """Sort key — smaller is better."""
        kind = 0 if self.area == 0 and not self.scaled else (1 if self.scaled else 2)
        return (kind, -self.area, FORMAT_RANK.get(self.ext, 9), -self.size)


def classify(path: Path) -> Candidate | None:
    """Return a Candidate, or None when the file is not a collectable image."""
    ext = path.suffix.lower()
    if ext not in IMAGE_EXTS:
        return None
    name = path.stem
    if name.lower().endswith(".bak"):        # optimizer backup copy
        return None

    area, scaled = 0, False
    m = SIZE_SUFFIX.match(name)
    if m:
        name = m.group("stem")
        area = int(m.group("w")) * int(m.group("h"))
    m = SCALED_SUFFIX.match(name)
    if m:
        name = m.group("stem")
        scaled = True

    return Candidate(path=path, stem=name, area=area, scaled=scaled,
                     ext=ext, size=path.stat().st_size)


def year_dirs(source: Path, first: int, last: int) -> list[Path]:
    out = []
    for child in sorted(source.iterdir()):
        if child.is_dir() and child.name.isdigit() and first <= int(child.name) <= last:
            out.append(child)
    return out


def scan(source: Path, first: int, last: int) -> tuple[dict, int]:
    """Group every image under uploads/<year>/<month>/ by its logical stem."""
    groups: dict[tuple[str, str], list[Candidate]] = defaultdict(list)
    seen = 0
    for ydir in year_dirs(source, first, last):
        for mdir in sorted(p for p in ydir.iterdir() if p.is_dir() and MONTH_DIR.match(p.name)):
            for path in sorted(mdir.rglob("*")):
                if not path.is_file():
                    continue
                seen += 1
                cand = classify(path)
                if cand is not None:
                    # Group per month folder: the same name in two months is
                    # two different uploads.
                    groups[(f"{ydir.name}-{int(mdir.name):02d}", cand.stem)].append(cand)
    return groups, seen


def long_path(path: Path) -> str:
    r"""Windows caps plain paths at 260 chars; the \\?\ prefix lifts that."""
    resolved = str(path.resolve())
    if sys.platform == "win32" and not resolved.startswith("\\\\"):
        return rf"\\?\{resolved}"
    return resolved


def fit_name(dest_dir: Path, name: str, limit: int = 255) -> str:
    """Return `name` unchanged unless it would blow the Windows path limit.

    Most Windows tooling (numpy, cv2, Explorer) still refuses paths over 260
    chars even though the copy itself succeeds. Only the handful of names that
    would cross that line get shortened, with a hash to keep them unique; the
    manifest always carries the untouched WordPress name.
    """
    room = limit - len(str(dest_dir.resolve())) - 1
    if len(name) <= room:
        return name
    stem, dot, ext = name.rpartition(".")
    tag = hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]
    return f"{stem[:max(1, room - len(ext) - len(dot) - 7)]}~{tag}{dot}{ext}"


def sha1(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with open(long_path(path), "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=Path,
                    default=Path(r"C:\Users\barbierl\OneDrive - Legrand France"
                                 r"\Desktop\WP\wp-content\uploads"),
                    help="WordPress uploads folder")
    ap.add_argument("--dest", type=Path, default=root / "input" / "wp_originals",
                    help="destination folder for the collected originals")
    ap.add_argument("--years", default="2014-2026", help="year range, e.g. 2014-2026")
    ap.add_argument("--dry-run", action="store_true", help="report only, copy nothing")
    ap.add_argument("--dedupe", action="store_true",
                    help="skip byte-identical uploads instead of keeping every one")
    args = ap.parse_args(argv)

    first, _, last = args.years.partition("-")
    first, last = int(first), int(last or first)

    if not args.source.is_dir():
        print(f"source folder not found: {args.source}", file=sys.stderr)
        return 1

    groups, seen = scan(args.source, first, last)
    print(f"scanned {seen} files under {args.source}")
    print(f"found {len(groups)} distinct images ({first}-{last})")

    args.dest.mkdir(parents=True, exist_ok=True)
    manifest = args.dest.parent / f"{args.dest.name}_manifest.csv"

    copied = skipped_dupe = 0
    hashes: dict[str, str] = {}
    rows = []
    for (period, stem), cands in sorted(groups.items()):
        best = min(cands, key=Candidate.rank)
        variants = len(cands) - 1
        reason = ("original" if best.area == 0 and not best.scaled
                  else "scaled" if best.scaled else "largest-variant")
        # Filenames are kept exactly as WordPress stored them; the month folder
        # carries the provenance and keeps same-named uploads apart.
        name = fit_name(args.dest / period, best.path.name)
        rel = f"{period}/{name}"
        note = "" if name == best.path.name else "shortened-for-path-limit"

        if not args.dry_run and args.dedupe:
            digest = sha1(best.path)
            if digest in hashes:
                rows.append((best.path, "", reason, variants, "duplicate-of:" + hashes[digest]))
                skipped_dupe += 1
                continue
            hashes[digest] = rel

        if not args.dry_run:
            dest = args.dest / period / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(long_path(best.path), long_path(dest))
        rows.append((best.path, rel, reason, variants, note))
        copied += 1

    with manifest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "dest_relpath", "original_name", "reason",
                    "variants_ignored", "note"])
        for src, rel, reason, variants, note in rows:
            w.writerow([str(src), rel, src.name, reason, variants, note])

    verb = "would copy" if args.dry_run else "copied"
    print(f"{verb} {copied} images -> {args.dest}")
    if skipped_dupe:
        print(f"skipped {skipped_dupe} byte-identical duplicates")
    print(f"manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
