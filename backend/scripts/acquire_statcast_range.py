"""CLI adapter for downloading Statcast CSV files in 5-day chunks."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

from app.ingestion.acquisition import download_statcast_csv

_CHUNK_DAYS = 5
_SAVANT_ROW_LIMIT = 25_000


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid date {value!r}; expected YYYY-MM-DD"
        ) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download Statcast CSV files for an inclusive date range "
            "in 5-day chunks."
        )
    )
    parser.add_argument(
        "start_date",
        type=_iso_date,
        help="Inclusive start date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "end_date",
        type=_iso_date,
        help="Inclusive end date in YYYY-MM-DD format",
    )
    return parser


def _output_path(start_date: date, end_date: date) -> Path:
    filename = (
        f"statcast_{start_date.isoformat()}_{end_date.isoformat()}.csv"
    )
    return Path("..") / "data" / "raw" / "statcast" / "acquired" / filename


def _date_chunks(start_date: date, end_date: date) -> list[tuple[date, date]]:
    chunks: list[tuple[date, date]] = []
    current = start_date
    while current <= end_date:
        chunk_end = current + timedelta(days=_CHUNK_DAYS - 1)
        if chunk_end > end_date:
            chunk_end = end_date
        chunks.append((current, chunk_end))
        current = chunk_end + timedelta(days=1)
    return chunks


def _csv_data_row_count(path: Path) -> int:
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        if next(reader, None) is None:
            return 0
        return sum(1 for _ in reader)


def _reject_truncated_csv(path: Path) -> None:
    row_count = _csv_data_row_count(path)
    if row_count == _SAVANT_ROW_LIMIT:
        raise OSError(
            "Baseball Savant response may have been truncated at the "
            "endpoint's observed 25,000-row limit: "
            f"{path} contains exactly {row_count} data rows."
        )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.start_date > args.end_date:
        parser.error("start_date must not be after end_date")

    chunks = _date_chunks(args.start_date, args.end_date)
    print("Acquiring Statcast data")
    print(
        "Range: "
        f"{args.start_date.isoformat()} to {args.end_date.isoformat()}"
    )
    print(f"Chunks: {len(chunks)}")
    print()

    for index, (chunk_start, chunk_end) in enumerate(chunks, start=1):
        output_path = _output_path(chunk_start, chunk_end)
        print(
            f"[{index}/{len(chunks)}] "
            f"{chunk_start.isoformat()} to {chunk_end.isoformat()}"
        )
        try:
            downloaded_path = download_statcast_csv(
                chunk_start,
                chunk_end,
                output_path,
            )
            _reject_truncated_csv(downloaded_path)
        except Exception as exc:
            print(
                "error: failed to acquire "
                f"{chunk_start.isoformat()} to {chunk_end.isoformat()}",
                file=sys.stderr,
            )
            print(exc, file=sys.stderr)
            return 1
        print(f"Saved: {downloaded_path}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
