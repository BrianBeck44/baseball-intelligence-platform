"""Integration tests for Statcast chunk persistence."""

from datetime import date, datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.ingestion.loader import load_statcast_chunk
from app.ingestion.validation import INVALID_SOURCE_KEY, RejectionRecord


def _engine() -> Engine:
    return create_engine(settings.database_url)


def _create_ingestion_batch(connection: Connection, source_name: str) -> int:
    ingestion_batch_id = connection.execute(
        text(
            """
            INSERT INTO raw.ingestion_batch (source_name, started_at, status)
            VALUES (:source_name, :started_at, :status)
            RETURNING ingestion_batch_id
            """
        ),
        {
            "source_name": source_name,
            "started_at": datetime.now(timezone.utc),
            "status": "RUNNING",
        },
    ).scalar_one()
    return ingestion_batch_id


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


def _valid_statcast_row(**overrides) -> dict:
    row = {
        "game_pk": 888000001,
        "at_bat_number": 1,
        "pitch_number": 1,
        "game_type": "R",
        "pitch_type": "FF",
        "game_date": date(2022, 4, 8),
        "release_speed": 95.1,
        "player_name": "Pytest, Pitcher",
        "batter": 608070,
        "pitcher": 434378,
        "events": None,
        "description": "called_strike",
        "stand": "L",
        "p_throws": "R",
        "home_team": "NYY",
        "away_team": "BOS",
        "zone": 5,
    }
    row.update(overrides)
    return row


def _fetch_pitch(
    connection: Connection,
    game_pk: int,
    at_bat_number: int,
    pitch_number: int,
):
    return connection.execute(
        text(
            """
            SELECT
                raw_statcast_pitch_id,
                ingestion_batch_id,
                game_pk,
                at_bat_number,
                pitch_number,
                game_type
            FROM raw.statcast_pitch
            WHERE game_pk = :game_pk
              AND at_bat_number = :at_bat_number
              AND pitch_number = :pitch_number
            """
        ),
        {
            "game_pk": game_pk,
            "at_bat_number": at_bat_number,
            "pitch_number": pitch_number,
        },
    ).mappings().all()


def _count_rejections(connection: Connection, batch_id: int) -> int:
    return connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM raw.ingestion_rejection
            WHERE ingestion_batch_id = :batch_id
            """
        ),
        {"batch_id": batch_id},
    ).scalar_one()


def test_valid_row_is_loaded():
    engine = _engine()
    batch_ids: list[int] = []
    game_pk = 888000101

    try:
        with engine.begin() as connection:
            batch_id = _create_ingestion_batch(
                connection, "pytest_loader_valid_row"
            )
            batch_ids.append(batch_id)

            valid_rows = pd.DataFrame([_valid_statcast_row(game_pk=game_pk)])
            result = load_statcast_chunk(
                connection=connection,
                ingestion_batch_id=batch_id,
                valid_rows=valid_rows,
                rejection_records=[],
            )

            assert result.records_attempted == 1
            assert result.records_loaded == 1
            assert result.records_skipped == 0
            assert result.records_rejected == 0

            pitches = _fetch_pitch(connection, game_pk, 1, 1)
            assert len(pitches) == 1
            pitch = pitches[0]
            assert pitch["ingestion_batch_id"] == batch_id
            assert pitch["raw_statcast_pitch_id"] is not None
            assert pitch["game_type"] == "R"
    finally:
        _cleanup_ingestion_batches(engine, batch_ids)
        engine.dispose()


def test_existing_row_is_skipped():
    engine = _engine()
    batch_ids: list[int] = []
    game_pk = 888000102

    try:
        with engine.begin() as connection:
            batch_id = _create_ingestion_batch(
                connection, "pytest_loader_existing_row_skipped"
            )
            batch_ids.append(batch_id)
            valid_rows = pd.DataFrame([_valid_statcast_row(game_pk=game_pk)])

            first = load_statcast_chunk(
                connection=connection,
                ingestion_batch_id=batch_id,
                valid_rows=valid_rows,
                rejection_records=[],
            )
            assert first.records_loaded == 1

            original = _fetch_pitch(connection, game_pk, 1, 1)[0]
            original_id = original["raw_statcast_pitch_id"]
            original_batch_id = original["ingestion_batch_id"]

            second = load_statcast_chunk(
                connection=connection,
                ingestion_batch_id=batch_id,
                valid_rows=valid_rows,
                rejection_records=[],
            )

            assert second.records_attempted == 1
            assert second.records_loaded == 0
            assert second.records_skipped == 1
            assert second.records_rejected == 0

            pitches = _fetch_pitch(connection, game_pk, 1, 1)
            assert len(pitches) == 1
            assert pitches[0]["raw_statcast_pitch_id"] == original_id
            assert pitches[0]["ingestion_batch_id"] == original_batch_id
            assert pitches[0]["ingestion_batch_id"] == batch_id
    finally:
        _cleanup_ingestion_batches(engine, batch_ids)
        engine.dispose()


def test_rejection_is_persisted():
    engine = _engine()
    batch_ids: list[int] = []

    try:
        with engine.begin() as connection:
            batch_id = _create_ingestion_batch(
                connection, "pytest_loader_rejection_persisted"
            )
            batch_ids.append(batch_id)

            rejection = RejectionRecord(
                source_row_number=17,
                rejection_reason=INVALID_SOURCE_KEY,
                source_key={
                    "game_pk": 888000103,
                    "at_bat_number": 1,
                    "pitch_number": 0,
                },
                details={
                    "errors": [
                        {
                            "field": "pitch_number",
                            "issue": "not_positive",
                            "value": 0,
                        }
                    ]
                },
                raw_row={
                    "game_pk": 888000103,
                    "at_bat_number": 1,
                    "pitch_number": 0,
                    "game_type": "R",
                },
            )

            result = load_statcast_chunk(
                connection=connection,
                ingestion_batch_id=batch_id,
                valid_rows=pd.DataFrame(),
                rejection_records=[rejection],
            )

            assert result.records_attempted == 0
            assert result.records_loaded == 0
            assert result.records_skipped == 0
            assert result.records_rejected == 1

            rows = connection.execute(
                text(
                    """
                    SELECT
                        ingestion_batch_id,
                        source_row_number,
                        rejection_reason,
                        source_key,
                        details,
                        raw_row
                    FROM raw.ingestion_rejection
                    WHERE ingestion_batch_id = :batch_id
                    """
                ),
                {"batch_id": batch_id},
            ).mappings().all()

            assert len(rows) == 1
            persisted = rows[0]
            assert persisted["ingestion_batch_id"] == batch_id
            assert persisted["source_row_number"] == 17
            assert persisted["rejection_reason"] == INVALID_SOURCE_KEY
            assert persisted["details"] == rejection.details
            assert persisted["raw_row"] == rejection.raw_row
    finally:
        _cleanup_ingestion_batches(engine, batch_ids)
        engine.dispose()


def test_valid_rows_and_rejections_can_be_loaded_together():
    engine = _engine()
    batch_ids: list[int] = []
    game_pk = 888000104

    try:
        with engine.begin() as connection:
            batch_id = _create_ingestion_batch(
                connection, "pytest_loader_valid_and_rejection"
            )
            batch_ids.append(batch_id)

            valid_rows = pd.DataFrame([_valid_statcast_row(game_pk=game_pk)])
            rejection = RejectionRecord(
                source_row_number=2,
                rejection_reason=INVALID_SOURCE_KEY,
                source_key={
                    "game_pk": game_pk,
                    "at_bat_number": 1,
                    "pitch_number": -1,
                },
                details={"errors": [{"field": "pitch_number", "issue": "not_positive"}]},
                raw_row={"game_pk": game_pk, "pitch_number": -1, "game_type": "R"},
            )

            result = load_statcast_chunk(
                connection=connection,
                ingestion_batch_id=batch_id,
                valid_rows=valid_rows,
                rejection_records=[rejection],
            )

            assert result.records_attempted == 1
            assert result.records_loaded == 1
            assert result.records_skipped == 0
            assert result.records_rejected == 1

            assert len(_fetch_pitch(connection, game_pk, 1, 1)) == 1
            assert _count_rejections(connection, batch_id) == 1
    finally:
        _cleanup_ingestion_batches(engine, batch_ids)
        engine.dispose()


def test_multiple_existing_rows_are_all_skipped():
    engine = _engine()
    batch_ids: list[int] = []
    rows = [
        _valid_statcast_row(game_pk=888000105, pitch_number=1),
        _valid_statcast_row(game_pk=888000105, pitch_number=2),
        _valid_statcast_row(game_pk=888000105, pitch_number=3),
    ]

    try:
        with engine.begin() as connection:
            batch_id = _create_ingestion_batch(
                connection, "pytest_loader_multiple_existing_skipped"
            )
            batch_ids.append(batch_id)
            valid_rows = pd.DataFrame(rows)

            first = load_statcast_chunk(
                connection=connection,
                ingestion_batch_id=batch_id,
                valid_rows=valid_rows,
                rejection_records=[],
            )
            assert first.records_loaded == 3

            count_after_first = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM raw.statcast_pitch
                    WHERE game_pk = :game_pk
                    """
                ),
                {"game_pk": 888000105},
            ).scalar_one()
            assert count_after_first == 3

            second = load_statcast_chunk(
                connection=connection,
                ingestion_batch_id=batch_id,
                valid_rows=valid_rows,
                rejection_records=[],
            )

            assert second.records_attempted == 3
            assert second.records_loaded == 0
            assert second.records_skipped == 3
            assert second.records_rejected == 0

            count_after_second = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM raw.statcast_pitch
                    WHERE game_pk = :game_pk
                    """
                ),
                {"game_pk": 888000105},
            ).scalar_one()
            assert count_after_second == 3
    finally:
        _cleanup_ingestion_batches(engine, batch_ids)
        engine.dispose()


def test_loader_preserves_ingestion_lineage():
    engine = _engine()
    batch_ids: list[int] = []
    game_pk = 888000106

    try:
        with engine.begin() as connection:
            original_batch_id = _create_ingestion_batch(
                connection, "pytest_loader_lineage_original"
            )
            later_batch_id = _create_ingestion_batch(
                connection, "pytest_loader_lineage_later"
            )
            batch_ids.extend([original_batch_id, later_batch_id])
            valid_rows = pd.DataFrame([_valid_statcast_row(game_pk=game_pk)])

            first = load_statcast_chunk(
                connection=connection,
                ingestion_batch_id=original_batch_id,
                valid_rows=valid_rows,
                rejection_records=[],
            )
            assert first.records_loaded == 1

            pitch = _fetch_pitch(connection, game_pk, 1, 1)[0]
            assert pitch["ingestion_batch_id"] == original_batch_id

            second = load_statcast_chunk(
                connection=connection,
                ingestion_batch_id=later_batch_id,
                valid_rows=valid_rows,
                rejection_records=[],
            )
            assert second.records_loaded == 0
            assert second.records_skipped == 1

            pitch_after_duplicate = _fetch_pitch(connection, game_pk, 1, 1)[0]
            assert pitch_after_duplicate["raw_statcast_pitch_id"] == pitch[
                "raw_statcast_pitch_id"
            ]
            assert pitch_after_duplicate["ingestion_batch_id"] == original_batch_id
    finally:
        _cleanup_ingestion_batches(engine, batch_ids)
        engine.dispose()
