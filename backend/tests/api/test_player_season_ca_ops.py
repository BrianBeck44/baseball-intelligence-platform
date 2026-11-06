"""Tests for GET /players/{player_id}/season-ca-ops."""

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


def test_season_ca_ops_returns_stored_line_for_valid_player() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()
            assert database_name == REQUIRED_TEST_DATABASE_NAME

            player_id = _insert_player(connection, 888098201, "Ada CA-OPS")
            season_id = _insert_season(connection, 2901)
            _insert_player_season_ca_ops(
                connection,
                player_id=player_id,
                season_id=season_id,
                plate_appearances=12,
                observed_ops=0.812345,
                league_ops=0.700000,
                expected_opponent_ops=0.650000,
                ca_ops=0.862345,
            )

            with _client_for_connection(connection) as client:
                response = client.get(
                    f"/players/{player_id}/season-ca-ops",
                    params={"season_id": season_id},
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["player_id"] == player_id
            assert payload["full_name"] == "Ada CA-OPS"
            assert payload["season_id"] == season_id
            assert payload["season_year"] == 2901
            assert payload["plate_appearances"] == 12
            assert payload["observed_ops"] == pytest.approx(0.812345)
            assert payload["league_ops"] == pytest.approx(0.700000)
            assert payload["expected_opponent_ops"] == pytest.approx(0.650000)
            assert payload["ca_ops"] == pytest.approx(0.862345)
    finally:
        engine.dispose()


def test_unknown_player_returns_404() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            with _client_for_connection(connection) as client:
                response = client.get(
                    "/players/9000000002/season-ca-ops",
                    params={"season_id": 1},
                )

            assert response.status_code == 404
            assert response.json() == {"detail": "Player not found"}
    finally:
        engine.dispose()


def test_existing_player_without_season_ca_ops_returns_null_statistics() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888098202, "Pat Empty CA")
            season_id = _insert_season(connection, 2902)

            with _client_for_connection(connection) as client:
                response = client.get(
                    f"/players/{player_id}/season-ca-ops",
                    params={"season_id": season_id},
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["player_id"] == player_id
            assert payload["full_name"] == "Pat Empty CA"
            assert payload["season_id"] == season_id
            assert payload["season_year"] == 2902
            assert payload["plate_appearances"] is None
            assert payload["observed_ops"] is None
            assert payload["league_ops"] is None
            assert payload["expected_opponent_ops"] is None
            assert payload["ca_ops"] is None
    finally:
        engine.dispose()


def test_null_ca_ops_components_remain_null() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888098203, "Ada Null CA")
            season_id = _insert_season(connection, 2903)
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
                    f"/players/{player_id}/season-ca-ops",
                    params={"season_id": season_id},
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["plate_appearances"] == 0
            assert payload["observed_ops"] is None
            assert payload["league_ops"] is None
            assert payload["expected_opponent_ops"] is None
            assert payload["ca_ops"] is None
    finally:
        engine.dispose()


def test_requested_season_id_is_respected() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888098204, "Ada Two Seasons")
            first_season_id = _insert_season(connection, 2904)
            second_season_id = _insert_season(connection, 2905)
            _insert_player_season_ca_ops(
                connection,
                player_id=player_id,
                season_id=first_season_id,
                plate_appearances=10,
                observed_ops=0.800000,
                league_ops=0.710000,
                expected_opponent_ops=0.690000,
                ca_ops=0.820000,
            )
            _insert_player_season_ca_ops(
                connection,
                player_id=player_id,
                season_id=second_season_id,
                plate_appearances=20,
                observed_ops=0.900000,
                league_ops=0.720000,
                expected_opponent_ops=0.740000,
                ca_ops=0.880000,
            )

            with _client_for_connection(connection) as client:
                response = client.get(
                    f"/players/{player_id}/season-ca-ops",
                    params={"season_id": first_season_id},
                )

            assert response.status_code == 200
            payload = response.json()
            assert payload["season_id"] == first_season_id
            assert payload["season_year"] == 2904
            assert payload["plate_appearances"] == 10
            assert payload["observed_ops"] == pytest.approx(0.800000)
            assert payload["ca_ops"] == pytest.approx(0.820000)
            assert payload["plate_appearances"] != 20
            assert payload["ca_ops"] != pytest.approx(0.880000)
    finally:
        engine.dispose()


def test_season_ca_ops_does_not_manage_transactions() -> None:
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            player_id = _insert_player(connection, 888098205, "Ada Readonly CA")
            season_id = _insert_season(connection, 2906)
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
                    f"/players/{player_id}/season-ca-ops",
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
                    "/players/0/season-ca-ops",
                    params={"season_id": 1},
                )
                invalid_season = client.get(
                    "/players/1/season-ca-ops",
                    params={"season_id": 0},
                )
                missing_season = client.get("/players/1/season-ca-ops")

            assert invalid_player.status_code == 422
            assert invalid_season.status_code == 422
            assert missing_season.status_code == 422
    finally:
        engine.dispose()
