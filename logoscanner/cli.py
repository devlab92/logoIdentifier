"""Command line interface: `python -m logoscanner <command>`.

`scan` walks a folder and writes the reports - resumably, skipping duplicate
images and saving review artifacts since phase07 - `benchmark` measures each signal
on a labeled set, `calibrate` (phase04) tunes the per-signal thresholds on that
same set and writes them into `config.py`, and `version` prints the version.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from tqdm import tqdm

from logoscanner import __version__
from logoscanner import artifacts, config, dedup, journal, signals
from logoscanner.benchmark import run_benchmark
from logoscanner.calibrate import run_calibration
from logoscanner.io_utils import iter_images, load_image
from logoscanner.journal import JOURNAL_NAME, Journal, JournalEntry
from logoscanner.pipeline import build_pipeline
from logoscanner.scorecache import CACHE_NAME
from logoscanner.results import (
    CSV_NAME,
    ERRORS_NAME,
    JSON_NAME,
    summarize,
    write_csv,
    write_errors,
    write_json,
)


def _process_one(
    path: Path,
    relative: str,
    pipeline,
    index: dedup.DuplicateIndex,
    entries: dict[str, JournalEntry],
    output_dir: Path,
    save_artifacts: bool,
) -> JournalEntry:
    """Turn one file into its journal entry: dedup, load, score, save artifacts.

    The two hashes come first because both are far cheaper than a signal pass:
    identical bytes never reach the decoder, and a re-encode of something
    already scanned never reaches the pipeline.
    """
    try:
        sha = dedup.sha256_file(path)
    except OSError as exc:
        return journal.error_entry(relative, f"read failed: {exc.strerror or exc}")

    image, image_hash = None, None
    twin = index.find_by_sha(sha)
    if twin is None:
        image, error = load_image(path)
        if error:
            return journal.error_entry(relative, error, sha=sha)
        image_hash = dedup.dhash(image)
        twin = index.find_by_hash(image_hash)

    if twin is not None and twin in entries:
        # Same picture, already judged: copy the verdict, run nothing. No crop
        # and no copy either - the point of dedup is to keep the review folder
        # free of the same image five times over.
        return journal.copy_of(entries[twin], relative, sha=sha, image_hash=image_hash)

    entry = JournalEntry.from_decision(
        relative, pipeline.run(image), sha=sha, image_hash=image_hash
    )
    if save_artifacts:
        problem = artifacts.save(image, path, output_dir, relative, entry.band, entry.bbox)
        if problem:
            entry.error = problem
    index.add(relative, sha, image_hash)
    return entry


def _counter_line(counts: dict[str, int]) -> str:
    """The live band tally tqdm shows to the right of the bar."""
    parts = [f"{name[:3]}={counts.get(name, 0)}" for name in config.BANDS]
    parts.append(f"dup={counts.get('duplicate', 0)}")
    parts.append(f"err={counts.get('error', 0)}")
    return " ".join(parts)


def _tally(counts: dict[str, int], entry: JournalEntry) -> None:
    """Fold one entry into the live counters."""
    counts[entry.band] = counts.get(entry.band, 0) + 1
    if entry.duplicate_of:
        counts["duplicate"] = counts.get("duplicate", 0) + 1
    if entry.error:
        counts["error"] = counts.get("error", 0) + 1


def run_scan(
    input_dir: str | Path,
    output_dir: str | Path,
    limit: int | None = None,
    progress: bool = True,
    signals=None,
    restart: bool = False,
    save_artifacts: bool = True,
) -> dict:
    """Scan `input_dir`, write the reports into `output_dir`, return the summary.

    Resumable: every finished image is appended to `output/.progress.jsonl` and
    flushed before the next one starts, and a re-run skips whatever that
    journal already holds. Ctrl-C stops after the image in flight and still
    writes complete reports. The reports are always rebuilt from the journal,
    so they describe the whole collection and not just this run's slice (D-030).
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    journal_path = output_dir / JOURNAL_NAME
    if restart:
        journal.reset(journal_path)

    entries = journal.load(journal_path)
    index = dedup.DuplicateIndex()
    for done in entries.values():
        # Only images that were actually scanned can lend their verdict to a
        # duplicate; failures and copies are not originals.
        if not done.error and not done.duplicate_of:
            index.add(done.path, done.sha256, done.image_hash)

    pipeline = build_pipeline(signals)
    paths = list(iter_images(input_dir))
    if limit is not None:
        paths = paths[:limit]

    counts: dict[str, int] = {}
    for done in entries.values():
        _tally(counts, done)

    processed, interrupted = 0, False
    start = time.perf_counter()
    with Journal(journal_path) as log:
        bar = tqdm(paths, desc="scanning", unit="img", disable=not progress)
        try:
            for path in bar:
                try:
                    relative = str(path.relative_to(input_dir))
                except ValueError:  # pragma: no cover - path is always under input_dir
                    relative = str(path)
                if relative in entries:
                    continue
                try:
                    entry = _process_one(
                        path, relative, pipeline, index, entries, output_dir, save_artifacts
                    )
                except Exception as exc:  # one bad image must never end the run
                    entry = journal.error_entry(relative, f"{type(exc).__name__}: {exc}")
                log.append(entry)
                entries[relative] = entry
                processed += 1
                _tally(counts, entry)
                if progress:
                    bar.set_postfix_str(_counter_line(counts), refresh=False)
        except KeyboardInterrupt:
            interrupted = True
        finally:
            bar.close()
    seconds = time.perf_counter() - start

    rows = journal.rows(entries.values())
    summary = summarize(rows, seconds, processed=processed)
    summary["input"] = str(input_dir)
    summary["output"] = str(output_dir)
    summary["signals"] = list(pipeline.names)
    summary["interrupted"] = interrupted
    write_csv(rows, output_dir / CSV_NAME)
    write_errors(rows, output_dir / ERRORS_NAME)
    write_json(summary, output_dir / JSON_NAME)
    if interrupted:
        print("\ninterrupted - reports written; re-run the same command to resume")
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
    """End-of-run summary block: what was found, what it cost, where it went."""
    bands = summary["bands"]
    print()
    print(f"Scanned    : {summary['images']} images from {summary['input']}")
    print(f"  processed: {summary['processed']} this run, {summary['skipped']} already journaled")
    print("Signals    : " + ", ".join(summary.get("signals") or ["none"]))
    print("Bands      : " + "  ".join(f"{name}={bands.get(name, 0)}" for name in config.BANDS))
    print(f"Duplicates : {summary['duplicates']} (verdict copied, not re-scanned)")
    print(f"Errors     : {summary['errors']}")
    print(f"Elapsed    : {_format_duration(summary['seconds'])}")
    print(f"Throughput : {summary['images_per_second']:.2f} img/s")
    print(f"ETA 10,000 : {_format_duration(summary['eta_10k_seconds'])}")
    print(f"Report     : {output_dir / CSV_NAME}")
    print(f"Summary    : {output_dir / JSON_NAME}")
    if summary["errors"]:
        print(f"Errors CSV : {output_dir / ERRORS_NAME}")
    if bands.get(config.BAND_POSITIVE):
        print(f"Detected   : {output_dir / artifacts.DETECTED_DIR}")
    if bands.get(config.BAND_REVIEW):
        print(f"Review     : {output_dir / artifacts.REVIEW_DIR}   "
              f"(crops: {output_dir / artifacts.CROPS_DIR})")


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
        "--restart",
        action="store_true",
        help="discard the resume journal and scan everything again - do this after "
             "changing thresholds or signals, or old verdicts are reused",
    )
    scan.add_argument(
        "--no-artifacts",
        action="store_true",
        help="skip crops/ detected/ review/; write the reports only",
    )
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
    cal.add_argument(
        "--no-cache",
        action="store_true",
        help="ignore output/scores.json and re-score every image (do this after "
             "changing a signal, which invalidates every stored score)",
    )
    cal.add_argument(
        "--cache",
        default=None,
        help="where per-image scores are remembered (default: output/scores.json). "
             "Only new images are scored, so recalibrating after labeling more is cheap",
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
            restart=args.restart,
            save_artifacts=not args.no_artifacts,
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
        cache_path = None
        if not args.no_cache:
            cache_path = Path(args.cache) if args.cache else Path("output") / CACHE_NAME
        run_calibration(
            labeled_dir,
            signal_names,
            limit=args.limit,
            progress=not args.no_progress,
            apply=not args.no_apply,
            cache_path=cache_path,
        )
        return 0

    return 2  # pragma: no cover - argparse rejects unknown commands first
