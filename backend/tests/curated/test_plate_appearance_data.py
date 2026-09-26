"""Tests for curated.plate_appearance upserts."""

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.curated.plate_appearance_data import (
    PlateAppearanceLoadResult,
    load_plate_appearances,
)
from app.curated.statcast_plate_appearance_data import StatcastPlateAppearance


def _create_engine() -> Engine:
    return create_engine(settings.database_url)


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


def _insert_outcome_type(connection: Connection, code: str, name: str) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.outcome_type (code, name)
            VALUES (:code, :name)
            RETURNING id
            """
        ),
        {"code": code, "name": name},
    ).scalar_one()


def _fetch_plate_appearance(
    connection: Connection,
    game_id: int,
    at_bat_number: int,
):
    return connection.execute(
        text(
            """
            SELECT
                plate_appearance_id,
                game_id,
                at_bat_number,
                batter_id,
                pitcher_id,
                batter_team_id,
                pitcher_team_id,
                inning,
                inning_topbot,
                outcome_type_id
            FROM curated.plate_appearance
            WHERE game_id = :game_id
              AND at_bat_number = :at_bat_number
            """
        ),
        {"game_id": game_id, "at_bat_number": at_bat_number},
    ).mappings().one()


def _count_plate_appearances(connection: Connection, game_ids: list[int]) -> int:
    return connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM curated.plate_appearance
            WHERE game_id = ANY(:game_ids)
            """
        ),
        {"game_ids": game_ids},
    ).scalar_one()


def test_empty_input_returns_zero_counts():
    connection = MagicMock()

    result = load_plate_appearances(connection, [])

    assert result == PlateAppearanceLoadResult(
        plate_appearances_supplied=0,
        plate_appearances_loaded=0,
    )
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_single_plate_appearance_is_inserted():
    engine = _create_engine()
    mlb_game_pk = 900000901

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2059)
            game_type_id = _insert_game_type(connection, "QA", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2059, 4, 8),
            )
            batter_id = _insert_player(connection, 888009101, "Ada Batter")
            pitcher_id = _insert_player(connection, 888009102, "Pat Pitcher")
            batter_team_id = _insert_team(connection, "ZQA", "Zeta Aces")
            pitcher_team_id = _insert_team(connection, "ZQB", "Zeta Bats")
            outcome_type_id = _insert_outcome_type(connection, "ZPA_SINGLE", "Single")

            result = load_plate_appearances(
                connection,
                [
                    StatcastPlateAppearance(
                        mlb_game_pk=mlb_game_pk,
                        at_bat_number=1,
                        batter_id=888009101,
                        pitcher_id=888009102,
                        batter_team_code="ZQA",
                        pitcher_team_code="ZQB",
                        inning=1,
                        inning_topbot="Top",
                        outcome_code="ZPA_SINGLE",
                    )
                ],
            )

            assert result == PlateAppearanceLoadResult(
                plate_appearances_supplied=1,
                plate_appearances_loaded=1,
            )
            plate_appearance = _fetch_plate_appearance(connection, game_id, 1)
            assert plate_appearance["game_id"] == game_id
            assert plate_appearance["at_bat_number"] == 1
            assert plate_appearance["batter_id"] == batter_id
            assert plate_appearance["pitcher_id"] == pitcher_id
            assert plate_appearance["batter_team_id"] == batter_team_id
            assert plate_appearance["pitcher_team_id"] == pitcher_team_id
            assert plate_appearance["inning"] == 1
            assert plate_appearance["inning_topbot"] == "Top"
            assert plate_appearance["outcome_type_id"] == outcome_type_id
            assert plate_appearance["plate_appearance_id"] is not None
    finally:
        engine.dispose()


def test_multiple_plate_appearances_are_inserted():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2058)
            game_type_id = _insert_game_type(connection, "QB", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=900000902,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2058, 4, 8),
            )
            batter_id = _insert_player(connection, 888009103, "Ada Batter")
            pitcher_id = _insert_player(connection, 888009104, "Pat Pitcher")
            batter_team_id = _insert_team(connection, "ZQC", "Zeta Cats")
            pitcher_team_id = _insert_team(connection, "ZQD", "Zeta Dogs")

            result = load_plate_appearances(
                connection,
                [
                    StatcastPlateAppearance(
                        mlb_game_pk=900000902,
                        at_bat_number=1,
                        batter_id=888009103,
                        pitcher_id=888009104,
                        batter_team_code="ZQC",
                        pitcher_team_code="ZQD",
                        inning=1,
                        inning_topbot="Top",
                        outcome_code=None,
                    ),
                    StatcastPlateAppearance(
                        mlb_game_pk=900000902,
                        at_bat_number=2,
                        batter_id=888009103,
                        pitcher_id=888009104,
                        batter_team_code="ZQD",
                        pitcher_team_code="ZQC",
                        inning=1,
                        inning_topbot="Bot",
                        outcome_code=None,
                    ),
                ],
            )

            assert result == PlateAppearanceLoadResult(
                plate_appearances_supplied=2,
                plate_appearances_loaded=2,
            )
            assert _count_plate_appearances(connection, [game_id]) == 2
            first = _fetch_plate_appearance(connection, game_id, 1)
            second = _fetch_plate_appearance(connection, game_id, 2)
            assert first["batter_id"] == batter_id
            assert first["pitcher_id"] == pitcher_id
            assert first["batter_team_id"] == batter_team_id
            assert first["pitcher_team_id"] == pitcher_team_id
            assert second["batter_team_id"] == pitcher_team_id
            assert second["pitcher_team_id"] == batter_team_id
            assert second["inning_topbot"] == "Bot"
    finally:
        engine.dispose()


def test_duplicate_supplied_natural_keys_use_last_record():
    engine = _create_engine()
    mlb_game_pk = 900000903

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2057)
            game_type_id = _insert_game_type(connection, "QC", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2057, 4, 8),
            )
            first_batter_id = _insert_player(connection, 888009105, "Ada Batter")
            second_batter_id = _insert_player(connection, 888009106, "Bea Batter")
            pitcher_id = _insert_player(connection, 888009107, "Pat Pitcher")
            batter_team_id = _insert_team(connection, "ZQE", "Zeta Eagles")
            pitcher_team_id = _insert_team(connection, "ZQF", "Zeta Foxes")
            first_outcome_id = _insert_outcome_type(connection, "ZPA_WALK", "Walk")
            second_outcome_id = _insert_outcome_type(connection, "ZPA_HR", "Home Run")

            result = load_plate_appearances(
                connection,
                [
                    StatcastPlateAppearance(
                        mlb_game_pk=mlb_game_pk,
                        at_bat_number=1,
                        batter_id=888009105,
                        pitcher_id=888009107,
                        batter_team_code="ZQE",
                        pitcher_team_code="ZQF",
                        inning=1,
                        inning_topbot="Top",
                        outcome_code="ZPA_WALK",
                    ),
                    StatcastPlateAppearance(
                        mlb_game_pk=mlb_game_pk,
                        at_bat_number=1,
                        batter_id=888009106,
                        pitcher_id=888009107,
                        batter_team_code="ZQE",
                        pitcher_team_code="ZQF",
                        inning=3,
                        inning_topbot="Bot",
                        outcome_code="ZPA_HR",
                    ),
                ],
            )

            assert result == PlateAppearanceLoadResult(
                plate_appearances_supplied=2,
                plate_appearances_loaded=2,
            )
            assert _count_plate_appearances(connection, [game_id]) == 1
            plate_appearance = _fetch_plate_appearance(connection, game_id, 1)
            assert plate_appearance["batter_id"] == second_batter_id
            assert plate_appearance["batter_id"] != first_batter_id
            assert plate_appearance["pitcher_id"] == pitcher_id
            assert plate_appearance["batter_team_id"] == batter_team_id
            assert plate_appearance["pitcher_team_id"] == pitcher_team_id
            assert plate_appearance["inning"] == 3
            assert plate_appearance["inning_topbot"] == "Bot"
            assert plate_appearance["outcome_type_id"] == second_outcome_id
            assert plate_appearance["outcome_type_id"] != first_outcome_id
    finally:
        engine.dispose()


def test_load_result_counts_include_duplicates():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2056)
            game_type_id = _insert_game_type(connection, "QD", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=900000904,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2056, 4, 8),
            )
            _insert_player(connection, 888009108, "Ada Batter")
            _insert_player(connection, 888009109, "Pat Pitcher")
            _insert_team(connection, "ZQG", "Zeta Giants")
            _insert_team(connection, "ZQH", "Zeta Hawks")

            result = load_plate_appearances(
                connection,
                [
                    StatcastPlateAppearance(
                        mlb_game_pk=900000904,
                        at_bat_number=1,
                        batter_id=888009108,
                        pitcher_id=888009109,
                        batter_team_code="ZQG",
                        pitcher_team_code="ZQH",
                        inning=1,
                        inning_topbot="Top",
                        outcome_code=None,
                    ),
                    StatcastPlateAppearance(
                        mlb_game_pk=900000904,
                        at_bat_number=2,
                        batter_id=888009108,
                        pitcher_id=888009109,
                        batter_team_code="ZQG",
                        pitcher_team_code="ZQH",
                        inning=1,
                        inning_topbot="Top",
                        outcome_code=None,
                    ),
                    StatcastPlateAppearance(
                        mlb_game_pk=900000904,
                        at_bat_number=1,
                        batter_id=888009108,
                        pitcher_id=888009109,
                        batter_team_code="ZQG",
                        pitcher_team_code="ZQH",
                        inning=2,
                        inning_topbot="Top",
                        outcome_code=None,
                    ),
                ],
            )

            assert result == PlateAppearanceLoadResult(
                plate_appearances_supplied=3,
                plate_appearances_loaded=3,
            )
            assert _count_plate_appearances(connection, [game_id]) == 2
            assert _fetch_plate_appearance(connection, game_id, 1)["inning"] == 2
    finally:
        engine.dispose()


def test_existing_plate_appearance_id_is_preserved_when_reloaded():
    engine = _create_engine()
    mlb_game_pk = 900000905

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2055)
            game_type_id = _insert_game_type(connection, "QE", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2055, 4, 8),
            )
            _insert_player(connection, 888009110, "Ada Batter")
            _insert_player(connection, 888009111, "Pat Pitcher")
            _insert_team(connection, "ZQI", "Zeta Irons")
            _insert_team(connection, "ZQJ", "Zeta Jays")

            load_plate_appearances(
                connection,
                [
                    StatcastPlateAppearance(
                        mlb_game_pk=mlb_game_pk,
                        at_bat_number=1,
                        batter_id=888009110,
                        pitcher_id=888009111,
                        batter_team_code="ZQI",
                        pitcher_team_code="ZQJ",
                        inning=1,
                        inning_topbot="Top",
                        outcome_code=None,
                    )
                ],
            )
            original = _fetch_plate_appearance(connection, game_id, 1)

            result = load_plate_appearances(
                connection,
                [
                    StatcastPlateAppearance(
                        mlb_game_pk=mlb_game_pk,
                        at_bat_number=1,
                        batter_id=888009110,
                        pitcher_id=888009111,
                        batter_team_code="ZQI",
                        pitcher_team_code="ZQJ",
                        inning=4,
                        inning_topbot="Bot",
                        outcome_code=None,
                    )
                ],
            )
            updated = _fetch_plate_appearance(connection, game_id, 1)

            assert result == PlateAppearanceLoadResult(
                plate_appearances_supplied=1,
                plate_appearances_loaded=1,
            )
            assert updated["plate_appearance_id"] == original["plate_appearance_id"]
            assert updated["game_id"] == game_id
            assert updated["at_bat_number"] == 1
            assert _count_plate_appearances(connection, [game_id]) == 1
    finally:
        engine.dispose()


def test_existing_row_is_updated_on_natural_key_conflict():
    engine = _create_engine()
    mlb_game_pk = 900000906

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2054)
            game_type_id = _insert_game_type(connection, "QF", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2054, 4, 8),
            )
            first_batter_id = _insert_player(connection, 888009112, "Ada Batter")
            second_batter_id = _insert_player(connection, 888009113, "Bea Batter")
            first_pitcher_id = _insert_player(connection, 888009114, "Pat Pitcher")
            second_pitcher_id = _insert_player(connection, 888009115, "Quinn Pitcher")
            first_batter_team_id = _insert_team(connection, "ZQK", "Zeta Kings")
            second_batter_team_id = _insert_team(connection, "ZQL", "Zeta Lions")
            first_pitcher_team_id = _insert_team(connection, "ZQM", "Zeta Moose")
            second_pitcher_team_id = _insert_team(connection, "ZQN", "Zeta Nuts")
            first_outcome_id = _insert_outcome_type(connection, "ZPA_OUT", "Out")
            second_outcome_id = _insert_outcome_type(connection, "ZPA_HIT", "Hit")

            load_plate_appearances(
                connection,
                [
                    StatcastPlateAppearance(
                        mlb_game_pk=mlb_game_pk,
                        at_bat_number=1,
                        batter_id=888009112,
                        pitcher_id=888009114,
                        batter_team_code="ZQK",
                        pitcher_team_code="ZQM",
                        inning=1,
                        inning_topbot="Top",
                        outcome_code="ZPA_OUT",
                    )
                ],
            )
            original = _fetch_plate_appearance(connection, game_id, 1)
            assert original["batter_id"] == first_batter_id
            assert original["pitcher_id"] == first_pitcher_id
            assert original["batter_team_id"] == first_batter_team_id
            assert original["pitcher_team_id"] == first_pitcher_team_id
            assert original["outcome_type_id"] == first_outcome_id

            result = load_plate_appearances(
                connection,
                [
                    StatcastPlateAppearance(
                        mlb_game_pk=mlb_game_pk,
                        at_bat_number=1,
                        batter_id=888009113,
                        pitcher_id=888009115,
                        batter_team_code="ZQL",
                        pitcher_team_code="ZQN",
                        inning=7,
                        inning_topbot="Bot",
                        outcome_code="ZPA_HIT",
                    )
                ],
            )
            updated = _fetch_plate_appearance(connection, game_id, 1)

            assert result == PlateAppearanceLoadResult(
                plate_appearances_supplied=1,
                plate_appearances_loaded=1,
            )
            assert updated["plate_appearance_id"] == original["plate_appearance_id"]
            assert updated["batter_id"] == second_batter_id
            assert updated["pitcher_id"] == second_pitcher_id
            assert updated["batter_team_id"] == second_batter_team_id
            assert updated["pitcher_team_id"] == second_pitcher_team_id
            assert updated["inning"] == 7
            assert updated["inning_topbot"] == "Bot"
            assert updated["outcome_type_id"] == second_outcome_id
    finally:
        engine.dispose()


def test_missing_game_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900000907

    try:
        with _isolated_connection(engine) as connection:
            _insert_player(connection, 888009116, "Ada Batter")
            _insert_player(connection, 888009117, "Pat Pitcher")
            _insert_team(connection, "ZQO", "Zeta Otters")
            _insert_team(connection, "ZQP", "Zeta Pumas")

            with pytest.raises(ValueError, match=str(mlb_game_pk)):
                load_plate_appearances(
                    connection,
                    [
                        StatcastPlateAppearance(
                            mlb_game_pk=mlb_game_pk,
                            at_bat_number=1,
                            batter_id=888009116,
                            pitcher_id=888009117,
                            batter_team_code="ZQO",
                            pitcher_team_code="ZQP",
                            inning=1,
                            inning_topbot="Top",
                            outcome_code=None,
                        )
                    ],
                )
    finally:
        engine.dispose()


def test_missing_batter_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900000908

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2053)
            game_type_id = _insert_game_type(connection, "QG", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2053, 4, 8),
            )
            _insert_player(connection, 888009118, "Pat Pitcher")
            _insert_team(connection, "ZQQ", "Zeta Quails")
            _insert_team(connection, "ZQR", "Zeta Rams")

            with pytest.raises(ValueError, match="888009999"):
                load_plate_appearances(
                    connection,
                    [
                        StatcastPlateAppearance(
                            mlb_game_pk=mlb_game_pk,
                            at_bat_number=1,
                            batter_id=888009999,
                            pitcher_id=888009118,
                            batter_team_code="ZQQ",
                            pitcher_team_code="ZQR",
                            inning=1,
                            inning_topbot="Top",
                            outcome_code=None,
                        )
                    ],
                )

            assert _count_plate_appearances(connection, [game_id]) == 0
    finally:
        engine.dispose()


def test_missing_pitcher_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900000909

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2052)
            game_type_id = _insert_game_type(connection, "QH", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2052, 4, 8),
            )
            _insert_player(connection, 888009119, "Ada Batter")
            _insert_team(connection, "ZQS", "Zeta Seals")
            _insert_team(connection, "ZQT", "Zeta Tigers")

            with pytest.raises(ValueError, match="888009998"):
                load_plate_appearances(
                    connection,
                    [
                        StatcastPlateAppearance(
                            mlb_game_pk=mlb_game_pk,
                            at_bat_number=1,
                            batter_id=888009119,
                            pitcher_id=888009998,
                            batter_team_code="ZQS",
                            pitcher_team_code="ZQT",
                            inning=1,
                            inning_topbot="Top",
                            outcome_code=None,
                        )
                    ],
                )

            assert _count_plate_appearances(connection, [game_id]) == 0
    finally:
        engine.dispose()


def test_missing_batter_team_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900000910

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2051)
            game_type_id = _insert_game_type(connection, "QI", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2051, 4, 8),
            )
            _insert_player(connection, 888009120, "Ada Batter")
            _insert_player(connection, 888009121, "Pat Pitcher")
            _insert_team(connection, "ZQU", "Zeta Unicorns")

            with pytest.raises(ValueError, match="MISSING_BATTER_TEAM"):
                load_plate_appearances(
                    connection,
                    [
                        StatcastPlateAppearance(
                            mlb_game_pk=mlb_game_pk,
                            at_bat_number=1,
                            batter_id=888009120,
                            pitcher_id=888009121,
                            batter_team_code="MISSING_BATTER_TEAM",
                            pitcher_team_code="ZQU",
                            inning=1,
                            inning_topbot="Top",
                            outcome_code=None,
                        )
                    ],
                )

            assert _count_plate_appearances(connection, [game_id]) == 0
    finally:
        engine.dispose()


def test_missing_pitcher_team_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900000911

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2050)
            game_type_id = _insert_game_type(connection, "QJ", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2050, 4, 8),
            )
            _insert_player(connection, 888009122, "Ada Batter")
            _insert_player(connection, 888009123, "Pat Pitcher")
            _insert_team(connection, "ZQV", "Zeta Vipers")

            with pytest.raises(ValueError, match="MISSING_PITCHER_TEAM"):
                load_plate_appearances(
                    connection,
                    [
                        StatcastPlateAppearance(
                            mlb_game_pk=mlb_game_pk,
                            at_bat_number=1,
                            batter_id=888009122,
                            pitcher_id=888009123,
                            batter_team_code="ZQV",
                            pitcher_team_code="MISSING_PITCHER_TEAM",
                            inning=1,
                            inning_topbot="Top",
                            outcome_code=None,
                        )
                    ],
                )

            assert _count_plate_appearances(connection, [game_id]) == 0
    finally:
        engine.dispose()


def test_null_outcome_code_inserts_null_outcome_type_id():
    engine = _create_engine()
    mlb_game_pk = 900000912

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2049)
            game_type_id = _insert_game_type(connection, "QK", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2049, 4, 8),
            )
            _insert_player(connection, 888009124, "Ada Batter")
            _insert_player(connection, 888009125, "Pat Pitcher")
            _insert_team(connection, "ZQW", "Zeta Wolves")
            _insert_team(connection, "ZQX", "Zeta X-Rays")

            result = load_plate_appearances(
                connection,
                [
                    StatcastPlateAppearance(
                        mlb_game_pk=mlb_game_pk,
                        at_bat_number=1,
                        batter_id=888009124,
                        pitcher_id=888009125,
                        batter_team_code="ZQW",
                        pitcher_team_code="ZQX",
                        inning=1,
                        inning_topbot="Top",
                        outcome_code=None,
                    )
                ],
            )

            assert result == PlateAppearanceLoadResult(
                plate_appearances_supplied=1,
                plate_appearances_loaded=1,
            )
            assert _fetch_plate_appearance(connection, game_id, 1)["outcome_type_id"] is None
    finally:
        engine.dispose()


def test_valid_outcome_code_resolves_to_outcome_type_id():
    engine = _create_engine()
    mlb_game_pk = 900000913

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2048)
            game_type_id = _insert_game_type(connection, "QL", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2048, 4, 8),
            )
            _insert_player(connection, 888009126, "Ada Batter")
            _insert_player(connection, 888009127, "Pat Pitcher")
            _insert_team(connection, "ZQY", "Zeta Yaks")
            _insert_team(connection, "ZQZ", "Zeta Zebras")
            outcome_type_id = _insert_outcome_type(connection, "ZPA_DOUBLE", "Double")

            result = load_plate_appearances(
                connection,
                [
                    StatcastPlateAppearance(
                        mlb_game_pk=mlb_game_pk,
                        at_bat_number=1,
                        batter_id=888009126,
                        pitcher_id=888009127,
                        batter_team_code="ZQY",
                        pitcher_team_code="ZQZ",
                        inning=2,
                        inning_topbot="Bot",
                        outcome_code="ZPA_DOUBLE",
                    )
                ],
            )

            assert result == PlateAppearanceLoadResult(
                plate_appearances_supplied=1,
                plate_appearances_loaded=1,
            )
            assert (
                _fetch_plate_appearance(connection, game_id, 1)["outcome_type_id"]
                == outcome_type_id
            )
    finally:
        engine.dispose()


def test_missing_outcome_code_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900000914

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2047)
            game_type_id = _insert_game_type(connection, "QM", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=mlb_game_pk,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2047, 4, 8),
            )
            _insert_player(connection, 888009128, "Ada Batter")
            _insert_player(connection, 888009129, "Pat Pitcher")
            _insert_team(connection, "ZRA", "Zeta Rays")
            _insert_team(connection, "ZRB", "Zeta Bears")

            with pytest.raises(ValueError, match="MISSING_OUTCOME"):
                load_plate_appearances(
                    connection,
                    [
                        StatcastPlateAppearance(
                            mlb_game_pk=mlb_game_pk,
                            at_bat_number=1,
                            batter_id=888009128,
                            pitcher_id=888009129,
                            batter_team_code="ZRA",
                            pitcher_team_code="ZRB",
                            inning=1,
                            inning_topbot="Top",
                            outcome_code="MISSING_OUTCOME",
                        )
                    ],
                )

            assert _count_plate_appearances(connection, [game_id]) == 0
    finally:
        engine.dispose()


def test_missing_references_do_not_insert_plate_appearances():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2046)
            game_type_id = _insert_game_type(connection, "QN", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=900000915,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2046, 4, 8),
            )
            _insert_player(connection, 888009130, "Ada Batter")
            _insert_player(connection, 888009131, "Pat Pitcher")
            _insert_team(connection, "ZRC", "Zeta Crows")
            _insert_team(connection, "ZRD", "Zeta Ducks")

            with pytest.raises(ValueError, match="900000916"):
                load_plate_appearances(
                    connection,
                    [
                        StatcastPlateAppearance(
                            mlb_game_pk=900000915,
                            at_bat_number=1,
                            batter_id=888009130,
                            pitcher_id=888009131,
                            batter_team_code="ZRC",
                            pitcher_team_code="ZRD",
                            inning=1,
                            inning_topbot="Top",
                            outcome_code=None,
                        ),
                        StatcastPlateAppearance(
                            mlb_game_pk=900000916,
                            at_bat_number=1,
                            batter_id=888009130,
                            pitcher_id=888009131,
                            batter_team_code="ZRC",
                            pitcher_team_code="ZRD",
                            inning=1,
                            inning_topbot="Top",
                            outcome_code=None,
                        ),
                    ],
                )

            assert _count_plate_appearances(connection, [game_id]) == 0
    finally:
        engine.dispose()


def test_successful_load_does_not_commit_or_rollback():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2045)
            game_type_id = _insert_game_type(connection, "QO", "Q Regular")
            game_id = _insert_game(
                connection,
                mlb_game_pk=900000917,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2045, 4, 8),
            )
            _insert_player(connection, 888009132, "Ada Batter")
            _insert_player(connection, 888009133, "Pat Pitcher")
            _insert_team(connection, "ZRE", "Zeta Elks")
            _insert_team(connection, "ZRF", "Zeta Finches")
            connection.commit = MagicMock()
            connection.rollback = MagicMock()

            result = load_plate_appearances(
                connection,
                [
                    StatcastPlateAppearance(
                        mlb_game_pk=900000917,
                        at_bat_number=1,
                        batter_id=888009132,
                        pitcher_id=888009133,
                        batter_team_code="ZRE",
                        pitcher_team_code="ZRF",
                        inning=1,
                        inning_topbot="Top",
                        outcome_code=None,
                    )
                ],
            )

            assert result == PlateAppearanceLoadResult(
                plate_appearances_supplied=1,
                plate_appearances_loaded=1,
            )
            _fetch_plate_appearance(connection, game_id, 1)
            connection.commit.assert_not_called()
            connection.rollback.assert_not_called()
    finally:
        engine.dispose()
