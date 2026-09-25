"""Tests for curated.game_team upserts."""

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.curated.game_team_data import GameTeamLoadResult, load_game_teams
from app.curated.statcast_game_team_data import StatcastGameTeam


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


def _insert_season(connection: Connection, season_year: int) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.season (season_year)
            VALUES (:season_year)
            RETURNING season_id
            """
        ),
        {"season_year": season_year},
    ).scalar_one()


def _insert_game_type(connection: Connection, code: str, name: str) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.game_type (code, name)
            VALUES (:code, :name)
            RETURNING id
            """
        ),
        {"code": code, "name": name},
    ).scalar_one()


def _insert_game(
    connection: Connection,
    *,
    mlb_game_pk: int,
    season_id: int,
    game_type_id: int,
    official_game_date: date,
) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.game (
                mlb_game_pk,
                season_id,
                official_game_date,
                game_type_id
            )
            VALUES (
                :mlb_game_pk,
                :season_id,
                :official_game_date,
                :game_type_id
            )
            RETURNING game_id
            """
        ),
        {
            "mlb_game_pk": mlb_game_pk,
            "season_id": season_id,
            "official_game_date": official_game_date,
            "game_type_id": game_type_id,
        },
    ).scalar_one()


def _insert_team(connection: Connection, code: str, name: str) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.team (code, name)
            VALUES (:code, :name)
            RETURNING team_id
            """
        ),
        {"code": code, "name": name},
    ).scalar_one()


def _fetch_game_team(connection: Connection, game_id: int, team_id: int):
    return connection.execute(
        text(
            """
            SELECT game_team_id, game_id, team_id, home_away
            FROM curated.game_team
            WHERE game_id = :game_id
              AND team_id = :team_id
            """
        ),
        {"game_id": game_id, "team_id": team_id},
    ).mappings().one()


def _count_game_teams(connection: Connection, game_ids: list[int]) -> int:
    return connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM curated.game_team
            WHERE game_id = ANY(:game_ids)
            """
        ),
        {"game_ids": game_ids},
    ).scalar_one()


def test_empty_input_returns_zero_counts():
    connection = MagicMock()

    result = load_game_teams(connection, [])

    assert result == GameTeamLoadResult(game_teams_supplied=0, game_teams_loaded=0)
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_single_game_team_is_inserted():
    engine = _create_engine()
    mlb_game_pk = 900000401

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2079)
            game_type_id = _insert_game_type(connection, "YA", "Yotta Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2079, 4, 8),
            )
            team_id = _insert_team(connection, "ZTA", "Zeta Aces")

            result = load_game_teams(
                connection,
                [
                    StatcastGameTeam(
                        mlb_game_pk=mlb_game_pk,
                        team_code="ZTA",
                        home_away="HOME",
                    )
                ],
            )

            assert result == GameTeamLoadResult(
                game_teams_supplied=1,
                game_teams_loaded=1,
            )
            game_team = _fetch_game_team(connection, game_id, team_id)
            assert game_team["game_id"] == game_id
            assert game_team["team_id"] == team_id
            assert game_team["home_away"] == "HOME"
            assert game_team["game_team_id"] is not None
    finally:
        engine.dispose()


def test_multiple_game_teams_are_inserted():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2078)
            game_type_id = _insert_game_type(connection, "YB", "Yotta Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=900000402,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2078, 4, 8),
            )
            home_team_id = _insert_team(connection, "ZTB", "Zeta Bats")
            away_team_id = _insert_team(connection, "ZTC", "Zeta Cats")

            result = load_game_teams(
                connection,
                [
                    StatcastGameTeam(
                        mlb_game_pk=900000402,
                        team_code="ZTB",
                        home_away="HOME",
                    ),
                    StatcastGameTeam(
                        mlb_game_pk=900000402,
                        team_code="ZTC",
                        home_away="AWAY",
                    ),
                ],
            )

            assert result == GameTeamLoadResult(
                game_teams_supplied=2,
                game_teams_loaded=2,
            )
            assert _count_game_teams(connection, [game_id]) == 2
            home = _fetch_game_team(connection, game_id, home_team_id)
            away = _fetch_game_team(connection, game_id, away_team_id)
            assert home["home_away"] == "HOME"
            assert away["home_away"] == "AWAY"
    finally:
        engine.dispose()


def test_duplicate_input_uses_last_supplied_record():
    engine = _create_engine()
    mlb_game_pk = 900000404

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2077)
            game_type_id = _insert_game_type(connection, "YC", "Yotta Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2077, 4, 8),
            )
            team_id = _insert_team(connection, "ZTD", "Zeta Dogs")

            result = load_game_teams(
                connection,
                [
                    StatcastGameTeam(
                        mlb_game_pk=mlb_game_pk,
                        team_code="ZTD",
                        home_away="HOME",
                    ),
                    StatcastGameTeam(
                        mlb_game_pk=mlb_game_pk,
                        team_code="ZTD",
                        home_away="AWAY",
                    ),
                ],
            )

            assert result == GameTeamLoadResult(
                game_teams_supplied=2,
                game_teams_loaded=2,
            )
            assert _count_game_teams(connection, [game_id]) == 1
            game_team = _fetch_game_team(connection, game_id, team_id)
            assert game_team["home_away"] == "AWAY"
    finally:
        engine.dispose()


def test_existing_game_team_id_is_preserved_when_reloaded():
    engine = _create_engine()
    mlb_game_pk = 900000405

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2076)
            game_type_id = _insert_game_type(connection, "YD", "Yotta Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2076, 4, 8),
            )
            team_id = _insert_team(connection, "ZTE", "Zeta Eagles")

            load_game_teams(
                connection,
                [
                    StatcastGameTeam(
                        mlb_game_pk=mlb_game_pk,
                        team_code="ZTE",
                        home_away="HOME",
                    )
                ],
            )
            original = _fetch_game_team(connection, game_id, team_id)

            load_game_teams(
                connection,
                [
                    StatcastGameTeam(
                        mlb_game_pk=mlb_game_pk,
                        team_code="ZTE",
                        home_away="AWAY",
                    )
                ],
            )
            updated = _fetch_game_team(connection, game_id, team_id)

            assert updated["game_team_id"] == original["game_team_id"]
            assert updated["game_id"] == game_id
            assert updated["team_id"] == team_id
    finally:
        engine.dispose()


def test_existing_home_away_is_updated_on_conflict():
    engine = _create_engine()
    mlb_game_pk = 900000406

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2075)
            game_type_id = _insert_game_type(connection, "YE", "Yotta Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2075, 4, 8),
            )
            team_id = _insert_team(connection, "ZTF", "Zeta Foxes")

            load_game_teams(
                connection,
                [
                    StatcastGameTeam(
                        mlb_game_pk=mlb_game_pk,
                        team_code="ZTF",
                        home_away="HOME",
                    )
                ],
            )
            original = _fetch_game_team(connection, game_id, team_id)
            assert original["home_away"] == "HOME"

            result = load_game_teams(
                connection,
                [
                    StatcastGameTeam(
                        mlb_game_pk=mlb_game_pk,
                        team_code="ZTF",
                        home_away="AWAY",
                    )
                ],
            )

            assert result == GameTeamLoadResult(
                game_teams_supplied=1,
                game_teams_loaded=1,
            )
            updated = _fetch_game_team(connection, game_id, team_id)
            assert updated["game_team_id"] == original["game_team_id"]
            assert updated["home_away"] == "AWAY"
    finally:
        engine.dispose()


def test_missing_game_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900000407

    try:
        with _isolated_connection(engine) as connection:
            _insert_team(connection, "ZTG", "Zeta Giants")

            with pytest.raises(ValueError, match=str(mlb_game_pk)):
                load_game_teams(
                    connection,
                    [
                        StatcastGameTeam(
                            mlb_game_pk=mlb_game_pk,
                            team_code="ZTG",
                            home_away="HOME",
                        )
                    ],
                )
    finally:
        engine.dispose()


def test_missing_team_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900000408

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2074)
            game_type_id = _insert_game_type(connection, "YF", "Yotta Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2074, 4, 8),
            )

            with pytest.raises(ValueError, match="MISSING_TEAM"):
                load_game_teams(
                    connection,
                    [
                        StatcastGameTeam(
                            mlb_game_pk=mlb_game_pk,
                            team_code="MISSING_TEAM",
                            home_away="HOME",
                        )
                    ],
                )

            assert _count_game_teams(connection, [game_id]) == 0
    finally:
        engine.dispose()


def test_multiple_games_and_teams_are_resolved():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2073)
            game_type_id = _insert_game_type(connection, "YG", "Yotta Regular")
            first_game_id = _insert_game(
                connection,
                mlb_game_pk=900000409,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2073, 4, 8),
            )
            second_game_id = _insert_game(
                connection,
                mlb_game_pk=900000410,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2073, 4, 9),
            )
            first_team_id = _insert_team(connection, "ZTI", "Zeta Irons")
            second_team_id = _insert_team(connection, "ZTJ", "Zeta Jays")

            result = load_game_teams(
                connection,
                [
                    StatcastGameTeam(
                        mlb_game_pk=900000409,
                        team_code="ZTI",
                        home_away="HOME",
                    ),
                    StatcastGameTeam(
                        mlb_game_pk=900000410,
                        team_code="ZTJ",
                        home_away="AWAY",
                    ),
                ],
            )

            assert result == GameTeamLoadResult(
                game_teams_supplied=2,
                game_teams_loaded=2,
            )
            first = _fetch_game_team(connection, first_game_id, first_team_id)
            second = _fetch_game_team(connection, second_game_id, second_team_id)
            assert first["home_away"] == "HOME"
            assert second["home_away"] == "AWAY"
    finally:
        engine.dispose()


def test_missing_references_do_not_insert_game_teams():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2072)
            game_type_id = _insert_game_type(connection, "YH", "Yotta Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=900000411,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2072, 4, 8),
            )
            _insert_team(connection, "ZTK", "Zeta Kings")

            with pytest.raises(ValueError, match="900000412"):
                load_game_teams(
                    connection,
                    [
                        StatcastGameTeam(
                            mlb_game_pk=900000411,
                            team_code="ZTK",
                            home_away="HOME",
                        ),
                        StatcastGameTeam(
                            mlb_game_pk=900000412,
                            team_code="ZTK",
                            home_away="AWAY",
                        ),
                    ],
                )

            assert _count_game_teams(connection, [game_id]) == 0
    finally:
        engine.dispose()


def test_game_team_load_result_counts_include_duplicates():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2071)
            game_type_id = _insert_game_type(connection, "YI", "Yotta Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=900000413,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2071, 4, 8),
            )
            first_team_id = _insert_team(connection, "ZTL", "Zeta Lions")
            second_team_id = _insert_team(connection, "ZTN", "Zeta Nuts")

            result = load_game_teams(
                connection,
                [
                    StatcastGameTeam(
                        mlb_game_pk=900000413,
                        team_code="ZTL",
                        home_away="HOME",
                    ),
                    StatcastGameTeam(
                        mlb_game_pk=900000413,
                        team_code="ZTN",
                        home_away="AWAY",
                    ),
                    StatcastGameTeam(
                        mlb_game_pk=900000413,
                        team_code="ZTL",
                        home_away="AWAY",
                    ),
                ],
            )

            assert result == GameTeamLoadResult(
                game_teams_supplied=3,
                game_teams_loaded=3,
            )
            assert _count_game_teams(connection, [game_id]) == 2
            assert _fetch_game_team(connection, game_id, first_team_id)["home_away"] == "AWAY"
            assert _fetch_game_team(connection, game_id, second_team_id)["home_away"] == "AWAY"
    finally:
        engine.dispose()


def test_successful_load_does_not_commit_or_rollback():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2070)
            game_type_id = _insert_game_type(connection, "YJ", "Yotta Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=900000414,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2070, 4, 8),
            )
            team_id = _insert_team(connection, "ZTM", "Zeta Moose")
            connection.commit = MagicMock()
            connection.rollback = MagicMock()

            result = load_game_teams(
                connection,
                [
                    StatcastGameTeam(
                        mlb_game_pk=900000414,
                        team_code="ZTM",
                        home_away="HOME",
                    )
                ],
            )

            assert result == GameTeamLoadResult(
                game_teams_supplied=1,
                game_teams_loaded=1,
            )
            assert _fetch_game_team(connection, game_id, team_id)["home_away"] == "HOME"
            connection.commit.assert_not_called()
            connection.rollback.assert_not_called()
    finally:
        engine.dispose()
