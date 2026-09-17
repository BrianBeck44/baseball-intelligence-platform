from dataclasses import dataclass
from typing import Any

import pandas as pd
from app.ingestion.validation import RejectionRecord
from sqlalchemy import MetaData, Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class ChunkLoadResult:
    records_attempted: int
    records_loaded: int
    records_skipped: int
    records_rejected: int


def normalize_database_value(value: Any) -> Any:
    """
    Convert Pandas/NumPy missing and scalar values into
    values suitable for PostgreSQL.
    """
    if pd.isna(value):
        return None

    if hasattr(value, "item"):
        return value.item()

    return value


def load_statcast_chunk(
    connection: Connection,
    ingestion_batch_id: int,
    valid_rows: pd.DataFrame,
    rejection_records: list[RejectionRecord],
) -> ChunkLoadResult:
    """
    Persist one validated Statcast chunk within an existing transaction.

    The caller owns the transaction boundary.
    """
    metadata = MetaData()

    statcast_pitch = Table(
        "statcast_pitch",
        metadata,
        schema="raw",
        autoload_with=connection,
    )

    ingestion_rejection = Table(
        "ingestion_rejection",
        metadata,
        schema="raw",
        autoload_with=connection,
    )

    source_rows = valid_rows.to_dict(orient="records")
    records_attempted = len(source_rows)

    if source_rows:
        rows_to_insert = []

        for row in source_rows:
            database_row = {
                column: normalize_database_value(value)
                for column, value in row.items()
            }

            database_row["ingestion_batch_id"] = ingestion_batch_id
            rows_to_insert.append(database_row)

        stmt = insert(statcast_pitch).values(rows_to_insert)

        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_raw_statcast_pitch_source_key"
        ).returning(
            statcast_pitch.c.raw_statcast_pitch_id
        )

        inserted_ids = connection.execute(stmt).scalars().all()

        records_loaded = len(inserted_ids)

    else:
        records_loaded = 0

    records_skipped = records_attempted - records_loaded

    if rejection_records:
        rejection_rows = []

        for rejection in rejection_records:
            rejection_rows.append(
                {
                    "ingestion_batch_id": ingestion_batch_id,
                    "source_row_number": rejection.source_row_number,
                    "rejection_reason": rejection.rejection_reason,
                    "source_key": rejection.source_key,
                    "details": rejection.details,
                    "raw_row": rejection.raw_row,
                }
            )

        rejection_stmt = insert(ingestion_rejection).values(
            rejection_rows
        )

        connection.execute(rejection_stmt)

    return ChunkLoadResult(
        records_attempted=records_attempted,
        records_loaded=records_loaded,
        records_skipped=records_skipped,
        records_rejected=len(rejection_records),
    )