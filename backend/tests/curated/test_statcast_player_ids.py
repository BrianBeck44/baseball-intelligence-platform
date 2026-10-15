"""Tests for distinct MLB player-ID extraction from raw Statcast data."""

from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from tests.db import create_test_engine
from app.curated.statcast_player_ids import get_statcast_player_ids
from app.ingestion.batch import create_ingestion_batch


def _create_engine() -> Engine:
    return create_test_engine()


@contextmanager
def _isolated_connection(engine: Engine):
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


def _clear_statcast_pitches(connection: Connection) -> None:
    connection.execute(text("DELETE FROM raw.statcast_pitch"))


def _insert_pitch(
    connection: Connection,
    *,
    game_pk: int,
    batter: int | None,
    pitcher: int | None,
) -> None:
    batch_id = create_ingestion_batch(
        connection,
        source_name=f"pytest_statcast_player_ids_{game_pk}",
        started_at=datetime.now(timezone.utc),
    )
    connection.execute(
        text(
            """
            INSERT INTO raw.statcast_pitch (
                ingestion_batch_id,
                game_pk,
                at_bat_number,
                pitch_number,
                batter,
                pitcher
            )
            VALUES (
                :ingestion_batch_id,
                :game_pk,
                1,
                1,
                :batter,
                :pitcher
            )
            """
        ),
        {
            "ingestion_batch_id": batch_id,
            "game_pk": game_pk,
            "batter": batter,
            "pitcher": pitcher,
        },
    )


def test_batter_only_ids_are_returned():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=888003101,
                batter=1001,
                pitcher=None,
            )

            assert get_statcast_player_ids(connection) == [1001]
    finally:
        engine.dispose()


def test_pitcher_only_ids_are_returned():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=888003102,
                batter=None,
                pitcher=2002,
            )

            assert get_statcast_player_ids(connection) == [2002]
    finally:
        engine.dispose()


def test_id_appearing_as_batter_and_pitcher_is_returned_once():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=888003103,
                batter=3003,
                pitcher=3003,
            )
            _insert_pitch(
                connection,
                game_pk=888003104,
                batter=3003,
                pitcher=4004,
            )

            assert get_statcast_player_ids(connection) == [3003, 4004]
    finally:
        engine.dispose()


def test_null_batter_and_pitcher_values_are_ignored():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=888003105,
                batter=None,
                pitcher=None,
            )
            _insert_pitch(
                connection,
                game_pk=888003106,
                batter=5005,
                pitcher=None,
            )

            assert get_statcast_player_ids(connection) == [5005]
    finally:
        engine.dispose()


def test_results_are_sorted_deterministically():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=888003107,
                batter=50,
                pitcher=10,
            )
            _insert_pitch(
                connection,
                game_pk=888003108,
                batter=40,
                pitcher=20,
            )

            assert get_statcast_player_ids(connection) == [10, 20, 40, 50]
    finally:
        engine.dispose()


def test_empty_statcast_pitch_table_returns_empty_list():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)

            assert get_statcast_player_ids(connection) == []
    finally:
        engine.dispose()
