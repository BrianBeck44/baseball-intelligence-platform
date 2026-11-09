"""Tests for GET /analytics/season-ca-ops."""

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
from tests.db import REQUIRED_TEST_DATABASE_NAME


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


def _insert_player_season_ca_ops(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
    plate_appearances: int = 8,
    observed_ops: float | None = 0.8,
    league_ops: float | None = 0.7,
    expected_opponent_ops: float | None = 0.65,
    ca_ops: float | None = 0.85,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO analytics.player_season_ca_ops (
                player_id,
                season_id,
                plate_appearances,
                observed_ops,
                league_ops,
                expected_opponent_ops,
                ca_ops
            )
            VALUES (
                :player_id,
                :season_id,
                :plate_appearances,
                :observed_ops,
                :league_ops,
                :expected_opponent_ops,
                :ca_ops
            )
            """
        ),
        {
            "player_id": player_id,
            "season_id": season_id,
            "plate_appearances": plate_appearances,
            "observed_ops": observed_ops,
            "league_ops": league_ops,
            "expected_opponent_ops": expected_opponent_ops,
            "ca_ops": ca_ops,
        },
    )


def test_season_ca_ops_returns_multiple_players() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()
            assert database_name == REQUIRED_TEST_DATABASE_NAME

            first_id = _insert_player(connection, 888198301, "Ada Season CA")
            second_id = _insert_player(connection, 888198302, "Pat Season CA")
            season_id = _insert_season(connection, 3901)
            _insert_player_season_ca_ops(
                connection,
                player_id=first_id,
                season_id=season_id,
                plate_appearances=12,
                observed_ops=0.812345,
                league_ops=0.700000,
                expected_opponent_ops=0.650000,
                ca_ops=0.862345,
            )
            _insert_player_season_ca_ops(
                connection,
                player_id=second_id,
                season_id=season_id,
                plate_appearances=20,
                observed_ops=0.900000,
                league_ops=0.710000,
                expected_opponent_ops=0.740000,
                ca_ops=0.870000,
            )

            with _client_for_connection(connection) as client:
                response = client.get(
                    "/analytics/season-ca-ops",
                    params={"season_id": season_id},
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["season_id"] == season_id
            assert payload["season_year"] == 3901
            assert len(payload["players"]) == 2
            by_name = {row["full_name"]: row for row in payload["players"]}
            assert by_name["Ada Season CA"]["player_id"] == first_id
            assert by_name["Ada Season CA"]["season_id"] == season_id
            assert by_name["Ada Season CA"]["season_year"] == 3901
            assert by_name["Ada Season CA"]["plate_appearances"] == 12
            assert by_name["Ada Season CA"]["observed_ops"] == pytest.approx(
                0.812345
            )
            assert by_name["Ada Season CA"]["league_ops"] == pytest.approx(0.7)
            assert by_name["Ada Season CA"]["expected_opponent_ops"] == (
                pytest.approx(0.65)
            )
            assert by_name["Ada Season CA"]["ca_ops"] == pytest.approx(0.862345)
            assert by_name["Pat Season CA"]["player_id"] == second_id
            assert by_name["Pat Season CA"]["ca_ops"] == pytest.approx(0.87)
    finally:
        engine.dispose()


def test_null_ca_ops_values_remain_null() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888198303, "Ada Null Season")
            season_id = _insert_season(connection, 3902)
            _insert_player_season_ca_ops(
                connection,
                player_id=player_id,
                season_id=season_id,
                plate_appearances=0,
                observed_ops=None,
                league_ops=None,
                expected_opponent_ops=None,
                ca_ops=None,
            )

            with _client_for_connection(connection) as client:
                response = client.get(
                    "/analytics/season-ca-ops",
                    params={"season_id": season_id},
                )

            assert response.status_code == 200
            payload = response.json()
            assert len(payload["players"]) == 1
            row = payload["players"][0]
            assert row["player_id"] == player_id
            assert row["plate_appearances"] == 0
            assert row["observed_ops"] is None
            assert row["league_ops"] is None
            assert row["expected_opponent_ops"] is None
            assert row["ca_ops"] is None
    finally:
        engine.dispose()


def test_requested_season_id_is_respected() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888198304, "Ada Filter CA")
            first_season_id = _insert_season(connection, 3903)
            second_season_id = _insert_season(connection, 3904)
            _insert_player_season_ca_ops(
                connection,
                player_id=player_id,
                season_id=first_season_id,
                plate_appearances=10,
                ca_ops=0.820000,
            )
            _insert_player_season_ca_ops(
                connection,
                player_id=player_id,
                season_id=second_season_id,
                plate_appearances=20,
                ca_ops=0.880000,
            )

            with _client_for_connection(connection) as client:
                response = client.get(
                    "/analytics/season-ca-ops",
                    params={"season_id": first_season_id},
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["season_id"] == first_season_id
            assert payload["season_year"] == 3903
            assert len(payload["players"]) == 1
            assert payload["players"][0]["plate_appearances"] == 10
            assert payload["players"][0]["ca_ops"] == pytest.approx(0.82)
            assert payload["players"][0]["ca_ops"] != pytest.approx(0.88)
    finally:
        engine.dispose()


def test_empty_season_returns_empty_player_list() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 3905)

            with _client_for_connection(connection) as client:
                response = client.get(
                    "/analytics/season-ca-ops",
                    params={"season_id": season_id},
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["season_id"] == season_id
            assert payload["season_year"] == 3905
            assert payload["players"] == []
    finally:
        engine.dispose()


def test_unknown_season_returns_empty_player_list() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            with _client_for_connection(connection) as client:
                response = client.get(
                    "/analytics/season-ca-ops",
                    params={"season_id": 9000000003},
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["season_id"] == 9000000003
            assert payload["season_year"] is None
            assert payload["players"] == []
    finally:
        engine.dispose()


def test_season_ca_ops_analytics_does_not_manage_transactions() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888198305, "Ada Readonly List")
            season_id = _insert_season(connection, 3906)
            _insert_player_season_ca_ops(
                connection,
                player_id=player_id,
                season_id=season_id,
            )
            connection.commit = MagicMock()
            connection.rollback = MagicMock()
            connection.begin = MagicMock()

            with _client_for_connection(connection) as client:
                response = client.get(
                    "/analytics/season-ca-ops",
                    params={"season_id": season_id},
                )

            assert response.status_code == 200
            connection.commit.assert_not_called()
            connection.rollback.assert_not_called()
            connection.begin.assert_not_called()
    finally:
        engine.dispose()


def test_invalid_and_missing_season_id_return_422() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            with _client_for_connection(connection) as client:
                invalid_season = client.get(
                    "/analytics/season-ca-ops",
                    params={"season_id": 0},
                )
                missing_season = client.get("/analytics/season-ca-ops")

            assert invalid_season.status_code == 422
            assert missing_season.status_code == 422
    finally:
        engine.dispose()
