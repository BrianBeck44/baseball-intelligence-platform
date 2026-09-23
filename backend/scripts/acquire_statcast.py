"""CLI adapter for downloading a Statcast CSV from Baseball Savant."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from app.ingestion.acquisition import download_statcast_csv


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid date {value!r}; expected YYYY-MM-DD"
        ) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download a Statcast CSV for an inclusive date range."
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


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.start_date > args.end_date:
        parser.error("start_date must not be after end_date")

    output_path = _output_path(args.start_date, args.end_date)

    try:
        downloaded_path = download_statcast_csv(
            start_date=args.start_date,
            end_date=args.end_date,
            output_path=output_path,
        )
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(downloaded_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
