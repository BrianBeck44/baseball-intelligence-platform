"""Tests for season, team, and player lookup endpoints."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.engine import Connection

from app.core.db import get_connection
from app.main import app
from tests.analytics.test_player_performance_trends import (
    _create_engine,
    _insert_game,
    _insert_game_team,
    _insert_game_type,
    _insert_player,
    _insert_player_game_batting,
    _insert_season,
    _insert_team,
    _isolated_connection,
)


@contextmanager
def _client_for_connection(connection: Connection) -> Iterator[TestClient]:
    def override_get_connection() -> Iterator[Connection]:
        yield connection

    app.dependency_overrides[get_connection] = override_get_connection
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _add_batting_game(
    connection: Connection,
    *,
    mlb_game_pk: int,
    season_id: int,
    game_type_id: int,
    official_game_date: date,
    player_id: int,
    team_id: int,
) -> None:
    game_id = _insert_game(
        connection,
        mlb_game_pk=mlb_game_pk,
        season_id=season_id,
        game_type_id=game_type_id,
        official_game_date=official_game_date,
    )
    _insert_game_team(
        connection,
        game_id=game_id,
        team_id=team_id,
        home_away="HOME",
    )
    _insert_player_game_batting(
        connection,
        player_id=player_id,
        game_id=game_id,
        team_id=team_id,
        plate_appearances=4,
        at_bats=4,
        hits=1,
        singles=1,
    )


def test_seasons_return_year_and_id_for_seasons_with_history() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            newer_season_id = _insert_season(connection, 2882)
            older_season_id = _insert_season(connection, 2881)
            _insert_season(connection, 2880)
            player_id = _insert_player(connection, 888097201, "Ada Lookup")
            team_id = _insert_team(connection, "ZLS", "Zeta Lookup")
            game_type_id = _insert_game_type(connection, "ZLS", "Zeta Lookup")
            _add_batting_game(
                connection,
                mlb_game_pk=916001001,
                season_id=older_season_id,
                game_type_id=game_type_id,
                official_game_date=date(2881, 4, 8),
                player_id=player_id,
                team_id=team_id,
            )
            _add_batting_game(
                connection,
                mlb_game_pk=916001002,
                season_id=newer_season_id,
                game_type_id=game_type_id,
                official_game_date=date(2882, 4, 8),
                player_id=player_id,
                team_id=team_id,
            )

            with _client_for_connection(connection) as client:
                response = client.get("/seasons")

            assert response.status_code == 200
            seasons = response.json()["seasons"]
            matching = [
                season
                for season in seasons
                if season["season_id"] in {older_season_id, newer_season_id}
            ]
            assert matching == [
                {"season_id": newer_season_id, "season_year": 2882},
                {"season_id": older_season_id, "season_year": 2881},
            ]
            assert all(season["season_year"] != 2880 for season in seasons)
            assert all(season["season_id"] != season["season_year"] for season in matching)
    finally:
        engine.dispose()


def test_teams_are_limited_to_the_selected_season() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2883)
            other_season_id = _insert_season(connection, 2884)
            player_id = _insert_player(connection, 888097202, "Pat Team")
            alpha_id = _insert_team(connection, "ZLA", "Alpha City")
            beta_id = _insert_team(connection, "ZLB", "Beta City")
            unused_id = _insert_team(connection, "ZLU", "Unused City")
            game_type_id = _insert_game_type(connection, "ZLT", "Zeta Teams")
            _add_batting_game(
                connection,
                mlb_game_pk=916001011,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2883, 4, 8),
                player_id=player_id,
                team_id=beta_id,
            )
            _add_batting_game(
                connection,
                mlb_game_pk=916001012,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2883, 4, 9),
                player_id=player_id,
                team_id=alpha_id,
            )
            _add_batting_game(
                connection,
                mlb_game_pk=916001013,
                season_id=other_season_id,
                game_type_id=game_type_id,
                official_game_date=date(2884, 4, 8),
                player_id=player_id,
                team_id=unused_id,
            )

            with _client_for_connection(connection) as client:
                response = client.get("/teams", params={"season_id": season_id})

            assert response.status_code == 200
            assert response.json() == {
                "teams": [
                    {"team_id": alpha_id, "name": "Alpha City"},
                    {"team_id": beta_id, "name": "Beta City"},
                ]
            }
    finally:
        engine.dispose()


def test_players_search_all_teams_deduplicates_multi_team_players() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2885)
            traded_id = _insert_player(connection, 888097203, "Cam Traded")
            home_id = _insert_player(connection, 888097204, "Bea Home")
            first_team_id = _insert_team(connection, "ZLC", "First Club")
            second_team_id = _insert_team(connection, "ZLD", "Second Club")
            game_type_id = _insert_game_type(connection, "ZLP", "Zeta Players")
            _add_batting_game(
                connection,
                mlb_game_pk=916001021,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2885, 4, 8),
                player_id=traded_id,
                team_id=first_team_id,
            )
            _add_batting_game(
                connection,
                mlb_game_pk=916001022,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2885, 6, 1),
                player_id=traded_id,
                team_id=second_team_id,
            )
            _add_batting_game(
                connection,
                mlb_game_pk=916001023,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2885, 4, 9),
                player_id=home_id,
                team_id=first_team_id,
            )

            with _client_for_connection(connection) as client:
                all_teams = client.get(
                    "/players",
                    params={"season_id": season_id},
                )
                first_team = client.get(
                    "/players",
                    params={"season_id": season_id, "team_id": first_team_id},
                )
                second_team = client.get(
                    "/players",
                    params={"season_id": season_id, "team_id": second_team_id},
                )

            assert all_teams.status_code == 200
            assert all_teams.json() == {
                "players": [
                    {"player_id": home_id, "full_name": "Bea Home"},
                    {"player_id": traded_id, "full_name": "Cam Traded"},
                ]
            }
            assert first_team.json() == {
                "players": [
                    {"player_id": home_id, "full_name": "Bea Home"},
                    {"player_id": traded_id, "full_name": "Cam Traded"},
                ]
            }
            assert second_team.json() == {
                "players": [
                    {"player_id": traded_id, "full_name": "Cam Traded"},
                ]
            }
    finally:
        engine.dispose()


def test_unknown_season_returns_empty_lookup_lists() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            with _client_for_connection(connection) as client:
                teams = client.get("/teams", params={"season_id": 9000000001})
                players = client.get("/players", params={"season_id": 9000000001})

            assert teams.status_code == 200
            assert teams.json() == {"teams": []}
            assert players.status_code == 200
            assert players.json() == {"players": []}
    finally:
        engine.dispose()


def test_invalid_lookup_ids_return_422() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            with _client_for_connection(connection) as client:
                missing_team_season = client.get("/teams")
                invalid_team_season = client.get("/teams", params={"season_id": 0})
                missing_player_season = client.get("/players")
                invalid_player_season = client.get(
                    "/players",
                    params={"season_id": 0},
                )
                invalid_team_id = client.get(
                    "/players",
                    params={"season_id": 1, "team_id": 0},
                )

            assert missing_team_season.status_code == 422
            assert invalid_team_season.status_code == 422
            assert missing_player_season.status_code == 422
            assert invalid_player_season.status_code == 422
            assert invalid_team_id.status_code == 422
    finally:
        engine.dispose()
