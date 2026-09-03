"""Command line interface: `python -m logoscanner <command>`.

phase01 ships `scan` (walk + load + report, no detection yet) and `version`.
Later phases add `benchmark` (phase02) and `calibrate` (phase04).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from tqdm import tqdm

from logoscanner import __version__
from logoscanner import config
from logoscanner.io_utils import iter_images, load_image
from logoscanner.results import (
    CSV_NAME,
    JSON_NAME,
    ResultRow,
    summarize,
    write_csv,
    write_json,
)


def run_scan(
    input_dir: str | Path,
    output_dir: str | Path,
    limit: int | None = None,
    progress: bool = True,
) -> dict:
    """Scan `input_dir`, write CSV + JSON into `output_dir`, return the summary.

    phase01 has no detector, so every readable image is scored 0.0 / negative;
    the point is the walk, the safe load and the throughput measurement.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    paths = list(iter_images(input_dir))
    if limit is not None:
        paths = paths[:limit]

    rows: list[ResultRow] = []
    start = time.perf_counter()
    for path in tqdm(paths, desc="scanning", unit="img", disable=not progress):
        try:
            relative = str(path.relative_to(input_dir))
        except ValueError:  # pragma: no cover - path is always under input_dir
            relative = str(path)
        image, error = load_image(path)
        if error:
            rows.append(ResultRow(filename=relative, error=error, method="none"))
            continue
        # No signals yet — phase02 onwards fills confidence / band / box.
        rows.append(
            ResultRow(
                filename=relative,
                contains_logo=False,
                band=config.BAND_NEGATIVE,
                confidence=0.0,
                method="none",
            )
        )
    seconds = time.perf_counter() - start

    summary = summarize(rows, seconds)
    summary["input"] = str(input_dir)
    write_csv(rows, output_dir / CSV_NAME)
    write_json(summary, output_dir / JSON_NAME)
    return summary


def _format_duration(seconds: float | None) -> str:
    """Human-readable h/m/s, for the 10k ETA line."""
    if seconds is None:
        return "n/a"
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def print_report(summary: dict, output_dir: Path) -> None:
    """Print the throughput report described by phase01 step 3."""
    bands = summary["bands"]
    print()
    print(f"Scanned    : {summary['images']} images from {summary['input']}")
    print(f"Bands      : " + "  ".join(f"{name}={bands.get(name, 0)}" for name in config.BANDS))
    print(f"Errors     : {summary['errors']}")
    print(f"Elapsed    : {summary['seconds']:.2f} s")
    print(f"Throughput : {summary['images_per_second']:.2f} img/s")
    print(f"ETA 10,000 : {_format_duration(summary['eta_10k_seconds'])}")
    print(f"Report     : {output_dir / CSV_NAME}")
    print(f"Summary    : {output_dir / JSON_NAME}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logoscanner",
        description="Offline scanner that flags images containing the company logo.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="scan a folder of images")
    scan.add_argument("--input", required=True, help="folder to scan (recursive)")
    scan.add_argument("--output", required=True, help="folder for results.csv / summary.json")
    scan.add_argument("--limit", type=int, default=None, help="stop after N images")
    scan.add_argument("--no-progress", action="store_true", help="hide the progress bar")

    sub.add_parser("version", help="print the version and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "version":
        print(f"logoscanner {__version__}")
        return 0

    if args.command == "scan":
        input_dir = Path(args.input)
        if not input_dir.is_dir():
            print(f"error: input folder not found: {input_dir}")
            return 2
        output_dir = Path(args.output)
        summary = run_scan(
            input_dir, output_dir, limit=args.limit, progress=not args.no_progress
        )
        print_report(summary, output_dir)
        return 0

    return 2  # pragma: no cover - argparse rejects unknown commands first
