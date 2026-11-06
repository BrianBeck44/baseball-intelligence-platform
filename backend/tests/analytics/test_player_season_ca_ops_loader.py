"""Tests for analytics player-season CA-OPS persistence."""

from contextlib import contextmanager
from dataclasses import asdict
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.analytics.player_season_ca_ops_data import PlayerSeasonCaOps
from app.analytics.player_season_ca_ops_loader import load_player_season_ca_ops
from tests.db import create_test_engine


def _row(
    *,
    player_id: int = 1,
    season_id: int = 2024,
    plate_appearances: int = 4,
    observed_ops: float | None = 0.8,
    league_ops: float | None = 0.7,
    expected_opponent_ops: float | None = 0.65,
    ca_ops: float | None = 0.85,
) -> PlayerSeasonCaOps:
    return PlayerSeasonCaOps(
        player_id=player_id,
        season_id=season_id,
        plate_appearances=plate_appearances,
        observed_ops=observed_ops,
        league_ops=league_ops,
        expected_opponent_ops=expected_opponent_ops,
        ca_ops=ca_ops,
    )


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


def _seed_lookups(
    connection: Connection,
    *,
    player_mlb_id: int,
    season_year: int,
    extra_player_mlb_id: int | None = None,
    extra_season_year: int | None = None,
) -> dict[str, int]:
    ids = {
        "player_id": _insert_player(connection, player_mlb_id, "Ada Batter"),
        "season_id": _insert_season(connection, season_year),
    }
    if extra_player_mlb_id is not None:
        ids["extra_player_id"] = _insert_player(
            connection,
            extra_player_mlb_id,
            "Pat Pitcher",
        )
    if extra_season_year is not None:
        ids["extra_season_id"] = _insert_season(connection, extra_season_year)
    return ids


def _fetch(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
):
    return (
        connection.execute(
            text(
                """
                SELECT *
                FROM analytics.player_season_ca_ops
                WHERE player_id = :player_id
                  AND season_id = :season_id
                """
            ),
            {"player_id": player_id, "season_id": season_id},
        )
        .mappings()
        .one()
    )


def _count(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
) -> int:
    return int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM analytics.player_season_ca_ops
                WHERE player_id = :player_id
                  AND season_id = :season_id
                """
            ),
            {"player_id": player_id, "season_id": season_id},
        ).scalar_one()
    )


def _as_rate(value: object) -> float | None:
    return None if value is None else float(value)


def test_load_empty_input_returns_zero_and_does_not_execute():
    connection = MagicMock()

    result = load_player_season_ca_ops(connection, [])

    assert result == 0
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_load_inserts_a_single_row():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_lookups(
                connection,
                player_mlb_id=888093201,
                season_year=2633,
            )
            row = _row(
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )

            inserted = load_player_season_ca_ops(connection, [row])
            stored = _fetch(
                connection,
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )

            assert inserted == 1
            assert stored["player_id"] == ids["player_id"]
            assert stored["season_id"] == ids["season_id"]
            assert stored["plate_appearances"] == 4
            assert _as_rate(stored["observed_ops"]) == pytest.approx(0.8)
            assert _as_rate(stored["league_ops"]) == pytest.approx(0.7)
            assert _as_rate(stored["expected_opponent_ops"]) == pytest.approx(0.65)
            assert _as_rate(stored["ca_ops"]) == pytest.approx(0.85)
            assert stored["created_at"] is not None
    finally:
        engine.dispose()


def test_load_retains_row_when_ca_ops_is_null():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_lookups(
                connection,
                player_mlb_id=888093202,
                season_year=2634,
            )
            row = _row(
                player_id=ids["player_id"],
                season_id=ids["season_id"],
                plate_appearances=0,
                observed_ops=None,
                league_ops=None,
                expected_opponent_ops=None,
                ca_ops=None,
            )

            inserted = load_player_season_ca_ops(connection, [row])
            stored = _fetch(
                connection,
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )

            assert inserted == 1
            assert stored["plate_appearances"] == 0
            assert stored["observed_ops"] is None
            assert stored["league_ops"] is None
            assert stored["expected_opponent_ops"] is None
            assert stored["ca_ops"] is None
    finally:
        engine.dispose()


def test_rebuild_upserts_without_creating_duplicates():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_lookups(
                connection,
                player_mlb_id=888093203,
                season_year=2635,
            )
            original = _row(
                player_id=ids["player_id"],
                season_id=ids["season_id"],
                plate_appearances=4,
                observed_ops=0.8,
                league_ops=0.7,
                expected_opponent_ops=0.65,
                ca_ops=0.85,
            )
            refreshed = _row(
                player_id=ids["player_id"],
                season_id=ids["season_id"],
                plate_appearances=8,
                observed_ops=0.9,
                league_ops=0.72,
                expected_opponent_ops=0.7,
                ca_ops=0.92,
            )

            first = load_player_season_ca_ops(connection, [original])
            second = load_player_season_ca_ops(connection, [original])
            third = load_player_season_ca_ops(connection, [refreshed])
            stored = _fetch(
                connection,
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )

            assert first == 1
            assert second == 1
            assert third == 1
            assert (
                _count(
                    connection,
                    player_id=ids["player_id"],
                    season_id=ids["season_id"],
                )
                == 1
            )
            assert stored["plate_appearances"] == 8
            assert _as_rate(stored["ca_ops"]) == pytest.approx(0.92)
    finally:
        engine.dispose()


def test_load_does_not_supply_created_at():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_lookups(
                connection,
                player_mlb_id=888093204,
                season_year=2636,
            )
            row = _row(
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )
            payload = asdict(row)
            original_execute = connection.execute
            captured: list[object] = []

            def spy_execute(statement, *args, **kwargs):
                captured.append(statement)
                return original_execute(statement, *args, **kwargs)

            connection.execute = spy_execute
            try:
                inserted = load_player_season_ca_ops(connection, [row])
            finally:
                connection.execute = original_execute

            stored = _fetch(
                connection,
                player_id=ids["player_id"],
                season_id=ids["season_id"],
            )
            compiled = str(captured[-1].compile(dialect=connection.dialect))

            assert inserted == 1
            assert "created_at" not in payload
            assert "created_at" not in compiled
            assert stored["created_at"] is not None
    finally:
        engine.dispose()
