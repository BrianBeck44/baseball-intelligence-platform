"""Tests for curated.game upserts."""

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from tests.db import create_test_engine
from app.curated.game_data import GameLoadResult, load_games
from app.curated.statcast_game_data import StatcastGame


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


def _fetch_game(connection: Connection, mlb_game_pk: int):
    return connection.execute(
        text(
            """
            SELECT
                game_id,
                mlb_game_pk,
                season_id,
                official_game_date,
                game_type_id
            FROM curated.game
            WHERE mlb_game_pk = :mlb_game_pk
            """
        ),
        {"mlb_game_pk": mlb_game_pk},
    ).mappings().one()


def _count_games(connection: Connection, mlb_game_pks: list[int]) -> int:
    return connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM curated.game
            WHERE mlb_game_pk = ANY(:mlb_game_pks)
            """
        ),
        {"mlb_game_pks": mlb_game_pks},
    ).scalar_one()


def test_empty_input_returns_zero_counts():
    connection = MagicMock()

    result = load_games(connection, [])

    assert result == GameLoadResult(games_supplied=0, games_loaded=0)
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()


def test_single_game_is_inserted():
    engine = _create_engine()
    mlb_game_pk = 900000101

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2099)
            game_type_id = _insert_game_type(connection, "ZT", "Zeta Regular")

            result = load_games(
                connection,
                [
                    StatcastGame(
                        mlb_game_pk=mlb_game_pk,
                        official_game_date=date(2099, 4, 8),
                        game_type="ZT",
                    )
                ],
            )

            assert result == GameLoadResult(games_supplied=1, games_loaded=1)
            game = _fetch_game(connection, mlb_game_pk)
            assert game["mlb_game_pk"] == mlb_game_pk
            assert game["season_id"] == season_id
            assert game["official_game_date"] == date(2099, 4, 8)
            assert game["game_type_id"] == game_type_id
            assert game["game_id"] is not None
    finally:
        engine.dispose()


def test_multiple_games_are_inserted():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2098)
            game_type_id = _insert_game_type(connection, "ZU", "Zeta Regular")

            result = load_games(
                connection,
                [
                    StatcastGame(
                        mlb_game_pk=900000102,
                        official_game_date=date(2098, 4, 8),
                        game_type="ZU",
                    ),
                    StatcastGame(
                        mlb_game_pk=900000103,
                        official_game_date=date(2098, 4, 9),
                        game_type="ZU",
                    ),
                ],
            )

            assert result == GameLoadResult(games_supplied=2, games_loaded=2)
            assert _count_games(connection, [900000102, 900000103]) == 2
            first = _fetch_game(connection, 900000102)
            second = _fetch_game(connection, 900000103)
            assert first["season_id"] == season_id
            assert second["season_id"] == season_id
            assert first["game_type_id"] == game_type_id
            assert second["game_type_id"] == game_type_id
    finally:
        engine.dispose()


def test_duplicate_mlb_game_pks_use_last_supplied_record():
    engine = _create_engine()
    mlb_game_pk = 900000104

    try:
        with _isolated_connection(engine) as connection:
            first_season_id = _insert_season(connection, 2097)
            second_season_id = _insert_season(connection, 2096)
            first_type_id = _insert_game_type(connection, "ZV", "Zeta Regular")
            second_type_id = _insert_game_type(connection, "ZW", "Zeta Spring")

            result = load_games(
                connection,
                [
                    StatcastGame(
                        mlb_game_pk=mlb_game_pk,
                        official_game_date=date(2097, 4, 8),
                        game_type="ZV",
                    ),
                    StatcastGame(
                        mlb_game_pk=mlb_game_pk,
                        official_game_date=date(2096, 3, 15),
                        game_type="ZW",
                    ),
                ],
            )

            assert result == GameLoadResult(games_supplied=2, games_loaded=2)
            assert _count_games(connection, [mlb_game_pk]) == 1
            game = _fetch_game(connection, mlb_game_pk)
            assert game["season_id"] == second_season_id
            assert game["official_game_date"] == date(2096, 3, 15)
            assert game["game_type_id"] == second_type_id
            assert game["season_id"] != first_season_id
            assert game["game_type_id"] != first_type_id
    finally:
        engine.dispose()


def test_existing_game_id_is_preserved_when_reloaded():
    engine = _create_engine()
    mlb_game_pk = 900000105

    try:
        with _isolated_connection(engine) as connection:
            _insert_season(connection, 2095)
            _insert_game_type(connection, "ZX", "Zeta Regular")

            load_games(
                connection,
                [
                    StatcastGame(
                        mlb_game_pk=mlb_game_pk,
                        official_game_date=date(2095, 4, 8),
                        game_type="ZX",
                    )
                ],
            )
            original = _fetch_game(connection, mlb_game_pk)

            load_games(
                connection,
                [
                    StatcastGame(
                        mlb_game_pk=mlb_game_pk,
                        official_game_date=date(2095, 4, 9),
                        game_type="ZX",
                    )
                ],
            )
            updated = _fetch_game(connection, mlb_game_pk)

            assert updated["game_id"] == original["game_id"]
            assert updated["mlb_game_pk"] == mlb_game_pk
    finally:
        engine.dispose()


def test_existing_game_values_are_updated_on_conflict():
    engine = _create_engine()
    mlb_game_pk = 900000106

    try:
        with _isolated_connection(engine) as connection:
            first_season_id = _insert_season(connection, 2094)
            second_season_id = _insert_season(connection, 2093)
            first_type_id = _insert_game_type(connection, "ZY", "Zeta Regular")
            second_type_id = _insert_game_type(connection, "ZZ", "Zeta Spring")

            load_games(
                connection,
                [
                    StatcastGame(
                        mlb_game_pk=mlb_game_pk,
                        official_game_date=date(2094, 4, 8),
                        game_type="ZY",
                    )
                ],
            )
            original = _fetch_game(connection, mlb_game_pk)
            assert original["season_id"] == first_season_id
            assert original["game_type_id"] == first_type_id

            result = load_games(
                connection,
                [
                    StatcastGame(
                        mlb_game_pk=mlb_game_pk,
                        official_game_date=date(2093, 3, 20),
                        game_type="ZZ",
                    )
                ],
            )

            assert result == GameLoadResult(games_supplied=1, games_loaded=1)
            updated = _fetch_game(connection, mlb_game_pk)
            assert updated["game_id"] == original["game_id"]
            assert updated["season_id"] == second_season_id
            assert updated["official_game_date"] == date(2093, 3, 20)
            assert updated["game_type_id"] == second_type_id
    finally:
        engine.dispose()


def test_missing_season_raises_value_error():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _insert_game_type(connection, "ZA", "Zeta Regular")

            with pytest.raises(ValueError, match="2088"):
                load_games(
                    connection,
                    [
                        StatcastGame(
                            mlb_game_pk=900000107,
                            official_game_date=date(2088, 4, 8),
                            game_type="ZA",
                        )
                    ],
                )
    finally:
        engine.dispose()


def test_missing_game_type_raises_value_error():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _insert_season(connection, 2087)

            with pytest.raises(ValueError, match="MISSING_TYPE"):
                load_games(
                    connection,
                    [
                        StatcastGame(
                            mlb_game_pk=900000108,
                            official_game_date=date(2087, 4, 8),
                            game_type="MISSING_TYPE",
                        )
                    ],
                )
    finally:
        engine.dispose()


def test_multiple_games_resolve_seasons_and_game_types():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_2092 = _insert_season(connection, 2092)
            season_2091 = _insert_season(connection, 2091)
            regular_id = _insert_game_type(connection, "ZR", "Zeta Regular")
            spring_id = _insert_game_type(connection, "ZS", "Zeta Spring")

            result = load_games(
                connection,
                [
                    StatcastGame(
                        mlb_game_pk=900000109,
                        official_game_date=date(2092, 4, 8),
                        game_type="ZR",
                    ),
                    StatcastGame(
                        mlb_game_pk=900000110,
                        official_game_date=date(2091, 3, 12),
                        game_type="ZS",
                    ),
                ],
            )

            assert result == GameLoadResult(games_supplied=2, games_loaded=2)
            first = _fetch_game(connection, 900000109)
            second = _fetch_game(connection, 900000110)
            assert first["season_id"] == season_2092
            assert first["game_type_id"] == regular_id
            assert second["season_id"] == season_2091
            assert second["game_type_id"] == spring_id
    finally:
        engine.dispose()


def test_missing_season_does_not_insert_game():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _insert_game_type(connection, "ZT", "Zeta Regular")

            with pytest.raises(ValueError, match="2086"):
                load_games(
                    connection,
                    [
                        StatcastGame(
                            mlb_game_pk=900000111,
                            official_game_date=date(2086, 4, 8),
                            game_type="ZT",
                        )
                    ],
                )

            assert _count_games(connection, [900000111]) == 0
    finally:
        engine.dispose()


def test_missing_game_type_does_not_insert_game():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _insert_season(connection, 2085)

            with pytest.raises(ValueError, match="MISSING_TYPE"):
                load_games(
                    connection,
                    [
                        StatcastGame(
                            mlb_game_pk=900000112,
                            official_game_date=date(2085, 4, 8),
                            game_type="MISSING_TYPE",
                        )
                    ],
                )

            assert _count_games(connection, [900000112]) == 0
    finally:
        engine.dispose()
