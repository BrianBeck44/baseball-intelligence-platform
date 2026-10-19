"""Tests for GET /players/{player_id}/games."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
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


def _insert_sacrifice_bunt_only(
    connection: Connection,
    *,
    player_id: int,
    game_id: int,
    team_id: int,
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
                1,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                1
            )
            """
        ),
        {
            "player_id": player_id,
            "game_id": game_id,
            "team_id": team_id,
        },
    )


def _seed_player_and_team(connection: Connection) -> tuple[int, int, int]:
    player_id = _insert_player(connection, 888096101, "Ada History")
    team_id = _insert_team(connection, "ZPH", "Zeta History")
    game_type_id = _insert_game_type(connection, "ZPH", "Zeta Player History")
    return player_id, team_id, game_type_id


def _add_game_with_batting(
    connection: Connection,
    *,
    mlb_game_pk: int,
    season_id: int,
    game_type_id: int,
    official_game_date: date,
    player_id: int,
    team_id: int,
    plate_appearances: int,
    at_bats: int,
    hits: int,
    singles: int,
) -> int:
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
        plate_appearances=plate_appearances,
        at_bats=at_bats,
        hits=hits,
        singles=singles,
    )
    return game_id


def test_player_games_returns_history_for_valid_player_and_season() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id, team_id, game_type_id = _seed_player_and_team(connection)
            season_id = _insert_season(connection, 2861)
            game_id = _add_game_with_batting(
                connection,
                mlb_game_pk=915001001,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2861, 4, 8),
                player_id=player_id,
                team_id=team_id,
                plate_appearances=4,
                at_bats=4,
                hits=4,
                singles=4,
            )

            with _client_for_connection(connection) as client:
                response = client.get(
                    f"/players/{player_id}/games",
                    params={"season_id": season_id},
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["player_id"] == player_id
            assert payload["player_name"] == "Ada History"
            assert payload["season_id"] == season_id
            assert len(payload["games"]) == 1
            game = payload["games"][0]
            assert game["game_id"] == game_id
            assert game["game_date"] == "2861-04-08"
            assert game["season_game_number"] == 1
            assert game["plate_appearances"] == 4
            assert game["rolling_14_ops"] == pytest.approx(2.0)
            assert game["season_ops"] == pytest.approx(2.0)
            assert game["ops_difference"] == pytest.approx(0.0)
    finally:
        engine.dispose()


def test_unknown_player_returns_404() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            with _client_for_connection(connection) as client:
                response = client.get(
                    "/players/9000000001/games",
                    params={"season_id": 1},
                )

            assert response.status_code == 404
            assert response.json() == {"detail": "Player not found"}
    finally:
        engine.dispose()


def test_existing_player_without_season_history_returns_empty_list() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888096102, "Pat Empty")

            with _client_for_connection(connection) as client:
                response = client.get(
                    f"/players/{player_id}/games",
                    params={"season_id": 9000000001},
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["player_id"] == player_id
            assert payload["player_name"] == "Pat Empty"
            assert payload["season_id"] == 9000000001
            assert payload["games"] == []
    finally:
        engine.dispose()


def test_limit_is_enforced() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id, team_id, game_type_id = _seed_player_and_team(connection)
            season_id = _insert_season(connection, 2862)
            first_game_id = _add_game_with_batting(
                connection,
                mlb_game_pk=915001011,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2862, 4, 8),
                player_id=player_id,
                team_id=team_id,
                plate_appearances=4,
                at_bats=4,
                hits=1,
                singles=1,
            )
            _add_game_with_batting(
                connection,
                mlb_game_pk=915001012,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2862, 4, 9),
                player_id=player_id,
                team_id=team_id,
                plate_appearances=4,
                at_bats=4,
                hits=0,
                singles=0,
            )
            _add_game_with_batting(
                connection,
                mlb_game_pk=915001013,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2862, 4, 10),
                player_id=player_id,
                team_id=team_id,
                plate_appearances=4,
                at_bats=4,
                hits=2,
                singles=2,
            )

            with _client_for_connection(connection) as client:
                response = client.get(
                    f"/players/{player_id}/games",
                    params={"season_id": season_id, "limit": 2},
                )

            assert response.status_code == 200
            games = response.json()["games"]
            assert len(games) == 2
            assert games[0]["game_id"] == first_game_id
            assert games[0]["game_date"] == "2862-04-08"
            assert games[1]["game_date"] == "2862-04-09"
    finally:
        engine.dispose()


def test_invalid_player_id_season_id_and_limit_return_422() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            with _client_for_connection(connection) as client:
                invalid_player = client.get(
                    "/players/0/games",
                    params={"season_id": 1},
                )
                invalid_season = client.get(
                    "/players/1/games",
                    params={"season_id": 0},
                )
                missing_season = client.get("/players/1/games")
                invalid_limit_low = client.get(
                    "/players/1/games",
                    params={"season_id": 1, "limit": 0},
                )
                invalid_limit_high = client.get(
                    "/players/1/games",
                    params={"season_id": 1, "limit": 201},
                )

            assert invalid_player.status_code == 422
            assert invalid_season.status_code == 422
            assert missing_season.status_code == 422
            assert invalid_limit_low.status_code == 422
            assert invalid_limit_high.status_code == 422
    finally:
        engine.dispose()


def test_null_ops_values_remain_null() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id, team_id, game_type_id = _seed_player_and_team(connection)
            season_id = _insert_season(connection, 2863)
            game_id = _insert_game(
                connection,
                mlb_game_pk=915001021,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2863, 4, 8),
            )
            _insert_game_team(
                connection,
                game_id=game_id,
                team_id=team_id,
                home_away="HOME",
            )
            _insert_sacrifice_bunt_only(
                connection,
                player_id=player_id,
                game_id=game_id,
                team_id=team_id,
            )

            with _client_for_connection(connection) as client:
                response = client.get(
                    f"/players/{player_id}/games",
                    params={"season_id": season_id},
                )

            assert response.status_code == 200
            game = response.json()["games"][0]
            assert game["plate_appearances"] == 1
            assert game["rolling_14_ops"] is None
            assert game["season_ops"] is None
            assert game["ops_difference"] is None
    finally:
        engine.dispose()
