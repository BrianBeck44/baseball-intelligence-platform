"""CLI adapter for ingesting a local Statcast CSV file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.ingestion.statcast import IngestionResult, ingest_statcast_file


def _default_source_name(file_path: Path) -> str:
    return file_path.name


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest a local Statcast CSV file into the raw database."
    )
    parser.add_argument(
        "file_path",
        help="Path to the Statcast CSV file",
    )
    parser.add_argument(
        "--source-name",
        dest="source_name",
        default=None,
        help="Ingestion source name. Defaults to the CSV filename.",
    )
    return parser


def _print_result(result: IngestionResult) -> None:
    print(f"ingestion_batch_id: {result.ingestion_batch_id}")
    print(f"status: {result.status}")
    print(f"records_received: {result.records_received}")
    print(f"records_filtered: {result.records_filtered}")
    print(f"records_rejected: {result.records_rejected}")
    print(f"records_skipped: {result.records_skipped}")
    print(f"records_loaded: {result.records_loaded}")
    if result.error_message:
        print(f"error_message: {result.error_message}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    file_path = Path(args.file_path)
    source_name = args.source_name or _default_source_name(file_path)

    result = ingest_statcast_file(
        file_path=file_path,
        source_name=source_name,
    )
    _print_result(result)

    if result.status == "COMPLETED":
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
