"""Tests for curated.game_player upserts."""

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from tests.db import create_test_engine
from app.curated.game_player_data import (
    GamePlayerLoadResult,
    _GAME_PLAYER_INSERT_BATCH_SIZE,
    load_game_players,
)
from app.curated.statcast_game_player_data import StatcastGamePlayer


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


def _fetch_game_player(
    connection: Connection,
    game_id: int,
    player_id: int,
    team_id: int,
):
    return connection.execute(
        text(
            """
            SELECT game_player_id, game_id, player_id, team_id
            FROM curated.game_player
            WHERE game_id = :game_id
              AND player_id = :player_id
              AND team_id = :team_id
            """
        ),
        {"game_id": game_id, "player_id": player_id, "team_id": team_id},
    ).mappings().one()


def _count_game_players(connection: Connection, game_ids: list[int]) -> int:
    return connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM curated.game_player
            WHERE game_id = ANY(:game_ids)
            """
        ),
        {"game_ids": game_ids},
    ).scalar_one()


def test_empty_input_returns_zero_counts():
    connection = MagicMock()

    result = load_game_players(connection, [])

    assert result == GamePlayerLoadResult(
        game_players_supplied=0,
        game_players_loaded=0,
    )
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_single_game_player_is_inserted():
    engine = _create_engine()
    mlb_game_pk = 900000601

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2069)
            game_type_id = _insert_game_type(connection, "XA", "Xi Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2069, 4, 8),
            )
            player_id = _insert_player(connection, 888006101, "Ada Batter")
            team_id = _insert_team(connection, "ZPA", "Zeta Aces")

            result = load_game_players(
                connection,
                [
                    StatcastGamePlayer(
                        mlb_game_pk=mlb_game_pk,
                        player_id=888006101,
                        team_code="ZPA",
                    )
                ],
            )

            assert result == GamePlayerLoadResult(
                game_players_supplied=1,
                game_players_loaded=1,
            )
            game_player = _fetch_game_player(connection, game_id, player_id, team_id)
            assert game_player["game_id"] == game_id
            assert game_player["player_id"] == player_id
            assert game_player["team_id"] == team_id
            assert game_player["game_player_id"] is not None
    finally:
        engine.dispose()


def test_multiple_game_players_are_inserted():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2068)
            game_type_id = _insert_game_type(connection, "XB", "Xi Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=900000602,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2068, 4, 8),
            )
            first_player_id = _insert_player(connection, 888006102, "Ada Batter")
            second_player_id = _insert_player(connection, 888006103, "Pat Pitcher")
            team_id = _insert_team(connection, "ZPB", "Zeta Bats")

            result = load_game_players(
                connection,
                [
                    StatcastGamePlayer(
                        mlb_game_pk=900000602,
                        player_id=888006102,
                        team_code="ZPB",
                    ),
                    StatcastGamePlayer(
                        mlb_game_pk=900000602,
                        player_id=888006103,
                        team_code="ZPB",
                    ),
                ],
            )

            assert result == GamePlayerLoadResult(
                game_players_supplied=2,
                game_players_loaded=2,
            )
            assert _count_game_players(connection, [game_id]) == 2
            first = _fetch_game_player(connection, game_id, first_player_id, team_id)
            second = _fetch_game_player(connection, game_id, second_player_id, team_id)
            assert first["player_id"] == first_player_id
            assert second["player_id"] == second_player_id
    finally:
        engine.dispose()


def test_duplicate_supplied_relationships_are_deduplicated():
    engine = _create_engine()
    mlb_game_pk = 900000603

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2067)
            game_type_id = _insert_game_type(connection, "XC", "Xi Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2067, 4, 8),
            )
            player_id = _insert_player(connection, 888006104, "Ada Batter")
            team_id = _insert_team(connection, "ZPC", "Zeta Cats")

            result = load_game_players(
                connection,
                [
                    StatcastGamePlayer(
                        mlb_game_pk=mlb_game_pk,
                        player_id=888006104,
                        team_code="ZPC",
                    ),
                    StatcastGamePlayer(
                        mlb_game_pk=mlb_game_pk,
                        player_id=888006104,
                        team_code="ZPC",
                    ),
                ],
            )

            assert result == GamePlayerLoadResult(
                game_players_supplied=2,
                game_players_loaded=2,
            )
            assert _count_game_players(connection, [game_id]) == 1
            game_player = _fetch_game_player(connection, game_id, player_id, team_id)
            assert game_player["player_id"] == player_id
    finally:
        engine.dispose()


def test_existing_game_player_id_is_preserved_when_reloaded():
    engine = _create_engine()
    mlb_game_pk = 900000604

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2066)
            game_type_id = _insert_game_type(connection, "XD", "Xi Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2066, 4, 8),
            )
            player_id = _insert_player(connection, 888006105, "Ada Batter")
            team_id = _insert_team(connection, "ZPD", "Zeta Dogs")

            load_game_players(
                connection,
                [
                    StatcastGamePlayer(
                        mlb_game_pk=mlb_game_pk,
                        player_id=888006105,
                        team_code="ZPD",
                    )
                ],
            )
            original = _fetch_game_player(connection, game_id, player_id, team_id)

            result = load_game_players(
                connection,
                [
                    StatcastGamePlayer(
                        mlb_game_pk=mlb_game_pk,
                        player_id=888006105,
                        team_code="ZPD",
                    )
                ],
            )
            updated = _fetch_game_player(connection, game_id, player_id, team_id)

            assert result == GamePlayerLoadResult(
                game_players_supplied=1,
                game_players_loaded=1,
            )
            assert updated["game_player_id"] == original["game_player_id"]
            assert updated["game_id"] == game_id
            assert updated["player_id"] == player_id
            assert updated["team_id"] == team_id
            assert _count_game_players(connection, [game_id]) == 1
    finally:
        engine.dispose()


def test_missing_game_raises_value_error_and_inserts_nothing():
    engine = _create_engine()
    missing_game_pk = 900000606

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2065)
            game_type_id = _insert_game_type(connection, "XE", "Xi Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=900000605,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2065, 4, 8),
            )
            _insert_player(connection, 888006106, "Ada Batter")
            _insert_team(connection, "ZPE", "Zeta Eagles")

            with pytest.raises(ValueError, match=str(missing_game_pk)):
                load_game_players(
                    connection,
                    [
                        StatcastGamePlayer(
                            mlb_game_pk=900000605,
                            player_id=888006106,
                            team_code="ZPE",
                        ),
                        StatcastGamePlayer(
                            mlb_game_pk=missing_game_pk,
                            player_id=888006106,
                            team_code="ZPE",
                        ),
                    ],
                )

            assert _count_game_players(connection, [game_id]) == 0
    finally:
        engine.dispose()


def test_missing_player_raises_value_error_and_inserts_nothing():
    engine = _create_engine()
    mlb_game_pk = 900000607

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2064)
            game_type_id = _insert_game_type(connection, "XF", "Xi Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2064, 4, 8),
            )
            _insert_player(connection, 888006107, "Ada Batter")
            _insert_team(connection, "ZPF", "Zeta Foxes")

            with pytest.raises(ValueError, match="888006999"):
                load_game_players(
                    connection,
                    [
                        StatcastGamePlayer(
                            mlb_game_pk=mlb_game_pk,
                            player_id=888006107,
                            team_code="ZPF",
                        ),
                        StatcastGamePlayer(
                            mlb_game_pk=mlb_game_pk,
                            player_id=888006999,
                            team_code="ZPF",
                        ),
                    ],
                )

            assert _count_game_players(connection, [game_id]) == 0
    finally:
        engine.dispose()


def test_missing_team_raises_value_error_and_inserts_nothing():
    engine = _create_engine()
    mlb_game_pk = 900000608

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2063)
            game_type_id = _insert_game_type(connection, "XG", "Xi Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2063, 4, 8),
            )
            _insert_player(connection, 888006108, "Ada Batter")
            _insert_team(connection, "ZPG", "Zeta Giants")

            with pytest.raises(ValueError, match="MISSING_TEAM"):
                load_game_players(
                    connection,
                    [
                        StatcastGamePlayer(
                            mlb_game_pk=mlb_game_pk,
                            player_id=888006108,
                            team_code="ZPG",
                        ),
                        StatcastGamePlayer(
                            mlb_game_pk=mlb_game_pk,
                            player_id=888006108,
                            team_code="MISSING_TEAM",
                        ),
                    ],
                )

            assert _count_game_players(connection, [game_id]) == 0
    finally:
        engine.dispose()


def test_game_player_load_result_counts_include_duplicates():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2062)
            game_type_id = _insert_game_type(connection, "XH", "Xi Regular")
            first_game_id = _insert_game(
                connection,
                mlb_game_pk=900000609,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2062, 4, 8),
            )
            second_game_id = _insert_game(
                connection,
                mlb_game_pk=900000610,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2062, 4, 9),
            )
            first_player_id = _insert_player(connection, 888006109, "Ada Batter")
            second_player_id = _insert_player(connection, 888006110, "Pat Pitcher")
            first_team_id = _insert_team(connection, "ZPH", "Zeta Hawks")
            second_team_id = _insert_team(connection, "ZPI", "Zeta Irons")

            result = load_game_players(
                connection,
                [
                    StatcastGamePlayer(
                        mlb_game_pk=900000609,
                        player_id=888006109,
                        team_code="ZPH",
                    ),
                    StatcastGamePlayer(
                        mlb_game_pk=900000610,
                        player_id=888006110,
                        team_code="ZPI",
                    ),
                    StatcastGamePlayer(
                        mlb_game_pk=900000609,
                        player_id=888006109,
                        team_code="ZPH",
                    ),
                ],
            )

            assert result == GamePlayerLoadResult(
                game_players_supplied=3,
                game_players_loaded=3,
            )
            assert _count_game_players(connection, [first_game_id, second_game_id]) == 2
            _fetch_game_player(connection, first_game_id, first_player_id, first_team_id)
            _fetch_game_player(
                connection, second_game_id, second_player_id, second_team_id
            )
    finally:
        engine.dispose()


def test_successful_load_does_not_commit_or_rollback():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2061)
            game_type_id = _insert_game_type(connection, "XI", "Xi Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=900000611,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2061, 4, 8),
            )
            player_id = _insert_player(connection, 888006111, "Ada Batter")
            team_id = _insert_team(connection, "ZPJ", "Zeta Jays")
            connection.commit = MagicMock()
            connection.rollback = MagicMock()

            result = load_game_players(
                connection,
                [
                    StatcastGamePlayer(
                        mlb_game_pk=900000611,
                        player_id=888006111,
                        team_code="ZPJ",
                    )
                ],
            )

            assert result == GamePlayerLoadResult(
                game_players_supplied=1,
                game_players_loaded=1,
            )
            _fetch_game_player(connection, game_id, player_id, team_id)
            connection.commit.assert_not_called()
            connection.rollback.assert_not_called()
    finally:
        engine.dispose()


def _statcast_game_players(count: int) -> list[StatcastGamePlayer]:
    return [
        StatcastGamePlayer(
            mlb_game_pk=index,
            player_id=index,
            team_code="NYY",
        )
        for index in range(count)
    ]


def _patch_game_player_lookups(count: int):
    game_ids = {index: 1_000 + index for index in range(count)}
    player_ids = {index: 2_000 + index for index in range(count)}
    team_ids = {"NYY": 7}
    statement = MagicMock()
    statement.values.return_value = statement
    statement.on_conflict_do_update.return_value = statement
    return (
        patch(
            "app.curated.game_player_data._game_ids_by_mlb_game_pk",
            return_value=game_ids,
        ),
        patch(
            "app.curated.game_player_data._player_ids_by_mlb_player_id",
            return_value=player_ids,
        ),
        patch(
            "app.curated.game_player_data._team_ids_by_code",
            return_value=team_ids,
        ),
        patch(
            "app.curated.game_player_data._curated_table",
            return_value=MagicMock(),
        ),
        patch(
            "app.curated.game_player_data.insert",
            return_value=statement,
        ),
        statement,
    )


def test_fewer_than_500_rows_makes_one_database_write():
    connection = MagicMock()
    count = _GAME_PLAYER_INSERT_BATCH_SIZE - 1
    *patches, statement = _patch_game_player_lookups(count)

    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = load_game_players(connection, _statcast_game_players(count))

    statement.values.assert_called_once()
    assert len(statement.values.call_args.args[0]) == count
    connection.execute.assert_called_once_with(statement)
    assert result == GamePlayerLoadResult(
        game_players_supplied=count,
        game_players_loaded=count,
    )


def test_exactly_500_rows_makes_one_database_write():
    connection = MagicMock()
    count = _GAME_PLAYER_INSERT_BATCH_SIZE
    *patches, statement = _patch_game_player_lookups(count)

    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = load_game_players(connection, _statcast_game_players(count))

    statement.values.assert_called_once()
    assert len(statement.values.call_args.args[0]) == count
    connection.execute.assert_called_once_with(statement)
    assert result == GamePlayerLoadResult(
        game_players_supplied=count,
        game_players_loaded=count,
    )


def test_more_than_500_rows_makes_multiple_database_writes():
    connection = MagicMock()
    count = _GAME_PLAYER_INSERT_BATCH_SIZE + 1
    *patches, statement = _patch_game_player_lookups(count)

    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = load_game_players(connection, _statcast_game_players(count))

    assert statement.values.call_count == 2
    assert len(statement.values.call_args_list[0].args[0]) == (
        _GAME_PLAYER_INSERT_BATCH_SIZE
    )
    assert len(statement.values.call_args_list[1].args[0]) == 1
    assert connection.execute.call_count == 2
    assert result == GamePlayerLoadResult(
        game_players_supplied=count,
        game_players_loaded=count,
    )
