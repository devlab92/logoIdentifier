"""Command line interface: `python -m logoscanner <command>`.

`scan` walks a folder and writes the reports, `benchmark` measures each signal
on a labeled set, `calibrate` (phase04) tunes the per-signal thresholds on that
same set and writes them into `config.py`, and `version` prints the version.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from tqdm import tqdm

from logoscanner import __version__
from logoscanner import config, signals
from logoscanner.benchmark import run_benchmark
from logoscanner.calibrate import run_calibration
from logoscanner.io_utils import iter_images, load_image
from logoscanner.pipeline import build_pipeline
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
    signals=None,
) -> dict:
    """Scan `input_dir`, write CSV + JSON into `output_dir`, return the summary.

    Every readable image goes through the signal pipeline; `decision.decide`
    bands it against the calibrated per-signal thresholds in `config`.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    pipeline = build_pipeline(signals)

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
        rows.append(pipeline.run(image).to_row(relative))
    seconds = time.perf_counter() - start

    summary = summarize(rows, seconds)
    summary["input"] = str(input_dir)
    summary["signals"] = list(pipeline.names)
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
    print(f"Signals    : " + ", ".join(summary.get("signals") or ["none"]))
    print(f"Bands      : " + "  ".join(f"{name}={bands.get(name, 0)}" for name in config.BANDS))
    print(f"Errors     : {summary['errors']}")
    print(f"Elapsed    : {summary['seconds']:.2f} s")
    print(f"Throughput : {summary['images_per_second']:.2f} img/s")
    print(f"ETA 10,000 : {_format_duration(summary['eta_10k_seconds'])}")
    print(f"Report     : {output_dir / CSV_NAME}")
    print(f"Summary    : {output_dir / JSON_NAME}")


def _parse_signals(value: str | None) -> tuple[str, ...] | None:
    """`"ocr,sift"` -> `("ocr", "sift")`.

    A missing flag returns None, which keeps `config.ENABLED_SIGNALS`; an empty
    string returns `()`, which runs no signal at all (useful for timing the
    walk and the decode on their own).
    """
    if value is None:
        return None
    return tuple(name.strip() for name in value.split(",") if name.strip())


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
    scan.add_argument(
        "--signals",
        default=None,
        help=f"comma-separated signals (default: {','.join(config.ENABLED_SIGNALS)})",
    )

    bench = sub.add_parser("benchmark", help="measure signal quality on a labeled set")
    bench.add_argument("--labeled", required=True, help="folder with positive/ and negative/")
    bench.add_argument(
        "--signals",
        default=None,
        help=f"comma-separated signals (default: {','.join(config.ENABLED_SIGNALS)})",
    )
    bench.add_argument("--limit", type=int, default=None, help="stop after N images per class")
    bench.add_argument("--no-progress", action="store_true", help="hide the progress bar")
    bench.add_argument(
        "--no-record", action="store_true", help="do not append a row to docs/BENCHMARKS.md"
    )
    bench.add_argument("--note", default="", help="note stored with the BENCHMARKS row")

    cal = sub.add_parser(
        "calibrate", help="tune the per-signal thresholds on a labeled set"
    )
    cal.add_argument("--labeled", required=True, help="folder with positive/ and negative/")
    cal.add_argument(
        "--signals",
        default=None,
        help=f"comma-separated signals (default: {','.join(config.ENABLED_SIGNALS)})",
    )
    cal.add_argument("--limit", type=int, default=None, help="stop after N images per class")
    cal.add_argument("--no-progress", action="store_true", help="hide the progress bar")
    cal.add_argument(
        "--no-apply",
        action="store_true",
        help="report the thresholds but do not write them into config.py",
    )

    sub.add_parser("version", help="print the version and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "version":
        print(f"logoscanner {__version__}")
        return 0

    signal_names = _parse_signals(getattr(args, "signals", None))
    if signal_names:
        unknown = [name for name in signal_names if name not in signals.available()]
        if unknown:
            print(
                f"error: unknown signal(s): {', '.join(unknown)}; "
                f"available: {', '.join(signals.available())}"
            )
            return 2

    if args.command == "scan":
        input_dir = Path(args.input)
        if not input_dir.is_dir():
            print(f"error: input folder not found: {input_dir}")
            return 2
        output_dir = Path(args.output)
        summary = run_scan(
            input_dir,
            output_dir,
            limit=args.limit,
            progress=not args.no_progress,
            signals=signal_names,
        )
        print_report(summary, output_dir)
        return 0

    if args.command == "benchmark":
        labeled_dir = Path(args.labeled)
        if not labeled_dir.is_dir():
            print(f"error: labeled folder not found: {labeled_dir}")
            return 2
        run_benchmark(
            labeled_dir,
            signal_names,
            limit=args.limit,
            progress=not args.no_progress,
            write_docs=not args.no_record,
            note=args.note,
        )
        return 0

    if args.command == "calibrate":
        labeled_dir = Path(args.labeled)
        if not labeled_dir.is_dir():
            print(f"error: labeled folder not found: {labeled_dir}")
            return 2
        run_calibration(
            labeled_dir,
            signal_names,
            limit=args.limit,
            progress=not args.no_progress,
            apply=not args.no_apply,
        )
        return 0

    return 2  # pragma: no cover - argparse rejects unknown commands first
