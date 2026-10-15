"""Tests for curated.player upserts."""

from contextlib import contextmanager
from unittest.mock import MagicMock

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from tests.db import create_test_engine
from app.curated.player_data import load_mlb_players
from app.mlb.stats_api import MlbPlayer


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


def _fetch_player(connection: Connection, mlb_player_id: int):
    return connection.execute(
        text(
            """
            SELECT player_id, mlb_player_id, full_name
            FROM curated.player
            WHERE mlb_player_id = :mlb_player_id
            """
        ),
        {"mlb_player_id": mlb_player_id},
    ).mappings().one()


def _count_players(connection: Connection, mlb_player_ids: list[int]) -> int:
    return connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM curated.player
            WHERE mlb_player_id = ANY(:mlb_player_ids)
            """
        ),
        {"mlb_player_ids": mlb_player_ids},
    ).scalar_one()


def test_empty_input_returns_zero_and_does_not_insert():
    connection = MagicMock()

    result = load_mlb_players(connection, [])

    assert result == 0
    connection.execute.assert_not_called()


def test_new_player_is_inserted():
    engine = _create_engine()
    mlb_player_id = 888004101

    try:
        with _isolated_connection(engine) as connection:
            result = load_mlb_players(
                connection,
                [MlbPlayer(mlb_player_id=mlb_player_id, full_name="Ada Batter")],
            )

            assert result == 1
            player = _fetch_player(connection, mlb_player_id)
            assert player["mlb_player_id"] == mlb_player_id
            assert player["full_name"] == "Ada Batter"
            assert player["player_id"] is not None
    finally:
        engine.dispose()


def test_multiple_players_can_be_inserted():
    engine = _create_engine()
    first_id = 888004201
    second_id = 888004202

    try:
        with _isolated_connection(engine) as connection:
            result = load_mlb_players(
                connection,
                [
                    MlbPlayer(mlb_player_id=first_id, full_name="Ada Batter"),
                    MlbPlayer(mlb_player_id=second_id, full_name="Pat Pitcher"),
                ],
            )

            assert result == 2
            assert _count_players(connection, [first_id, second_id]) == 2
            assert _fetch_player(connection, first_id)["full_name"] == "Ada Batter"
            assert _fetch_player(connection, second_id)["full_name"] == "Pat Pitcher"
    finally:
        engine.dispose()


def test_existing_mlb_player_id_updates_full_name():
    engine = _create_engine()
    mlb_player_id = 888004301

    try:
        with _isolated_connection(engine) as connection:
            load_mlb_players(
                connection,
                [MlbPlayer(mlb_player_id=mlb_player_id, full_name="Ada Batter")],
            )
            result = load_mlb_players(
                connection,
                [MlbPlayer(mlb_player_id=mlb_player_id, full_name="Ada Batter Jr.")],
            )

            assert result == 1
            player = _fetch_player(connection, mlb_player_id)
            assert player["full_name"] == "Ada Batter Jr."
    finally:
        engine.dispose()


def test_player_id_is_preserved_when_name_is_updated():
    engine = _create_engine()
    mlb_player_id = 888004401

    try:
        with _isolated_connection(engine) as connection:
            load_mlb_players(
                connection,
                [MlbPlayer(mlb_player_id=mlb_player_id, full_name="Ada Batter")],
            )
            original = _fetch_player(connection, mlb_player_id)

            load_mlb_players(
                connection,
                [MlbPlayer(mlb_player_id=mlb_player_id, full_name="Ada Batter Jr.")],
            )
            updated = _fetch_player(connection, mlb_player_id)

            assert updated["player_id"] == original["player_id"]
            assert updated["mlb_player_id"] == mlb_player_id
            assert updated["full_name"] == "Ada Batter Jr."
    finally:
        engine.dispose()


def test_duplicate_mlb_player_ids_in_input_do_not_cause_an_error():
    engine = _create_engine()
    mlb_player_id = 888004501

    try:
        with _isolated_connection(engine) as connection:
            result = load_mlb_players(
                connection,
                [
                    MlbPlayer(mlb_player_id=mlb_player_id, full_name="Ada Batter"),
                    MlbPlayer(mlb_player_id=mlb_player_id, full_name="Ada Batter Jr."),
                ],
            )

            assert result == 2
            player = _fetch_player(connection, mlb_player_id)
            assert player["full_name"] == "Ada Batter Jr."
            assert _count_players(connection, [mlb_player_id]) == 1
    finally:
        engine.dispose()
