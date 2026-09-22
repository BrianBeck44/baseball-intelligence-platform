"""Statcast ingestion orchestration and its public result type."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.ingestion.batch import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
    complete_ingestion_batch,
    create_ingestion_batch,
    fail_ingestion_batch,
    update_ingestion_batch_counts,
)
from app.ingestion.loader import load_statcast_chunk
from app.ingestion.validation import validate_statcast_chunk


@dataclass(frozen=True)
class IngestionResult:
    ingestion_batch_id: int
    status: str
    records_received: int
    records_filtered: int
    records_rejected: int
    records_skipped: int
    records_loaded: int
    error_message: str | None


def _create_engine() -> Engine:
    return create_engine(settings.database_url)


def _ingestion_result(
    ingestion_batch_id: int,
    status: str,
    counters: dict[str, int],
    error_message: str | None,
) -> IngestionResult:
    return IngestionResult(
        ingestion_batch_id=ingestion_batch_id,
        status=status,
        records_received=counters["records_received"],
        records_filtered=counters["records_filtered"],
        records_rejected=counters["records_rejected"],
        records_skipped=counters["records_skipped"],
        records_loaded=counters["records_loaded"],
        error_message=error_message,
    )


def ingest_statcast_file(
    file_path: Path,
    source_name: str,
    chunk_size: int = 10_000,
) -> IngestionResult:
    """Ingest one local Statcast CSV file into the raw PostgreSQL layer."""
    engine = _create_engine()
    try:
        with engine.begin() as connection:
            ingestion_batch_id = create_ingestion_batch(
                connection,
                source_name,
                datetime.now(timezone.utc),
            )

        counters = {
            "records_received": 0,
            "records_filtered": 0,
            "records_rejected": 0,
            "records_skipped": 0,
            "records_loaded": 0,
        }

        try:
            starting_source_row_number = 1
            for chunk in pd.read_csv(file_path, chunksize=chunk_size):
                validation = validate_statcast_chunk(
                    chunk,
                    starting_source_row_number,
                )
                with engine.begin() as connection:
                    load_result = load_statcast_chunk(
                        connection,
                        ingestion_batch_id,
                        validation.valid_rows,
                        validation.rejections,
                    )
                    pending = {
                        "records_received": (
                            counters["records_received"] + validation.records_received
                        ),
                        "records_filtered": (
                            counters["records_filtered"] + validation.records_filtered
                        ),
                        "records_rejected": (
                            counters["records_rejected"] + validation.records_rejected
                        ),
                        "records_skipped": (
                            counters["records_skipped"] + load_result.records_skipped
                        ),
                        "records_loaded": (
                            counters["records_loaded"] + load_result.records_loaded
                        ),
                    }
                    update_ingestion_batch_counts(
                        connection,
                        ingestion_batch_id,
                        records_received=pending["records_received"],
                        records_filtered=pending["records_filtered"],
                        records_rejected=pending["records_rejected"],
                        records_skipped=pending["records_skipped"],
                        records_loaded=pending["records_loaded"],
                    )
                counters = pending
                starting_source_row_number += validation.records_received

            if (
                counters["records_received"]
                != counters["records_filtered"]
                + counters["records_rejected"]
                + counters["records_skipped"]
                + counters["records_loaded"]
            ):
                raise ValueError(
                    "Completed ingestion counter invariant was violated."
                )

            with engine.begin() as connection:
                complete_ingestion_batch(
                    connection,
                    ingestion_batch_id,
                    completed_at=datetime.now(timezone.utc),
                    records_received=counters["records_received"],
                    records_filtered=counters["records_filtered"],
                    records_rejected=counters["records_rejected"],
                    records_skipped=counters["records_skipped"],
                    records_loaded=counters["records_loaded"],
                )

            return _ingestion_result(
                ingestion_batch_id,
                STATUS_COMPLETED,
                counters,
                None,
            )
        except Exception as exc:
            try:
                with engine.begin() as connection:
                    fail_ingestion_batch(
                        connection,
                        ingestion_batch_id,
                        completed_at=datetime.now(timezone.utc),
                        records_received=counters["records_received"],
                        records_filtered=counters["records_filtered"],
                        records_rejected=counters["records_rejected"],
                        records_skipped=counters["records_skipped"],
                        records_loaded=counters["records_loaded"],
                    )
            except Exception:
                pass
            return _ingestion_result(
                ingestion_batch_id,
                STATUS_FAILED,
                counters,
                str(exc),
            )
    finally:
        engine.dispose()
