"""Persistence operations for raw.ingestion_batch.

The caller owns the transaction boundary.
"""

from datetime import datetime

from sqlalchemy import MetaData, Table, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection


STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"


def _ingestion_batch_table(connection: Connection) -> Table:
    metadata = MetaData()
    return Table(
        "ingestion_batch",
        metadata,
        schema="raw",
        autoload_with=connection,
    )


def _require_one_row_updated(rowcount: int, ingestion_batch_id: int) -> None:
    if rowcount != 1:
        raise LookupError(
            f"No raw.ingestion_batch row found for "
            f"ingestion_batch_id={ingestion_batch_id}"
        )


def create_ingestion_batch(
    connection: Connection,
    source_name: str,
    started_at: datetime,
) -> int:
    """Insert a RUNNING ingestion batch with counters initialized to 0."""
    ingestion_batch = _ingestion_batch_table(connection)
    stmt = (
        insert(ingestion_batch)
        .values(
            source_name=source_name,
            started_at=started_at,
            status=STATUS_RUNNING,
            records_received=0,
            records_filtered=0,
            records_rejected=0,
            records_skipped=0,
            records_loaded=0,
        )
        .returning(ingestion_batch.c.ingestion_batch_id)
    )
    return connection.execute(stmt).scalar_one()


def update_ingestion_batch_counts(
    connection: Connection,
    ingestion_batch_id: int,
    *,
    records_received: int,
    records_filtered: int,
    records_rejected: int,
    records_skipped: int,
    records_loaded: int,
) -> None:
    """Update all five counters without changing status or completed_at."""
    ingestion_batch = _ingestion_batch_table(connection)
    stmt = (
        update(ingestion_batch)
        .where(ingestion_batch.c.ingestion_batch_id == ingestion_batch_id)
        .values(
            records_received=records_received,
            records_filtered=records_filtered,
            records_rejected=records_rejected,
            records_skipped=records_skipped,
            records_loaded=records_loaded,
        )
    )
    result = connection.execute(stmt)
    _require_one_row_updated(result.rowcount, ingestion_batch_id)


def complete_ingestion_batch(
    connection: Connection,
    ingestion_batch_id: int,
    *,
    completed_at: datetime,
    records_received: int,
    records_filtered: int,
    records_rejected: int,
    records_skipped: int,
    records_loaded: int,
) -> None:
    """Mark a batch COMPLETED and persist final counters."""
    ingestion_batch = _ingestion_batch_table(connection)
    stmt = (
        update(ingestion_batch)
        .where(ingestion_batch.c.ingestion_batch_id == ingestion_batch_id)
        .values(
            status=STATUS_COMPLETED,
            completed_at=completed_at,
            records_received=records_received,
            records_filtered=records_filtered,
            records_rejected=records_rejected,
            records_skipped=records_skipped,
            records_loaded=records_loaded,
        )
    )
    result = connection.execute(stmt)
    _require_one_row_updated(result.rowcount, ingestion_batch_id)


def fail_ingestion_batch(
    connection: Connection,
    ingestion_batch_id: int,
    *,
    completed_at: datetime,
    records_received: int,
    records_filtered: int,
    records_rejected: int,
    records_skipped: int,
    records_loaded: int,
) -> None:
    """Mark a batch FAILED and persist current counters."""
    ingestion_batch = _ingestion_batch_table(connection)
    stmt = (
        update(ingestion_batch)
        .where(ingestion_batch.c.ingestion_batch_id == ingestion_batch_id)
        .values(
            status=STATUS_FAILED,
            completed_at=completed_at,
            records_received=records_received,
            records_filtered=records_filtered,
            records_rejected=records_rejected,
            records_skipped=records_skipped,
            records_loaded=records_loaded,
        )
    )
    result = connection.execute(stmt)
    _require_one_row_updated(result.rowcount, ingestion_batch_id)
