"""Tests for distinct team-code extraction from raw Statcast data."""

from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.curated.statcast_team_data import (
    get_statcast_game_years,
    get_statcast_team_codes,
)
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
    home_team: str | None,
    away_team: str | None,
    game_year: int | None = None,
) -> None:
    batch_id = create_ingestion_batch(
        connection,
        source_name=f"pytest_statcast_team_codes_{game_pk}",
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
                home_team,
                away_team,
                game_year
            )
            VALUES (
                :ingestion_batch_id,
                :game_pk,
                1,
                1,
                :home_team,
                :away_team,
                :game_year
            )
            """
        ),
        {
            "ingestion_batch_id": batch_id,
            "game_pk": game_pk,
            "home_team": home_team,
            "away_team": away_team,
            "game_year": game_year,
        },
    )


def test_home_and_away_team_codes_are_returned():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=888004101,
                home_team="NYY",
                away_team="BOS",
            )

            assert get_statcast_team_codes(connection) == ["BOS", "NYY"]
    finally:
        engine.dispose()


def test_null_team_codes_are_ignored():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=888004102,
                home_team=None,
                away_team=None,
            )
            _insert_pitch(
                connection,
                game_pk=888004103,
                home_team="LAD",
                away_team=None,
            )
            _insert_pitch(
                connection,
                game_pk=888004104,
                home_team=None,
                away_team="SF",
            )

            assert get_statcast_team_codes(connection) == ["LAD", "SF"]
    finally:
        engine.dispose()


def test_duplicate_team_codes_are_deduplicated():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=888004105,
                home_team="NYY",
                away_team="BOS",
            )
            _insert_pitch(
                connection,
                game_pk=888004106,
                home_team="NYY",
                away_team="NYY",
            )
            _insert_pitch(
                connection,
                game_pk=888004107,
                home_team="BOS",
                away_team="BOS",
            )

            assert get_statcast_team_codes(connection) == ["BOS", "NYY"]
    finally:
        engine.dispose()


def test_results_are_sorted_deterministically():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=888004108,
                home_team="SEA",
                away_team="ATL",
            )
            _insert_pitch(
                connection,
                game_pk=888004109,
                home_team="CHC",
                away_team="MIN",
            )

            assert get_statcast_team_codes(connection) == [
                "ATL",
                "CHC",
                "MIN",
                "SEA",
            ]
    finally:
        engine.dispose()


def test_empty_statcast_pitch_table_returns_empty_list():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)

            assert get_statcast_team_codes(connection) == []
            assert get_statcast_game_years(connection) == []
    finally:
        engine.dispose()


def test_distinct_game_years_are_returned_in_sorted_order():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=888004110,
                home_team="NYY",
                away_team="BOS",
                game_year=2025,
            )
            _insert_pitch(
                connection,
                game_pk=888004111,
                home_team="LAD",
                away_team="SF",
                game_year=2022,
            )
            _insert_pitch(
                connection,
                game_pk=888004112,
                home_team="CHC",
                away_team="STL",
                game_year=2022,
            )

            assert get_statcast_game_years(connection) == [2022, 2025]
    finally:
        engine.dispose()


def test_null_game_years_are_ignored():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=888004113,
                home_team="NYY",
                away_team="BOS",
                game_year=None,
            )
            _insert_pitch(
                connection,
                game_pk=888004114,
                home_team="LAD",
                away_team="SF",
                game_year=2024,
            )

            assert get_statcast_game_years(connection) == [2024]
    finally:
        engine.dispose()
