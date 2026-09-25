"""Tests for distinct game extraction from raw Statcast data."""

from contextlib import contextmanager
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.curated.statcast_game_data import StatcastGame, get_statcast_games
from app.ingestion.batch import create_ingestion_batch


def _create_engine() -> Engine:
    return create_engine(settings.database_url)


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
    game_date: date | None,
    game_type: str | None,
    at_bat_number: int = 1,
    pitch_number: int = 1,
) -> None:
    batch_id = create_ingestion_batch(
        connection,
        source_name=(
            f"pytest_statcast_game_data_{game_pk}_{at_bat_number}_{pitch_number}"
        ),
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
                game_date,
                game_type
            )
            VALUES (
                :ingestion_batch_id,
                :game_pk,
                :at_bat_number,
                :pitch_number,
                :game_date,
                :game_type
            )
            """
        ),
        {
            "ingestion_batch_id": batch_id,
            "game_pk": game_pk,
            "at_bat_number": at_bat_number,
            "pitch_number": pitch_number,
            "game_date": game_date,
            "game_type": game_type,
        },
    )


def test_empty_statcast_pitch_table_returns_empty_list():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)

            assert get_statcast_games(connection) == []
    finally:
        engine.dispose()


def test_multiple_pitches_in_one_game_produce_one_record():
    engine = _create_engine()
    game_pk = 900000001
    game_date = date(2022, 4, 8)

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                game_date=game_date,
                game_type="R",
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                game_date=game_date,
                game_type="R",
                pitch_number=2,
            )

            result = get_statcast_games(connection)

            assert result == [
                StatcastGame(
                    mlb_game_pk=game_pk,
                    official_game_date=game_date,
                    game_type="R",
                )
            ]
    finally:
        engine.dispose()


def test_multiple_distinct_games_are_returned():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000011,
                game_date=date(2022, 4, 8),
                game_type="R",
            )
            _insert_pitch(
                connection,
                game_pk=900000012,
                game_date=date(2022, 4, 9),
                game_type="R",
            )

            result = get_statcast_games(connection)

            assert result == [
                StatcastGame(
                    mlb_game_pk=900000011,
                    official_game_date=date(2022, 4, 8),
                    game_type="R",
                ),
                StatcastGame(
                    mlb_game_pk=900000012,
                    official_game_date=date(2022, 4, 9),
                    game_type="R",
                ),
            ]
    finally:
        engine.dispose()


def test_results_are_ordered_by_mlb_game_pk():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000023,
                game_date=date(2022, 4, 10),
                game_type="R",
            )
            _insert_pitch(
                connection,
                game_pk=900000021,
                game_date=date(2022, 4, 8),
                game_type="R",
            )
            _insert_pitch(
                connection,
                game_pk=900000022,
                game_date=date(2022, 4, 9),
                game_type="R",
            )

            result = get_statcast_games(connection)

            assert [game.mlb_game_pk for game in result] == [
                900000021,
                900000022,
                900000023,
            ]
    finally:
        engine.dispose()


def test_rows_with_null_game_date_are_ignored():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000031,
                game_date=None,
                game_type="R",
            )
            _insert_pitch(
                connection,
                game_pk=900000032,
                game_date=date(2022, 4, 8),
                game_type="R",
            )

            result = get_statcast_games(connection)

            assert result == [
                StatcastGame(
                    mlb_game_pk=900000032,
                    official_game_date=date(2022, 4, 8),
                    game_type="R",
                )
            ]
    finally:
        engine.dispose()


def test_rows_with_null_game_type_are_ignored():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000041,
                game_date=date(2022, 4, 8),
                game_type=None,
            )
            _insert_pitch(
                connection,
                game_pk=900000042,
                game_date=date(2022, 4, 9),
                game_type="R",
            )

            result = get_statcast_games(connection)

            assert result == [
                StatcastGame(
                    mlb_game_pk=900000042,
                    official_game_date=date(2022, 4, 9),
                    game_type="R",
                )
            ]
    finally:
        engine.dispose()


def test_conflicting_game_dates_raise_value_error():
    engine = _create_engine()
    game_pk = 900000051

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                game_date=date(2022, 4, 8),
                game_type="R",
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                game_date=date(2022, 4, 9),
                game_type="R",
                pitch_number=2,
            )

            with pytest.raises(ValueError, match=str(game_pk)):
                get_statcast_games(connection)
    finally:
        engine.dispose()


def test_conflicting_game_types_raise_value_error():
    engine = _create_engine()
    game_pk = 900000061

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                game_date=date(2022, 4, 8),
                game_type="R",
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                game_date=date(2022, 4, 8),
                game_type="S",
                pitch_number=2,
            )

            with pytest.raises(ValueError, match=str(game_pk)):
                get_statcast_games(connection)
    finally:
        engine.dispose()


def test_returned_values_have_expected_types():
    engine = _create_engine()
    game_pk = 900000071
    game_date = date(2022, 4, 8)

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                game_date=game_date,
                game_type="R",
            )

            result = get_statcast_games(connection)

            assert len(result) == 1
            game = result[0]
            assert isinstance(game, StatcastGame)
            assert isinstance(game.mlb_game_pk, int)
            assert isinstance(game.official_game_date, date)
            assert isinstance(game.game_type, str)
            assert game.mlb_game_pk == game_pk
            assert game.official_game_date == game_date
            assert game.game_type == "R"
    finally:
        engine.dispose()
