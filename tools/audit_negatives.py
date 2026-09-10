"""Measure how many logos the scanner is *missing*, with an honest sample.

Every recall number the project has published is measured on images the
detector already flagged, or on a labeled set built from them. That is
circular: it tells you how often the scanner is right about what it found, not
how often it found everything. The only way to break the circle is to look at
images the scanner *rejected*, chosen at random rather than by the scanner.

So this tool takes a random sample of the `negative` band - excluding
duplicates, failures and anything already labeled - copies the **full images**
into a folder, and waits. A human moves the ones that do contain the logo into
`has_logo/`. Then `--report` counts them and turns that count into a miss rate
with a confidence interval, because 0 out of 100 does not mean zero.

    python tools\\audit_negatives.py --count 100        # prepare the sample
    ... a human sorts them ...
    python tools\\audit_negatives.py --report           # what it means

The sample is drawn with a fixed seed, so the same command always produces the
same images and the audit can be repeated or checked by someone else.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from logoscanner import artifacts  # noqa: E402
from logoscanner.results import read_csv  # noqa: E402

MANIFEST = "manifest.csv"
FOUND_DIR = "has_logo"
MANIFEST_COLUMNS = ("sample_name", "source")


def labeled_names(labeled: Path) -> set[str]:
    """Every filename already in the labeled set, with the `<month>__` prefix
    stripped as well, so an image is recognised under either spelling."""
    names: set[str] = set()
    for cls in ("positive", "negative"):
        folder = labeled / cls
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            if not path.is_file() or path.name == ".gitkeep":
                continue
            names.add(path.name)
            if "__" in path.name:
                names.add(path.name.split("__", 1)[1])
    return names


def flat_name(relative: str) -> str:
    """`wp_originals/2020-08/a.png` -> `2020-08__a.png` (the folders are flat)."""
    path = Path(relative)
    return f"{path.parent.name}__{path.name}" if path.parent.name else path.name


def candidates(rows, already: set[str]) -> list[str]:
    """Unique, readable, unlabeled images the scanner put in `negative`.

    Duplicates are excluded because they carry a copied verdict rather than one
    the scanner reached by looking - sampling them would measure the dedup, not
    the detector.
    """
    out = []
    for row in rows:
        if row.band != "negative" or row.duplicate_of or row.error:
            continue
        if Path(row.filename).name in already or flat_name(row.filename) in already:
            continue
        out.append(row.filename)
    return out


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval for a proportion, usable when the count is 0.

    The naive interval collapses to (0, 0) on a clean sample, which would claim
    certainty no sample can buy. Wilson's does not.
    """
    if total == 0:
        return 0.0, 1.0
    phat = successes / total
    denominator = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def prepare(args) -> int:
    rows = read_csv(args.results)
    pool = candidates(rows, labeled_names(Path(args.labeled)))
    if not pool:
        print("nothing to audit: every negative is already labeled")
        return 1

    count = min(args.count, len(pool))
    sample = random.Random(args.seed).sample(sorted(pool), count)

    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        print(f"error: {out} already exists and is not empty - move it aside or pass --out")
        return 2
    (out / FOUND_DIR).mkdir(parents=True, exist_ok=True)

    with (out / MANIFEST).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(MANIFEST_COLUMNS))
        writer.writeheader()
        for relative in sample:
            name = flat_name(relative)
            shutil.copy2(artifacts.long_path(Path(args.input) / relative),
                         artifacts.long_path(out / name))
            writer.writerow({"sample_name": name, "source": relative})

    negatives = sum(1 for r in rows if r.band == "negative" and not r.duplicate_of)
    print(f"pool of unlabeled negatives : {len(pool)}")
    print(f"sampled (seed {args.seed})           : {count}")
    print(f"copied into                 : {out}")
    print()
    print("Now: open that folder and look at each image. If an image DOES contain")
    print(f"the logo, move it into {out / FOUND_DIR}. Leave the rest where they are.")
    print(f"Then run:  python tools\\audit_negatives.py --report --out {out}")
    print()
    print(f"(this measures a band holding {negatives} unique images)")
    return 0


def report(args) -> int:
    out = Path(args.out)
    manifest = out / MANIFEST
    if not manifest.is_file():
        print(f"error: no {manifest} - run without --report first")
        return 2
    with manifest.open(encoding="utf-8", newline="") as handle:
        entries = list(csv.DictReader(handle))

    found_dir = out / FOUND_DIR
    found = {p.name for p in found_dir.iterdir() if p.is_file()} if found_dir.is_dir() else set()
    known = {row["sample_name"] for row in entries}
    unknown = found - known
    hits = len(found & known)
    total = len(entries)
    reviewed = hits + sum(1 for row in entries if (out / row["sample_name"]).is_file())

    rows = read_csv(args.results)
    negatives = sum(1 for r in rows if r.band == "negative" and not r.duplicate_of)
    flagged = sum(1 for r in rows if r.band != "negative" and not r.duplicate_of)

    low, high = wilson(hits, total)
    print(f"sample size          : {total}")
    print(f"reviewed             : {reviewed}" + ("" if reviewed == total else "  (INCOMPLETE)"))
    print(f"logos found in it    : {hits}")
    print(f"miss rate            : {hits / total:.1%}  (95% CI {low:.1%} - {high:.1%})")
    print()
    print(f"the negative band holds {negatives} unique images, so that is roughly")
    print(f"  {round(low * negatives)} to {round(high * negatives)} logos sitting in it, best guess {round(hits / total * negatives)}")
    if flagged:
        best = hits / total * negatives
        print()
        print(f"against {flagged} images the scanner did flag, that puts true recall near")
        print(f"  {flagged / (flagged + best):.1%}  (best guess; the CI above is the honest spread)")
    if unknown:
        print(f"\nwarning: {len(unknown)} file(s) in {FOUND_DIR} are not from this sample "
              f"and were ignored")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", default="output/results.csv")
    parser.add_argument("--input", default="input")
    parser.add_argument("--labeled", default="data/labeled")
    parser.add_argument("--out", default="output/audit")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--report", action="store_true",
                        help="summarise a sample a human has finished sorting")
    args = parser.parse_args(argv)
    return report(args) if args.report else prepare(args)


if __name__ == "__main__":
    raise SystemExit(main())
