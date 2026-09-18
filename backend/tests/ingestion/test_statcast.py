"""Integration tests for Statcast file-ingestion orchestration.

``ingest_statcast_file()`` is not implemented yet. These tests define
the required V1 behavior against real PostgreSQL.
"""

import csv
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.ingestion import batch as batch_module
from app.ingestion import statcast
from app.ingestion.batch import STATUS_COMPLETED, STATUS_FAILED, create_ingestion_batch
from app.ingestion.loader import load_statcast_chunk
from app.ingestion.statcast import IngestionResult
from app.ingestion.validation import MISSING_REQUIRED_FIELD, validate_statcast_chunk


CSV_FIELDS = [
    "game_pk",
    "at_bat_number",
    "pitch_number",
    "game_type",
    "pitch_type",
    "game_date",
    "release_speed",
    "player_name",
    "batter",
    "pitcher",
    "events",
    "description",
    "stand",
    "p_throws",
    "home_team",
    "away_team",
    "zone",
]


def _engine() -> Engine:
    return create_engine(settings.database_url)


def _valid_row(**overrides) -> dict:
    row = {
        "game_pk": 888002000,
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


def _csv_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_cell(row.get(field)) for field in CSV_FIELDS})


def _ingest(file_path: Path, source_name: str, chunk_size: int = 10_000) -> IngestionResult:
    return statcast.ingest_statcast_file(
        file_path=file_path,
        source_name=source_name,
        chunk_size=chunk_size,
    )


def _cleanup_statcast_test(
    engine: Engine,
    *,
    source_names: list[str],
    game_pks: list[int],
) -> None:
    with engine.begin() as connection:
        batch_ids = []
        for source_name in source_names:
            ids = connection.execute(
                text(
                    """
                    SELECT ingestion_batch_id
                    FROM raw.ingestion_batch
                    WHERE source_name = :source_name
                    """
                ),
                {"source_name": source_name},
            ).scalars().all()
            batch_ids.extend(ids)

        for game_pk in game_pks:
            connection.execute(
                text("DELETE FROM raw.statcast_pitch WHERE game_pk = :game_pk"),
                {"game_pk": game_pk},
            )

        for batch_id in batch_ids:
            connection.execute(
                text(
                    """
                    DELETE FROM raw.ingestion_rejection
                    WHERE ingestion_batch_id = :batch_id
                    """
                ),
                {"batch_id": batch_id},
            )
            connection.execute(
                text(
                    """
                    DELETE FROM raw.statcast_pitch
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


def _count_pitches(connection: Connection, game_pk: int) -> int:
    return connection.execute(
        text("SELECT COUNT(*) FROM raw.statcast_pitch WHERE game_pk = :game_pk"),
        {"game_pk": game_pk},
    ).scalar_one()


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
                pitch_number
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


def _fetch_rejections(connection: Connection, ingestion_batch_id: int):
    return connection.execute(
        text(
            """
            SELECT
                source_row_number,
                rejection_reason,
                source_key,
                raw_row
            FROM raw.ingestion_rejection
            WHERE ingestion_batch_id = :ingestion_batch_id
            ORDER BY source_row_number
            """
        ),
        {"ingestion_batch_id": ingestion_batch_id},
    ).mappings().all()


def _assert_result_matches_batch(result: IngestionResult, batch) -> None:
    assert result.ingestion_batch_id == batch["ingestion_batch_id"]
    assert result.status == batch["status"]
    assert result.records_received == batch["records_received"]
    assert result.records_filtered == batch["records_filtered"]
    assert result.records_rejected == batch["records_rejected"]
    assert result.records_skipped == batch["records_skipped"]
    assert result.records_loaded == batch["records_loaded"]


def _patch_imported_name(monkeypatch, module, name, value) -> None:
    monkeypatch.setattr(module, name, value, raising=False)


def test_successful_multi_chunk_ingestion(tmp_path, monkeypatch):
    engine = _engine()
    source_name = "pytest_statcast_multi_chunk"
    game_pks = [888002101, 888002102, 888002103, 888002104, 888002105]
    csv_path = tmp_path / "multi_chunk.csv"
    _write_csv(
        csv_path,
        [_valid_row(game_pk=game_pk, pitch_number=1) for game_pk in game_pks],
    )

    chunk_lengths = []
    real_validate = validate_statcast_chunk

    def spy_validate(chunk, starting_source_row_number):
        chunk_lengths.append(len(chunk))
        return real_validate(chunk, starting_source_row_number)

    monkeypatch.setattr(
        "app.ingestion.validation.validate_statcast_chunk",
        spy_validate,
    )
    _patch_imported_name(monkeypatch, statcast, "validate_statcast_chunk", spy_validate)

    try:
        result = _ingest(csv_path, source_name, chunk_size=2)

        assert isinstance(result, IngestionResult)
        assert result.status == STATUS_COMPLETED
        assert result.error_message is None
        assert result.records_received == 5
        assert result.records_filtered == 0
        assert result.records_rejected == 0
        assert result.records_skipped == 0
        assert result.records_loaded == 5
        assert (
            result.records_received
            == result.records_filtered
            + result.records_rejected
            + result.records_skipped
            + result.records_loaded
        )
        assert chunk_lengths == [2, 2, 1]

        with engine.connect() as connection:
            batch = _fetch_batch(connection, result.ingestion_batch_id)
            assert batch["source_name"] == source_name
            assert batch["status"] == STATUS_COMPLETED
            assert batch["completed_at"] is not None
            _assert_result_matches_batch(result, batch)
            for game_pk in game_pks:
                assert _count_pitches(connection, game_pk) == 1
    finally:
        _cleanup_statcast_test(
            engine,
            source_names=[source_name],
            game_pks=game_pks,
        )
        engine.dispose()


def test_non_regular_season_row_is_filtered(tmp_path):
    engine = _engine()
    source_name = "pytest_statcast_filter"
    loaded_game_pk = 888002201
    filtered_game_pk = 888002202
    csv_path = tmp_path / "filter.csv"
    _write_csv(
        csv_path,
        [
            _valid_row(game_pk=loaded_game_pk, pitch_number=1),
            _valid_row(game_pk=filtered_game_pk, pitch_number=1, game_type="S"),
        ],
    )

    try:
        result = _ingest(csv_path, source_name, chunk_size=2)

        assert result.status == STATUS_COMPLETED
        assert result.records_received == 2
        assert result.records_filtered == 1
        assert result.records_rejected == 0
        assert result.records_skipped == 0
        assert result.records_loaded == 1

        with engine.connect() as connection:
            batch = _fetch_batch(connection, result.ingestion_batch_id)
            _assert_result_matches_batch(result, batch)
            assert batch["records_filtered"] == 1
            assert _count_pitches(connection, loaded_game_pk) == 1
            assert _count_pitches(connection, filtered_game_pk) == 0
            assert _fetch_rejections(connection, result.ingestion_batch_id) == []
    finally:
        _cleanup_statcast_test(
            engine,
            source_names=[source_name],
            game_pks=[loaded_game_pk, filtered_game_pk],
        )
        engine.dispose()


def test_invalid_row_is_rejected_and_audited(tmp_path):
    engine = _engine()
    source_name = "pytest_statcast_reject"
    loaded_game_pk = 888002301
    rejected_game_pk = 888002302
    csv_path = tmp_path / "reject.csv"
    _write_csv(
        csv_path,
        [
            _valid_row(game_pk=loaded_game_pk, pitch_number=1),
            _valid_row(game_pk=None, at_bat_number=1, pitch_number=1),
        ],
    )

    try:
        result = _ingest(csv_path, source_name, chunk_size=2)

        assert result.status == STATUS_COMPLETED
        assert result.records_received == 2
        assert result.records_filtered == 0
        assert result.records_rejected == 1
        assert result.records_skipped == 0
        assert result.records_loaded == 1

        with engine.connect() as connection:
            batch = _fetch_batch(connection, result.ingestion_batch_id)
            _assert_result_matches_batch(result, batch)
            assert _count_pitches(connection, loaded_game_pk) == 1
            assert _count_pitches(connection, rejected_game_pk) == 0

            rejections = _fetch_rejections(connection, result.ingestion_batch_id)
            assert len(rejections) == 1
            rejection = rejections[0]
            assert rejection["source_row_number"] == 2
            assert rejection["rejection_reason"] == MISSING_REQUIRED_FIELD
    finally:
        _cleanup_statcast_test(
            engine,
            source_names=[source_name],
            game_pks=[loaded_game_pk, rejected_game_pk],
        )
        engine.dispose()


def test_existing_source_key_is_skipped(tmp_path):
    engine = _engine()
    original_source_name = "pytest_statcast_skip_original"
    ingest_source_name = "pytest_statcast_skip_ingest"
    game_pk = 888002401
    csv_path = tmp_path / "skip.csv"
    duplicate_row = _valid_row(game_pk=game_pk, pitch_number=1)
    _write_csv(csv_path, [duplicate_row])

    try:
        with engine.begin() as connection:
            original_batch_id = create_ingestion_batch(
                connection,
                original_source_name,
                datetime.now(timezone.utc),
            )
            load_statcast_chunk(
                connection,
                original_batch_id,
                pd.DataFrame([duplicate_row]),
                [],
            )
            original = _fetch_pitch(connection, game_pk, 1, 1)[0]
            original_pitch_id = original["raw_statcast_pitch_id"]

        result = _ingest(csv_path, ingest_source_name, chunk_size=2)

        assert result.status == STATUS_COMPLETED
        assert result.ingestion_batch_id != original_batch_id
        assert result.records_received == 1
        assert result.records_filtered == 0
        assert result.records_rejected == 0
        assert result.records_skipped == 1
        assert result.records_loaded == 0

        with engine.connect() as connection:
            batch = _fetch_batch(connection, result.ingestion_batch_id)
            _assert_result_matches_batch(result, batch)
            pitches = _fetch_pitch(connection, game_pk, 1, 1)
            assert len(pitches) == 1
            assert pitches[0]["raw_statcast_pitch_id"] == original_pitch_id
            assert pitches[0]["ingestion_batch_id"] == original_batch_id
            assert _fetch_rejections(connection, result.ingestion_batch_id) == []
    finally:
        _cleanup_statcast_test(
            engine,
            source_names=[original_source_name, ingest_source_name],
            game_pks=[game_pk],
        )
        engine.dispose()


def test_source_row_numbers_span_chunks(tmp_path):
    engine = _engine()
    source_name = "pytest_statcast_row_numbers"
    game_pks = [888002501, 888002502, 888002503, 888002504, 888002505]
    csv_path = tmp_path / "row_numbers.csv"
    _write_csv(
        csv_path,
        [
            _valid_row(game_pk=game_pks[0], pitch_number=1),
            _valid_row(game_pk=game_pks[1], pitch_number=0),
            _valid_row(game_pk=game_pks[2], pitch_number=1, game_type="S"),
            _valid_row(game_pk=None, at_bat_number=1, pitch_number=1),
            _valid_row(game_pk=game_pks[4], pitch_number=1),
        ],
    )

    try:
        result = _ingest(csv_path, source_name, chunk_size=2)

        assert result.status == STATUS_COMPLETED
        assert result.records_received == 5
        assert result.records_filtered == 1
        assert result.records_rejected == 2
        assert result.records_skipped == 0
        assert result.records_loaded == 2

        with engine.connect() as connection:
            rejections = _fetch_rejections(connection, result.ingestion_batch_id)
            assert [row["source_row_number"] for row in rejections] == [2, 4]
            assert rejections[0]["rejection_reason"] == "INVALID_SOURCE_KEY"
            assert rejections[1]["rejection_reason"] == MISSING_REQUIRED_FIELD
            assert _count_pitches(connection, game_pks[0]) == 1
            assert _count_pitches(connection, game_pks[1]) == 0
            assert _count_pitches(connection, game_pks[2]) == 0
            assert _count_pitches(connection, game_pks[4]) == 1
    finally:
        _cleanup_statcast_test(
            engine,
            source_names=[source_name],
            game_pks=game_pks,
        )
        engine.dispose()


def test_fatal_error_rolls_back_current_chunk_and_fails_batch(tmp_path, monkeypatch):
    engine = _engine()
    source_name = "pytest_statcast_fatal"
    game_pks = [888002601, 888002602, 888002603, 888002604, 888002605, 888002606]
    csv_path = tmp_path / "fatal.csv"
    _write_csv(
        csv_path,
        [_valid_row(game_pk=game_pk, pitch_number=1) for game_pk in game_pks],
    )

    real_update = batch_module.update_ingestion_batch_counts
    update_calls = {"count": 0}

    def fail_on_second_chunk(connection, ingestion_batch_id, **counts):
        update_calls["count"] += 1
        if update_calls["count"] == 2:
            raise RuntimeError("deterministic chunk-2 failure")
        return real_update(connection, ingestion_batch_id, **counts)

    monkeypatch.setattr(
        batch_module,
        "update_ingestion_batch_counts",
        fail_on_second_chunk,
    )
    _patch_imported_name(
        monkeypatch,
        statcast,
        "update_ingestion_batch_counts",
        fail_on_second_chunk,
    )

    try:
        result = _ingest(csv_path, source_name, chunk_size=2)

        assert isinstance(result, IngestionResult)
        assert result.status == STATUS_FAILED
        assert result.error_message
        assert "deterministic chunk-2 failure" in result.error_message
        assert result.records_received == 2
        assert result.records_filtered == 0
        assert result.records_rejected == 0
        assert result.records_skipped == 0
        assert result.records_loaded == 2
        assert update_calls["count"] == 2

        with engine.connect() as connection:
            batch = _fetch_batch(connection, result.ingestion_batch_id)
            assert batch["status"] == STATUS_FAILED
            assert batch["completed_at"] is not None
            _assert_result_matches_batch(result, batch)
            assert _count_pitches(connection, game_pks[0]) == 1
            assert _count_pitches(connection, game_pks[1]) == 1
            assert _count_pitches(connection, game_pks[2]) == 0
            assert _count_pitches(connection, game_pks[3]) == 0
            assert _count_pitches(connection, game_pks[4]) == 0
            assert _count_pitches(connection, game_pks[5]) == 0
    finally:
        _cleanup_statcast_test(
            engine,
            source_names=[source_name],
            game_pks=game_pks,
        )
        engine.dispose()


def test_completed_ingestion_counter_invariant(tmp_path):
    engine = _engine()
    original_source_name = "pytest_statcast_invariant_original"
    ingest_source_name = "pytest_statcast_invariant_ingest"
    loaded_game_pk = 888002701
    filtered_game_pk = 888002702
    rejected_game_pk = 888002703
    skipped_game_pk = 888002704
    csv_path = tmp_path / "invariant.csv"
    skipped_row = _valid_row(game_pk=skipped_game_pk, pitch_number=1)
    _write_csv(
        csv_path,
        [
            _valid_row(game_pk=loaded_game_pk, pitch_number=1),
            _valid_row(game_pk=filtered_game_pk, pitch_number=1, game_type="S"),
            _valid_row(game_pk=rejected_game_pk, pitch_number=0),
            skipped_row,
        ],
    )

    try:
        with engine.begin() as connection:
            original_batch_id = create_ingestion_batch(
                connection,
                original_source_name,
                datetime.now(timezone.utc),
            )
            load_statcast_chunk(
                connection,
                original_batch_id,
                pd.DataFrame([skipped_row]),
                [],
            )

        result = _ingest(csv_path, ingest_source_name, chunk_size=2)

        assert result.status == STATUS_COMPLETED
        assert result.records_received == 4
        assert result.records_filtered == 1
        assert result.records_rejected == 1
        assert result.records_skipped == 1
        assert result.records_loaded == 1
        assert (
            result.records_received
            == result.records_filtered
            + result.records_rejected
            + result.records_skipped
            + result.records_loaded
        )

        with engine.connect() as connection:
            batch = _fetch_batch(connection, result.ingestion_batch_id)
            _assert_result_matches_batch(result, batch)
            assert (
                batch["records_received"]
                == batch["records_filtered"]
                + batch["records_rejected"]
                + batch["records_skipped"]
                + batch["records_loaded"]
            )
    finally:
        _cleanup_statcast_test(
            engine,
            source_names=[original_source_name, ingest_source_name],
            game_pks=[
                loaded_game_pk,
                filtered_game_pk,
                rejected_game_pk,
                skipped_game_pk,
            ],
        )
        engine.dispose()
