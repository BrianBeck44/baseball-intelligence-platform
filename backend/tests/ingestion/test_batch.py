"""Integration tests for raw.ingestion_batch persistence."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

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


def _engine() -> Engine:
    return create_engine(settings.database_url)


def _cleanup_ingestion_batches(engine: Engine, batch_ids: list[int]) -> None:
    if not batch_ids:
        return

    with engine.begin() as connection:
        for batch_id in batch_ids:
            connection.execute(
                text(
                    """
                    DELETE FROM raw.statcast_pitch
                    WHERE ingestion_batch_id = :batch_id
                    """
                ),
                {"batch_id": batch_id},
            )
            connection.execute(
                text(
                    """
                    DELETE FROM raw.ingestion_rejection
                    WHERE ingestion_batch_id = :batch_id
                    """
                ),
                {"batch_id": batch_id},
            )
        for batch_id in batch_ids:
            connection.execute(
                text(
                    """
                    DELETE FROM raw.ingestion_batch
                    WHERE ingestion_batch_id = :batch_id
                    """
                ),
                {"batch_id": batch_id},
            )


def _fetch_batch(connection: Connection, ingestion_batch_id: int):
    return connection.execute(
        text(
            """
            SELECT
                ingestion_batch_id,
                source_name,
                status,
                completed_at,
                records_received,
                records_filtered,
                records_rejected,
                records_skipped,
                records_loaded
            FROM raw.ingestion_batch
            WHERE ingestion_batch_id = :ingestion_batch_id
            """
        ),
        {"ingestion_batch_id": ingestion_batch_id},
    ).mappings().one()


def test_create_ingestion_batch():
    engine = _engine()
    batch_ids: list[int] = []
    started_at = datetime.now(timezone.utc)

    try:
        with engine.begin() as connection:
            batch_id = create_ingestion_batch(
                connection,
                source_name="pytest_batch_create",
                started_at=started_at,
            )
            batch_ids.append(batch_id)

            row = _fetch_batch(connection, batch_id)
            assert row["ingestion_batch_id"] == batch_id
            assert row["source_name"] == "pytest_batch_create"
            assert row["status"] == STATUS_RUNNING
            assert row["completed_at"] is None
            assert row["records_received"] == 0
            assert row["records_filtered"] == 0
            assert row["records_rejected"] == 0
            assert row["records_skipped"] == 0
            assert row["records_loaded"] == 0
    finally:
        _cleanup_ingestion_batches(engine, batch_ids)
        engine.dispose()


def test_update_ingestion_batch_counts():
    engine = _engine()
    batch_ids: list[int] = []
    started_at = datetime.now(timezone.utc)

    try:
        with engine.begin() as connection:
            batch_id = create_ingestion_batch(
                connection,
                source_name="pytest_batch_update_counts",
                started_at=started_at,
            )
            batch_ids.append(batch_id)

            update_ingestion_batch_counts(
                connection,
                batch_id,
                records_received=100,
                records_filtered=10,
                records_rejected=5,
                records_skipped=15,
                records_loaded=70,
            )

            row = _fetch_batch(connection, batch_id)
            assert row["status"] == STATUS_RUNNING
            assert row["completed_at"] is None
            assert row["records_received"] == 100
            assert row["records_filtered"] == 10
            assert row["records_rejected"] == 5
            assert row["records_skipped"] == 15
            assert row["records_loaded"] == 70
            assert (
                row["records_received"]
                == row["records_filtered"]
                + row["records_rejected"]
                + row["records_skipped"]
                + row["records_loaded"]
            )
    finally:
        _cleanup_ingestion_batches(engine, batch_ids)
        engine.dispose()


def test_complete_ingestion_batch():
    engine = _engine()
    batch_ids: list[int] = []
    started_at = datetime.now(timezone.utc)
    completed_at = datetime.now(timezone.utc)

    try:
        with engine.begin() as connection:
            batch_id = create_ingestion_batch(
                connection,
                source_name="pytest_batch_complete",
                started_at=started_at,
            )
            batch_ids.append(batch_id)

            complete_ingestion_batch(
                connection,
                batch_id,
                completed_at=completed_at,
                records_received=100,
                records_filtered=10,
                records_rejected=5,
                records_skipped=15,
                records_loaded=70,
            )

            row = _fetch_batch(connection, batch_id)
            assert row["status"] == STATUS_COMPLETED
            assert row["completed_at"] is not None
            assert row["records_received"] == 100
            assert row["records_filtered"] == 10
            assert row["records_rejected"] == 5
            assert row["records_skipped"] == 15
            assert row["records_loaded"] == 70
    finally:
        _cleanup_ingestion_batches(engine, batch_ids)
        engine.dispose()


def test_fail_ingestion_batch():
    engine = _engine()
    batch_ids: list[int] = []
    started_at = datetime.now(timezone.utc)
    completed_at = datetime.now(timezone.utc)

    try:
        with engine.begin() as connection:
            batch_id = create_ingestion_batch(
                connection,
                source_name="pytest_batch_fail",
                started_at=started_at,
            )
            batch_ids.append(batch_id)

            fail_ingestion_batch(
                connection,
                batch_id,
                completed_at=completed_at,
                records_received=40,
                records_filtered=4,
                records_rejected=6,
                records_skipped=10,
                records_loaded=20,
            )

            row = _fetch_batch(connection, batch_id)
            assert row["status"] == STATUS_FAILED
            assert row["completed_at"] is not None
            assert row["records_received"] == 40
            assert row["records_filtered"] == 4
            assert row["records_rejected"] == 6
            assert row["records_skipped"] == 10
            assert row["records_loaded"] == 20
    finally:
        _cleanup_ingestion_batches(engine, batch_ids)
        engine.dispose()


def test_invalid_status_is_rejected_by_postgresql():
    engine = _engine()
    batch_ids: list[int] = []
    started_at = datetime.now(timezone.utc)

    try:
        with engine.begin() as connection:
            batch_id = create_ingestion_batch(
                connection,
                source_name="pytest_batch_invalid_status",
                started_at=started_at,
            )
            batch_ids.append(batch_id)

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        UPDATE raw.ingestion_batch
                        SET status = 'PENDING'
                        WHERE ingestion_batch_id = :ingestion_batch_id
                        """
                    ),
                    {"ingestion_batch_id": batch_ids[0]},
                )
    finally:
        _cleanup_ingestion_batches(engine, batch_ids)
        engine.dispose()


def test_null_filtered_and_skipped_are_rejected_by_postgresql():
    engine = _engine()
    batch_ids: list[int] = []
    started_at = datetime.now(timezone.utc)

    try:
        with engine.begin() as connection:
            batch_id = create_ingestion_batch(
                connection,
                source_name="pytest_batch_null_counter",
                started_at=started_at,
            )
            batch_ids.append(batch_id)

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        UPDATE raw.ingestion_batch
                        SET records_filtered = NULL
                        WHERE ingestion_batch_id = :ingestion_batch_id
                        """
                    ),
                    {"ingestion_batch_id": batch_ids[0]},
                )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        UPDATE raw.ingestion_batch
                        SET records_skipped = NULL
                        WHERE ingestion_batch_id = :ingestion_batch_id
                        """
                    ),
                    {"ingestion_batch_id": batch_ids[0]},
                )
    finally:
        _cleanup_ingestion_batches(engine, batch_ids)
        engine.dispose()


def test_negative_counter_is_rejected_by_postgresql():
    engine = _engine()
    batch_ids: list[int] = []
    started_at = datetime.now(timezone.utc)

    try:
        with engine.begin() as connection:
            batch_id = create_ingestion_batch(
                connection,
                source_name="pytest_batch_negative_counter",
                started_at=started_at,
            )
            batch_ids.append(batch_id)

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        UPDATE raw.ingestion_batch
                        SET records_filtered = -1
                        WHERE ingestion_batch_id = :ingestion_batch_id
                        """
                    ),
                    {"ingestion_batch_id": batch_ids[0]},
                )
    finally:
        _cleanup_ingestion_batches(engine, batch_ids)
        engine.dispose()


def test_nonexistent_batch_update_raises():
    engine = _engine()

    try:
        with engine.begin() as connection:
            with pytest.raises(LookupError, match="No raw.ingestion_batch row found"):
                update_ingestion_batch_counts(
                    connection,
                    999_999_999,
                    records_received=1,
                    records_filtered=0,
                    records_rejected=0,
                    records_skipped=0,
                    records_loaded=1,
                )
    finally:
        engine.dispose()
