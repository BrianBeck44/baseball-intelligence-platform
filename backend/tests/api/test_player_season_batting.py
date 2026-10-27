"""Tests for GET /players/{player_id}/season-batting."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.db import get_connection
from app.main import app
from tests.analytics.test_player_performance_trends import (
    _create_engine,
    _insert_player,
    _insert_season,
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


def _insert_player_season_batting(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
    games: int = 2,
    plate_appearances: int = 8,
    at_bats: int = 7,
    hits: int = 3,
    singles: int = 2,
    doubles: int = 1,
    triples: int = 0,
    home_runs: int = 0,
    walks: int = 1,
    hit_by_pitch: int = 0,
    strikeouts: int = 2,
    sacrifice_flies: int = 0,
    sacrifice_bunts: int = 0,
    batting_average: float | None = None,
    on_base_percentage: float | None = None,
    slugging_percentage: float | None = None,
    ops: float | None = None,
    strikeout_rate: float | None = None,
    walk_rate: float | None = None,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO analytics.player_season_batting (
                player_id,
                season_id,
                games,
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
                sacrifice_bunts,
                batting_average,
                on_base_percentage,
                slugging_percentage,
                ops,
                strikeout_rate,
                walk_rate
            )
            VALUES (
                :player_id,
                :season_id,
                :games,
                :plate_appearances,
                :at_bats,
                :hits,
                :singles,
                :doubles,
                :triples,
                :home_runs,
                :walks,
                :hit_by_pitch,
                :strikeouts,
                :sacrifice_flies,
                :sacrifice_bunts,
                :batting_average,
                :on_base_percentage,
                :slugging_percentage,
                :ops,
                :strikeout_rate,
                :walk_rate
            )
            """
        ),
        {
            "player_id": player_id,
            "season_id": season_id,
            "games": games,
            "plate_appearances": plate_appearances,
            "at_bats": at_bats,
            "hits": hits,
            "singles": singles,
            "doubles": doubles,
            "triples": triples,
            "home_runs": home_runs,
            "walks": walks,
            "hit_by_pitch": hit_by_pitch,
            "strikeouts": strikeouts,
            "sacrifice_flies": sacrifice_flies,
            "sacrifice_bunts": sacrifice_bunts,
            "batting_average": batting_average,
            "on_base_percentage": on_base_percentage,
            "slugging_percentage": slugging_percentage,
            "ops": ops,
            "strikeout_rate": strikeout_rate,
            "walk_rate": walk_rate,
        },
    )


def test_season_batting_returns_stored_line_for_valid_player() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888098101, "Ada Season")
            season_id = _insert_season(connection, 2891)
            _insert_player_season_batting(
                connection,
                player_id=player_id,
                season_id=season_id,
                batting_average=3 / 7,
                on_base_percentage=4 / 8,
                slugging_percentage=4 / 7,
                ops=(4 / 8) + (4 / 7),
                strikeout_rate=2 / 8,
                walk_rate=1 / 8,
            )

            with _client_for_connection(connection) as client:
                response = client.get(
                    f"/players/{player_id}/season-batting",
                    params={"season_id": season_id},
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["player_id"] == player_id
            assert payload["full_name"] == "Ada Season"
            assert payload["season_id"] == season_id
            assert payload["season_year"] == 2891
            assert payload["games"] == 2
            assert payload["plate_appearances"] == 8
            assert payload["at_bats"] == 7
            assert payload["hits"] == 3
            assert payload["singles"] == 2
            assert payload["doubles"] == 1
            assert payload["triples"] == 0
            assert payload["home_runs"] == 0
            assert payload["walks"] == 1
            assert payload["hit_by_pitch"] == 0
            assert payload["strikeouts"] == 2
            assert payload["sacrifice_flies"] == 0
            assert payload["sacrifice_bunts"] == 0
            assert payload["batting_average"] == pytest.approx(3 / 7)
            assert payload["on_base_percentage"] == pytest.approx(4 / 8)
            assert payload["slugging_percentage"] == pytest.approx(4 / 7)
            assert payload["ops"] == pytest.approx((4 / 8) + (4 / 7))
            assert payload["strikeout_rate"] == pytest.approx(2 / 8)
            assert payload["walk_rate"] == pytest.approx(1 / 8)
    finally:
        engine.dispose()


def test_unknown_player_returns_404() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            with _client_for_connection(connection) as client:
                response = client.get(
                    "/players/9000000001/season-batting",
                    params={"season_id": 1},
                )

            assert response.status_code == 404
            assert response.json() == {"detail": "Player not found"}
    finally:
        engine.dispose()


def test_existing_player_without_season_batting_returns_null_statistics() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888098102, "Pat Empty")
            season_id = _insert_season(connection, 2892)

            with _client_for_connection(connection) as client:
                response = client.get(
                    f"/players/{player_id}/season-batting",
                    params={"season_id": season_id},
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["player_id"] == player_id
            assert payload["full_name"] == "Pat Empty"
            assert payload["season_id"] == season_id
            assert payload["season_year"] == 2892
            assert payload["games"] is None
            assert payload["plate_appearances"] is None
            assert payload["at_bats"] is None
            assert payload["hits"] is None
            assert payload["singles"] is None
            assert payload["doubles"] is None
            assert payload["triples"] is None
            assert payload["home_runs"] is None
            assert payload["walks"] is None
            assert payload["hit_by_pitch"] is None
            assert payload["strikeouts"] is None
            assert payload["sacrifice_flies"] is None
            assert payload["sacrifice_bunts"] is None
            assert payload["batting_average"] is None
            assert payload["on_base_percentage"] is None
            assert payload["slugging_percentage"] is None
            assert payload["ops"] is None
            assert payload["strikeout_rate"] is None
            assert payload["walk_rate"] is None
    finally:
        engine.dispose()


def test_null_rate_values_remain_null() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888098103, "Ada Null Rates")
            season_id = _insert_season(connection, 2893)
            _insert_player_season_batting(
                connection,
                player_id=player_id,
                season_id=season_id,
                games=1,
                plate_appearances=1,
                at_bats=0,
                hits=0,
                singles=0,
                doubles=0,
                triples=0,
                home_runs=0,
                walks=0,
                strikeouts=0,
                sacrifice_bunts=1,
            )

            with _client_for_connection(connection) as client:
                response = client.get(
                    f"/players/{player_id}/season-batting",
                    params={"season_id": season_id},
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["games"] == 1
            assert payload["plate_appearances"] == 1
            assert payload["at_bats"] == 0
            assert payload["sacrifice_bunts"] == 1
            assert payload["batting_average"] is None
            assert payload["on_base_percentage"] is None
            assert payload["slugging_percentage"] is None
            assert payload["ops"] is None
            assert payload["strikeout_rate"] is None
            assert payload["walk_rate"] is None
    finally:
        engine.dispose()


def test_season_batting_does_not_manage_transactions() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888098104, "Ada Readonly")
            season_id = _insert_season(connection, 2894)
            _insert_player_season_batting(
                connection,
                player_id=player_id,
                season_id=season_id,
            )
            connection.commit = MagicMock()
            connection.rollback = MagicMock()
            connection.begin = MagicMock()

            with _client_for_connection(connection) as client:
                response = client.get(
                    f"/players/{player_id}/season-batting",
                    params={"season_id": season_id},
                )

            assert response.status_code == 200
            connection.commit.assert_not_called()
            connection.rollback.assert_not_called()
            connection.begin.assert_not_called()
    finally:
        engine.dispose()


def test_invalid_player_id_and_season_id_return_422() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            with _client_for_connection(connection) as client:
                invalid_player = client.get(
                    "/players/0/season-batting",
                    params={"season_id": 1},
                )
                invalid_season = client.get(
                    "/players/1/season-batting",
                    params={"season_id": 0},
                )
                missing_season = client.get("/players/1/season-batting")

            assert invalid_player.status_code == 422
            assert invalid_season.status_code == 422
            assert missing_season.status_code == 422
    finally:
        engine.dispose()
