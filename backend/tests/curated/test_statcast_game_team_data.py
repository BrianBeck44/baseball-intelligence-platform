"""Tests for distinct game-team extraction from raw Statcast data."""

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.curated.statcast_game_team_data import (
    StatcastGameTeam,
    get_statcast_game_teams,
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
    at_bat_number: int = 1,
    pitch_number: int = 1,
) -> None:
    batch_id = create_ingestion_batch(
        connection,
        source_name=(
            "pytest_statcast_game_team_data_"
            f"{game_pk}_{at_bat_number}_{pitch_number}"
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
                home_team,
                away_team
            )
            VALUES (
                :ingestion_batch_id,
                :game_pk,
                :at_bat_number,
                :pitch_number,
                :home_team,
                :away_team
            )
            """
        ),
        {
            "ingestion_batch_id": batch_id,
            "game_pk": game_pk,
            "at_bat_number": at_bat_number,
            "pitch_number": pitch_number,
            "home_team": home_team,
            "away_team": away_team,
        },
    )


def test_empty_statcast_pitch_table_returns_empty_list():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)

            assert get_statcast_game_teams(connection) == []
    finally:
        engine.dispose()


def test_one_game_produces_exactly_two_records():
    engine = _create_engine()
    game_pk = 900000311

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                home_team="NYY",
                away_team="BOS",
            )

            result = get_statcast_game_teams(connection)

            assert result == [
                StatcastGameTeam(
                    mlb_game_pk=game_pk,
                    team_code="BOS",
                    home_away="AWAY",
                ),
                StatcastGameTeam(
                    mlb_game_pk=game_pk,
                    team_code="NYY",
                    home_away="HOME",
                ),
            ]
    finally:
        engine.dispose()


def test_multiple_games_produce_two_records_per_game():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000321,
                home_team="NYY",
                away_team="BOS",
            )
            _insert_pitch(
                connection,
                game_pk=900000322,
                home_team="LAD",
                away_team="SF",
            )

            result = get_statcast_game_teams(connection)

            assert result == [
                StatcastGameTeam(
                    mlb_game_pk=900000321,
                    team_code="BOS",
                    home_away="AWAY",
                ),
                StatcastGameTeam(
                    mlb_game_pk=900000321,
                    team_code="NYY",
                    home_away="HOME",
                ),
                StatcastGameTeam(
                    mlb_game_pk=900000322,
                    team_code="SF",
                    home_away="AWAY",
                ),
                StatcastGameTeam(
                    mlb_game_pk=900000322,
                    team_code="LAD",
                    home_away="HOME",
                ),
            ]
    finally:
        engine.dispose()


def test_duplicate_pitch_rows_do_not_produce_duplicate_game_team_records():
    engine = _create_engine()
    game_pk = 900000331

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                home_team="NYY",
                away_team="BOS",
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                home_team="NYY",
                away_team="BOS",
                pitch_number=2,
            )

            result = get_statcast_game_teams(connection)

            assert result == [
                StatcastGameTeam(
                    mlb_game_pk=game_pk,
                    team_code="BOS",
                    home_away="AWAY",
                ),
                StatcastGameTeam(
                    mlb_game_pk=game_pk,
                    team_code="NYY",
                    home_away="HOME",
                ),
            ]
    finally:
        engine.dispose()


def test_results_are_ordered_by_mlb_game_pk_and_home_away():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000343,
                home_team="CHC",
                away_team="STL",
            )
            _insert_pitch(
                connection,
                game_pk=900000341,
                home_team="NYY",
                away_team="BOS",
            )
            _insert_pitch(
                connection,
                game_pk=900000342,
                home_team="LAD",
                away_team="SF",
            )

            result = get_statcast_game_teams(connection)

            assert [
                (game_team.mlb_game_pk, game_team.home_away)
                for game_team in result
            ] == [
                (900000341, "AWAY"),
                (900000341, "HOME"),
                (900000342, "AWAY"),
                (900000342, "HOME"),
                (900000343, "AWAY"),
                (900000343, "HOME"),
            ]
    finally:
        engine.dispose()


def test_null_team_values_are_ignored():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000351,
                home_team=None,
                away_team=None,
            )
            _insert_pitch(
                connection,
                game_pk=900000352,
                home_team=None,
                away_team="BOS",
            )
            _insert_pitch(
                connection,
                game_pk=900000353,
                home_team="NYY",
                away_team=None,
            )
            _insert_pitch(
                connection,
                game_pk=900000354,
                home_team="LAD",
                away_team="SF",
            )

            result = get_statcast_game_teams(connection)

            assert result == [
                StatcastGameTeam(
                    mlb_game_pk=900000354,
                    team_code="SF",
                    home_away="AWAY",
                ),
                StatcastGameTeam(
                    mlb_game_pk=900000354,
                    team_code="LAD",
                    home_away="HOME",
                ),
            ]
    finally:
        engine.dispose()


def test_conflicting_home_team_values_raise_value_error():
    engine = _create_engine()
    game_pk = 900000361

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                home_team="NYY",
                away_team="BOS",
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                home_team="TB",
                away_team="BOS",
                pitch_number=2,
            )

            with pytest.raises(ValueError, match=str(game_pk)):
                get_statcast_game_teams(connection)
    finally:
        engine.dispose()


def test_conflicting_away_team_values_raise_value_error():
    engine = _create_engine()
    game_pk = 900000371

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                home_team="NYY",
                away_team="BOS",
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                game_pk=game_pk,
                home_team="NYY",
                away_team="TB",
                pitch_number=2,
            )

            with pytest.raises(ValueError, match=str(game_pk)):
                get_statcast_game_teams(connection)
    finally:
        engine.dispose()


def test_returned_values_are_statcast_game_team_instances():
    engine = _create_engine()
    game_pk = 900000381

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=game_pk,
                home_team="NYY",
                away_team="BOS",
            )

            result = get_statcast_game_teams(connection)

            assert len(result) == 2
            assert all(isinstance(game_team, StatcastGameTeam) for game_team in result)
            away, home = result
            assert isinstance(away.mlb_game_pk, int)
            assert isinstance(away.team_code, str)
            assert isinstance(away.home_away, str)
            assert away == StatcastGameTeam(
                mlb_game_pk=game_pk,
                team_code="BOS",
                home_away="AWAY",
            )
            assert home == StatcastGameTeam(
                mlb_game_pk=game_pk,
                team_code="NYY",
                home_away="HOME",
            )
    finally:
        engine.dispose()


def test_extraction_does_not_manage_transactions():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900000391,
                home_team="NYY",
                away_team="BOS",
            )
            connection.commit = MagicMock()
            connection.rollback = MagicMock()

            get_statcast_game_teams(connection)

            connection.commit.assert_not_called()
            connection.rollback.assert_not_called()
    finally:
        engine.dispose()
