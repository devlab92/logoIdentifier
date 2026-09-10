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
MANIFEST_COLUMNS = ("sample_name", "source", "mode")


def _label_map(labeled: Path) -> dict[str, str]:
    """`{filename: class}`, each label readable under either spelling."""
    out: dict[str, str] = {}
    for cls in ("positive", "negative"):
        folder = labeled / cls
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            if not path.is_file() or path.name == ".gitkeep":
                continue
            out[path.name] = cls
            if "__" in path.name:
                out[path.name.split("__", 1)[1]] = cls
    return out


def labeled_names(labeled: Path) -> set[str]:
    """Every filename already in the labeled set, under either spelling."""
    return set(_label_map(labeled))


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
    if args.near_miss:
        # Harvesting, not measuring: the images that came closest to the review
        # line are where the misses concentrate, so reviewing them finds blind
        # spots faster than chance. The price is that this sample is chosen by
        # the detector, so it can never estimate a rate - see `report`.
        confidence = {r.filename: r.confidence for r in rows}
        sample = sorted(pool, key=lambda name: (-confidence.get(name, 0.0), name))[:count]
        mode = "near-miss"
    else:
        sample = random.Random(args.seed).sample(sorted(pool), count)
        mode = "random"

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
            writer.writerow({"sample_name": name, "source": relative, "mode": mode})

    negatives = sum(1 for r in rows if r.band == "negative" and not r.duplicate_of)
    print(f"pool of unlabeled negatives : {len(pool)}")
    if mode == "near-miss":
        scores = [r.confidence for r in rows if r.filename in set(sample)]
        print(f"taken (closest to the line) : {count}"
              f"   confidence {min(scores):.2f} - {max(scores):.2f}")
        print("mode                        : near-miss (harvest blind spots, NOT a rate)")
    else:
        print(f"sampled (seed {args.seed})           : {count}")
        print("mode                        : random (unbiased, measures the miss rate)")
    print(f"copied into                 : {out}")
    print()
    print("Now: open that folder and look at each image. If an image DOES contain")
    print(f"the logo, move it into {out / FOUND_DIR}. Leave the rest where they are.")
    print(f"Then run:  python tools\\audit_negatives.py --report --out {out}")
    print()
    print(f"(the negative band holds {negatives} unique images)")
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

    rows = [r for r in read_csv(args.results) if not r.duplicate_of]
    already = labeled_names(Path(args.labeled))
    positives = {name for name, cls in _label_map(Path(args.labeled)).items()
                 if cls == "positive"}

    # Recall counts *confirmed* logos, not flagged images: only 520 of the 1,165
    # images this scanner flagged actually carry the mark, so
    # flagged / (flagged + missed) would silently answer a different question.
    found = sum(1 for r in rows if r.band != "negative" and Path(r.filename).name in positives)
    negatives = [r for r in rows if r.band == "negative"]
    known_misses = sum(1 for r in negatives if Path(r.filename).name in positives)
    # The sample was drawn from the unlabeled negatives, so the rate applies to
    # those only; misses among the labeled ones are already counted exactly.
    pool = sum(1 for r in negatives
               if Path(r.filename).name not in already
               and flat_name(r.filename) not in already)

    mode = entries[0].get("mode", "random") if entries else "random"
    print(f"sample size          : {total}  ({mode})")
    print(f"reviewed             : {reviewed}" + ("" if reviewed == total else "  (INCOMPLETE)"))
    print(f"logos found in it    : {hits}")

    if mode != "random":
        # A sample the detector chose cannot measure the detector. Reporting a
        # rate off it would read as a 10x worse miss rate purely because these
        # images were picked for being borderline.
        print()
        print("This sample was chosen by confidence, not at random, so it says nothing")
        print("about the miss rate - it exists to FIND misses, not to count them.")
        print(f"Add the {hits} image(s) in {FOUND_DIR} to data/labeled/positive/ and recalibrate;")
        print("keep the random sample for the measurement.")
        if unknown:
            print(f"\nwarning: {len(unknown)} file(s) in {FOUND_DIR} are not from this sample")
        return 0

    low, high = wilson(hits, total)
    rate = hits / total
    print(f"miss rate            : {rate:.1%}  (95% CI {low:.1%} - {high:.1%})")
    print()
    print(f"{pool} unlabeled images sit in the negative band, so the logos hiding there number")
    print(f"  roughly {round(low * pool)} to {round(high * pool)}, best guess {round(rate * pool)}"
          f"  (+{known_misses} already known)")
    if found:
        def recall(missed: float) -> float:
            return found / (found + missed + known_misses)
        print()
        print(f"against {found} confirmed logos the scanner did surface, true recall is")
        print(f"  {recall(rate * pool):.1%}   (range {recall(high * pool):.1%} - "
              f"{recall(low * pool):.1%})")
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
    parser.add_argument("--near-miss", action="store_true", dest="near_miss",
                        help="take the images closest to the review line instead of a random "
                             "sample: finds blind spots faster, but cannot measure a rate")
    parser.add_argument("--report", action="store_true",
                        help="summarise a sample a human has finished sorting")
    args = parser.parse_args(argv)
    return report(args) if args.report else prepare(args)


if __name__ == "__main__":
    raise SystemExit(main())
