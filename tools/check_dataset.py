"""Report counts and size stats for the labeled dataset.

Usage:
    python tools/check_dataset.py [--root data/labeled]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Run as a plain script (`python tools/check_dataset.py`), so the repo root is
# not on sys.path by default.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logoscanner.io_utils import iter_images  # noqa: E402

CLASSES = ("positive", "negative")


def _stats(paths: list[Path]) -> dict:
    sizes = [path.stat().st_size for path in paths]
    total = sum(sizes)
    return {
        "count": len(paths),
        "total_mb": total / 1e6,
        "min_kb": min(sizes) / 1e3 if sizes else 0.0,
        "median_kb": sorted(sizes)[len(sizes) // 2] / 1e3 if sizes else 0.0,
        "max_kb": max(sizes) / 1e3 if sizes else 0.0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default="data/labeled", help="dataset root")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"error: {root} not found")
        return 2

    grand_total = 0
    print(f"{'class':<10}{'count':>8}{'total MB':>11}{'min KB':>10}{'med KB':>10}{'max KB':>10}")
    for name in CLASSES:
        stats = _stats(list(iter_images(root / name)))
        grand_total += stats["count"]
        print(
            f"{name:<10}{stats['count']:>8}{stats['total_mb']:>11.1f}"
            f"{stats['min_kb']:>10.1f}{stats['median_kb']:>10.1f}{stats['max_kb']:>10.1f}"
        )
    print(f"{'TOTAL':<10}{grand_total:>8}")

    if grand_total == 0:
        print("\nDataset is empty - drop labeled images into "
              f"{root / 'positive'} and {root / 'negative'}.")
    else:
        positives = len(list(iter_images(root / 'positive')))
        print(f"\npositive share: {positives / grand_total:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
