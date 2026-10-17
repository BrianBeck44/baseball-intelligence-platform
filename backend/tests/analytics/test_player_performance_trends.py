"""Tests for analytics.player_performance_trends rolling windows."""

from contextlib import contextmanager
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from tests.db import create_test_engine


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


def _insert_player(connection: Connection, mlb_player_id: int, full_name: str) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.player (mlb_player_id, full_name)
            VALUES (:mlb_player_id, :full_name)
            RETURNING player_id
            """
        ),
        {"mlb_player_id": mlb_player_id, "full_name": full_name},
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


def _insert_game_team(
    connection: Connection,
    *,
    game_id: int,
    team_id: int,
    home_away: str,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO curated.game_team (game_id, team_id, home_away)
            VALUES (:game_id, :team_id, :home_away)
            """
        ),
        {"game_id": game_id, "team_id": team_id, "home_away": home_away},
    )


def _insert_player_game_batting(
    connection: Connection,
    *,
    player_id: int,
    game_id: int,
    team_id: int,
    plate_appearances: int,
    at_bats: int,
    hits: int,
    singles: int,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO analytics.player_game_batting (
                player_id,
                game_id,
                team_id,
                plate_appearances,
                at_bats,
                hits,
                singles,
                doubles,
                triples,
                home_runs,
                walks,
                hit_by_pitch,
                strikeouts,
                sacrifice_flies,
                sacrifice_bunts
            )
            VALUES (
                :player_id,
                :game_id,
                :team_id,
                :plate_appearances,
                :at_bats,
                :hits,
                :singles,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0
            )
            """
        ),
        {
            "player_id": player_id,
            "game_id": game_id,
            "team_id": team_id,
            "plate_appearances": plate_appearances,
            "at_bats": at_bats,
            "hits": hits,
            "singles": singles,
        },
    )


def _fetch_season_trend(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
):
    return (
        connection.execute(
            text(
                """
                SELECT
                    season_game_number,
                    rolling_7_plate_appearances,
                    rolling_14_plate_appearances,
                    rolling_30_plate_appearances,
                    season_plate_appearances,
                    rolling_14_ops,
                    season_ops
                FROM analytics.player_performance_trends
                WHERE player_id = :player_id
                  AND season_id = :season_id
                """
            ),
            {"player_id": player_id, "season_id": season_id},
        )
        .mappings()
        .one()
    )


def test_rolling_windows_exclude_prior_season_games():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888093101, "Ada Trend")
            team_id = _insert_team(connection, "ZPT", "Zeta Trends")
            game_type_id = _insert_game_type(
                connection, "ZPT", "Zeta Performance Trends"
            )
            first_season_id = _insert_season(connection, 2831)
            second_season_id = _insert_season(connection, 2832)

            first_game_id = _insert_game(
                connection,
                mlb_game_pk=913001001,
                season_id=first_season_id,
                game_type_id=game_type_id,
                official_game_date=date(2831, 4, 8),
            )
            _insert_game_team(
                connection,
                game_id=first_game_id,
                team_id=team_id,
                home_away="HOME",
            )
            _insert_player_game_batting(
                connection,
                player_id=player_id,
                game_id=first_game_id,
                team_id=team_id,
                plate_appearances=4,
                at_bats=4,
                hits=4,
                singles=4,
            )

            second_game_id = _insert_game(
                connection,
                mlb_game_pk=913001002,
                season_id=second_season_id,
                game_type_id=game_type_id,
                official_game_date=date(2832, 4, 8),
            )
            _insert_game_team(
                connection,
                game_id=second_game_id,
                team_id=team_id,
                home_away="HOME",
            )
            _insert_player_game_batting(
                connection,
                player_id=player_id,
                game_id=second_game_id,
                team_id=team_id,
                plate_appearances=4,
                at_bats=4,
                hits=0,
                singles=0,
            )

            trend = _fetch_season_trend(
                connection,
                player_id=player_id,
                season_id=second_season_id,
            )

            assert trend["season_game_number"] == 1
            assert trend["rolling_7_plate_appearances"] == 4
            assert trend["rolling_14_plate_appearances"] == 4
            assert trend["rolling_30_plate_appearances"] == 4
            assert trend["season_plate_appearances"] == 4
            assert float(trend["rolling_14_ops"]) == pytest.approx(
                float(trend["season_ops"])
            )
    finally:
        engine.dispose()
