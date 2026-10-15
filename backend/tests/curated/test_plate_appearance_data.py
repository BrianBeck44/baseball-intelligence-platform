"""Tests for Statcast plate-appearance transformation into curated records."""

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from tests.db import create_test_engine
from app.curated.plate_appearance_data import (
    CuratedPlateAppearance,
    PlateAppearanceLoadResult,
    _PLATE_APPEARANCE_INSERT_BATCH_SIZE,
    load_plate_appearances,
    transform_plate_appearances,
)
from app.curated.statcast_plate_appearance_data import StatcastPlateAppearance


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


def _statcast_plate_appearance(
    *,
    mlb_game_pk: int,
    at_bat_number: int = 1,
    batter_id: int = 888011101,
    pitcher_id: int = 888011102,
    batter_team_code: str = "ZRA",
    pitcher_team_code: str = "ZRB",
    inning: int = 1,
    inning_topbot: str = "Top",
    stand: str = "L",
    p_throws: str = "R",
    outcome_code: str | None = "ZRA_SINGLE",
) -> StatcastPlateAppearance:
    return StatcastPlateAppearance(
        mlb_game_pk=mlb_game_pk,
        at_bat_number=at_bat_number,
        batter_id=batter_id,
        pitcher_id=pitcher_id,
        batter_team_code=batter_team_code,
        pitcher_team_code=pitcher_team_code,
        inning=inning,
        inning_topbot=inning_topbot,
        stand=stand,
        p_throws=p_throws,
        outcome_code=outcome_code,
    )


def _curated_plate_appearance(
    *,
    game_id: int,
    at_bat_number: int = 1,
    batter_id: int,
    pitcher_id: int,
    batter_team_id: int,
    pitcher_team_id: int,
    inning: int = 1,
    inning_topbot: str = "Top",
    outcome_type_id: int | None,
    stand: str = "L",
    p_throws: str = "R",
) -> CuratedPlateAppearance:
    return CuratedPlateAppearance(
        game_id=game_id,
        at_bat_number=at_bat_number,
        batter_id=batter_id,
        pitcher_id=pitcher_id,
        batter_team_id=batter_team_id,
        pitcher_team_id=pitcher_team_id,
        inning=inning,
        inning_topbot=inning_topbot,
        outcome_type_id=outcome_type_id,
        stand=stand,
        p_throws=p_throws,
    )


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
                outcome_type_id,
                stand,
                p_throws
            FROM curated.plate_appearance
            WHERE game_id = :game_id
              AND at_bat_number = :at_bat_number
            """
        ),
        {"game_id": game_id, "at_bat_number": at_bat_number},
    ).mappings().one()


def _seed_required_lookups(
    connection: Connection,
    *,
    season_year: int,
    game_type_code: str,
    mlb_game_pk: int,
    batter_mlb_id: int = 888011101,
    pitcher_mlb_id: int = 888011102,
    batter_team_code: str = "ZRA",
    pitcher_team_code: str = "ZRB",
    outcome_code: str = "ZRA_SINGLE",
) -> dict[str, int | str]:
    season_id = _insert_season(connection, season_year)
    game_type_id = _insert_game_type(connection, game_type_code, "Zeta Regular")
    game_id = _insert_game(
        connection,
        mlb_game_pk=mlb_game_pk,
        season_id=season_id,
        game_type_id=game_type_id,
        official_game_date=date(season_year, 4, 8),
    )
    batter_id = _insert_player(connection, batter_mlb_id, "Ada Batter")
    pitcher_id = _insert_player(connection, pitcher_mlb_id, "Pat Pitcher")
    batter_team_id = _insert_team(connection, batter_team_code, "Zeta Aces")
    pitcher_team_id = _insert_team(connection, pitcher_team_code, "Zeta Bats")
    outcome_type_id = _insert_outcome_type(connection, outcome_code, "Single")
    return {
        "season_id": season_id,
        "game_type_id": game_type_id,
        "game_id": game_id,
        "batter_id": batter_id,
        "pitcher_id": pitcher_id,
        "batter_team_id": batter_team_id,
        "pitcher_team_id": pitcher_team_id,
        "outcome_type_id": outcome_type_id,
    }


def test_empty_input_returns_empty_list():
    connection = MagicMock()

    result = transform_plate_appearances(connection, [])

    assert result == []
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_one_extracted_plate_appearance_transforms_correctly():
    engine = _create_engine()
    mlb_game_pk = 900001001

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2071,
                game_type_code="ZRA",
                mlb_game_pk=mlb_game_pk,
            )

            result = transform_plate_appearances(
                connection,
                [
                    _statcast_plate_appearance(
                        mlb_game_pk=mlb_game_pk,
                        stand="S",
                        p_throws="L",
                    )
                ],
            )

            assert result == [
                CuratedPlateAppearance(
                    game_id=ids["game_id"],
                    at_bat_number=1,
                    batter_id=ids["batter_id"],
                    pitcher_id=ids["pitcher_id"],
                    batter_team_id=ids["batter_team_id"],
                    pitcher_team_id=ids["pitcher_team_id"],
                    inning=1,
                    inning_topbot="Top",
                    outcome_type_id=ids["outcome_type_id"],
                    stand="S",
                    p_throws="L",
                )
            ]
    finally:
        engine.dispose()


def test_mlb_game_pk_resolves_to_game_id():
    engine = _create_engine()
    mlb_game_pk = 900001002

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2072,
                game_type_code="ZRB",
                mlb_game_pk=mlb_game_pk,
                batter_team_code="ZRC",
                pitcher_team_code="ZRD",
                outcome_code="ZRB_WALK",
            )

            result = transform_plate_appearances(
                connection,
                [_statcast_plate_appearance(
                    mlb_game_pk=mlb_game_pk,
                    batter_team_code="ZRC",
                    pitcher_team_code="ZRD",
                    outcome_code="ZRB_WALK",
                )],
            )

            assert len(result) == 1
            assert result[0].game_id == ids["game_id"]
    finally:
        engine.dispose()


def test_batter_mlb_id_resolves_to_player_id():
    engine = _create_engine()
    mlb_game_pk = 900001003

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2073,
                game_type_code="ZRC",
                mlb_game_pk=mlb_game_pk,
                batter_mlb_id=888011201,
                batter_team_code="ZRE",
                pitcher_team_code="ZRF",
                outcome_code="ZRC_DOUBLE",
            )

            result = transform_plate_appearances(
                connection,
                [_statcast_plate_appearance(
                    mlb_game_pk=mlb_game_pk,
                    batter_id=888011201,
                    batter_team_code="ZRE",
                    pitcher_team_code="ZRF",
                    outcome_code="ZRC_DOUBLE",
                )],
            )

            assert len(result) == 1
            assert result[0].batter_id == ids["batter_id"]
    finally:
        engine.dispose()


def test_pitcher_mlb_id_resolves_to_player_id():
    engine = _create_engine()
    mlb_game_pk = 900001004

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2074,
                game_type_code="ZRD",
                mlb_game_pk=mlb_game_pk,
                pitcher_mlb_id=888011202,
                batter_team_code="ZRG",
                pitcher_team_code="ZRH",
                outcome_code="ZRD_TRIPLE",
            )

            result = transform_plate_appearances(
                connection,
                [_statcast_plate_appearance(
                    mlb_game_pk=mlb_game_pk,
                    pitcher_id=888011202,
                    batter_team_code="ZRG",
                    pitcher_team_code="ZRH",
                    outcome_code="ZRD_TRIPLE",
                )],
            )

            assert len(result) == 1
            assert result[0].pitcher_id == ids["pitcher_id"]
    finally:
        engine.dispose()


def test_batter_team_code_resolves_to_team_id():
    engine = _create_engine()
    mlb_game_pk = 900001005

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2075,
                game_type_code="ZRE",
                mlb_game_pk=mlb_game_pk,
                batter_team_code="ZRI",
                pitcher_team_code="ZRJ",
                outcome_code="ZRE_HR",
            )

            result = transform_plate_appearances(
                connection,
                [_statcast_plate_appearance(
                    mlb_game_pk=mlb_game_pk,
                    batter_team_code="ZRI",
                    pitcher_team_code="ZRJ",
                    outcome_code="ZRE_HR",
                )],
            )

            assert len(result) == 1
            assert result[0].batter_team_id == ids["batter_team_id"]
    finally:
        engine.dispose()


def test_pitcher_team_code_resolves_to_team_id():
    engine = _create_engine()
    mlb_game_pk = 900001006

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2076,
                game_type_code="ZRF",
                mlb_game_pk=mlb_game_pk,
                batter_team_code="ZRK",
                pitcher_team_code="ZRL",
                outcome_code="ZRF_SO",
            )

            result = transform_plate_appearances(
                connection,
                [_statcast_plate_appearance(
                    mlb_game_pk=mlb_game_pk,
                    batter_team_code="ZRK",
                    pitcher_team_code="ZRL",
                    outcome_code="ZRF_SO",
                )],
            )

            assert len(result) == 1
            assert result[0].pitcher_team_id == ids["pitcher_team_id"]
    finally:
        engine.dispose()


def test_non_null_outcome_code_resolves_to_outcome_type_id():
    engine = _create_engine()
    mlb_game_pk = 900001007

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2077,
                game_type_code="ZRG",
                mlb_game_pk=mlb_game_pk,
                batter_team_code="ZRM",
                pitcher_team_code="ZRN",
                outcome_code="ZRG_FO",
            )

            result = transform_plate_appearances(
                connection,
                [_statcast_plate_appearance(
                    mlb_game_pk=mlb_game_pk,
                    batter_team_code="ZRM",
                    pitcher_team_code="ZRN",
                    outcome_code="ZRG_FO",
                )],
            )

            assert len(result) == 1
            assert result[0].outcome_type_id == ids["outcome_type_id"]
    finally:
        engine.dispose()


def test_null_outcome_code_produces_none_outcome_type_id():
    engine = _create_engine()
    mlb_game_pk = 900001008

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2078,
                game_type_code="ZRH",
                mlb_game_pk=mlb_game_pk,
                batter_team_code="ZRO",
                pitcher_team_code="ZRP",
                outcome_code="ZRH_UNUSED",
            )

            result = transform_plate_appearances(
                connection,
                [_statcast_plate_appearance(
                    mlb_game_pk=mlb_game_pk,
                    batter_team_code="ZRO",
                    pitcher_team_code="ZRP",
                    outcome_code=None,
                )],
            )

            assert len(result) == 1
            assert result[0].outcome_type_id is None
    finally:
        engine.dispose()


def test_missing_game_raises_value_error():
    engine = _create_engine()
    missing_game_pk = 900001099

    try:
        with _isolated_connection(engine) as connection:
            season_id = _insert_season(connection, 2079)
            game_type_id = _insert_game_type(connection, "ZRI", "Zeta Regular")
            _insert_game(
                connection,
                mlb_game_pk=900001009,
                season_id=season_id,
                game_type_id=game_type_id,
                official_game_date=date(2079, 4, 8),
            )
            _insert_player(connection, 888011101, "Ada Batter")
            _insert_player(connection, 888011102, "Pat Pitcher")
            _insert_team(connection, "ZRQ", "Zeta Aces")
            _insert_team(connection, "ZRR", "Zeta Bats")
            _insert_outcome_type(connection, "ZRI_SINGLE", "Single")

            with pytest.raises(
                ValueError,
                match=rf"No curated game found for MLB game PK {missing_game_pk}",
            ):
                transform_plate_appearances(
                    connection,
                    [_statcast_plate_appearance(
                        mlb_game_pk=missing_game_pk,
                        batter_team_code="ZRQ",
                        pitcher_team_code="ZRR",
                        outcome_code="ZRI_SINGLE",
                    )],
                )
    finally:
        engine.dispose()


def test_missing_batter_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900001010
    missing_batter_id = 888011999

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2080,
                game_type_code="ZRJ",
                mlb_game_pk=mlb_game_pk,
                batter_team_code="ZRS",
                pitcher_team_code="ZRT",
                outcome_code="ZRJ_SINGLE",
            )

            with pytest.raises(
                ValueError,
                match=(
                    rf"No curated player found for MLB player ID "
                    rf"{missing_batter_id}"
                ),
            ):
                transform_plate_appearances(
                    connection,
                    [_statcast_plate_appearance(
                        mlb_game_pk=mlb_game_pk,
                        batter_id=missing_batter_id,
                        batter_team_code="ZRS",
                        pitcher_team_code="ZRT",
                        outcome_code="ZRJ_SINGLE",
                    )],
                )
    finally:
        engine.dispose()


def test_missing_pitcher_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900001011
    missing_pitcher_id = 888011998

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2081,
                game_type_code="ZRK",
                mlb_game_pk=mlb_game_pk,
                batter_team_code="ZRU",
                pitcher_team_code="ZRV",
                outcome_code="ZRK_SINGLE",
            )

            with pytest.raises(
                ValueError,
                match=(
                    rf"No curated player found for MLB player ID "
                    rf"{missing_pitcher_id}"
                ),
            ):
                transform_plate_appearances(
                    connection,
                    [_statcast_plate_appearance(
                        mlb_game_pk=mlb_game_pk,
                        pitcher_id=missing_pitcher_id,
                        batter_team_code="ZRU",
                        pitcher_team_code="ZRV",
                        outcome_code="ZRK_SINGLE",
                    )],
                )
    finally:
        engine.dispose()


def test_missing_batter_team_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900001012
    missing_team_code = "ZZ_MISS_BAT"

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2082,
                game_type_code="ZRL",
                mlb_game_pk=mlb_game_pk,
                batter_team_code="ZRW",
                pitcher_team_code="ZRX",
                outcome_code="ZRL_SINGLE",
            )

            with pytest.raises(
                ValueError,
                match=rf"No curated team found for team code {missing_team_code}",
            ):
                transform_plate_appearances(
                    connection,
                    [_statcast_plate_appearance(
                        mlb_game_pk=mlb_game_pk,
                        batter_team_code=missing_team_code,
                        pitcher_team_code="ZRX",
                        outcome_code="ZRL_SINGLE",
                    )],
                )
    finally:
        engine.dispose()


def test_missing_pitcher_team_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900001013
    missing_team_code = "ZZ_MISS_PIT"

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2083,
                game_type_code="ZRM",
                mlb_game_pk=mlb_game_pk,
                batter_team_code="ZRY",
                pitcher_team_code="ZRZ",
                outcome_code="ZRM_SINGLE",
            )

            with pytest.raises(
                ValueError,
                match=rf"No curated team found for team code {missing_team_code}",
            ):
                transform_plate_appearances(
                    connection,
                    [_statcast_plate_appearance(
                        mlb_game_pk=mlb_game_pk,
                        batter_team_code="ZRY",
                        pitcher_team_code=missing_team_code,
                        outcome_code="ZRM_SINGLE",
                    )],
                )
    finally:
        engine.dispose()


def test_unknown_non_null_outcome_code_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900001014
    missing_outcome_code = "zzz_missing_outcome"

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2084,
                game_type_code="ZRN",
                mlb_game_pk=mlb_game_pk,
                batter_team_code="ZSA",
                pitcher_team_code="ZSB",
                outcome_code="ZRN_SINGLE",
            )

            with pytest.raises(
                ValueError,
                match=(
                    rf"No curated outcome type found for outcome code "
                    rf"{missing_outcome_code}"
                ),
            ):
                transform_plate_appearances(
                    connection,
                    [_statcast_plate_appearance(
                        mlb_game_pk=mlb_game_pk,
                        batter_team_code="ZSA",
                        pitcher_team_code="ZSB",
                        outcome_code=missing_outcome_code,
                    )],
                )
    finally:
        engine.dispose()


def test_multiple_extracted_plate_appearances_transform_independently():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            first = _seed_required_lookups(
                connection,
                season_year=2085,
                game_type_code="ZRO",
                mlb_game_pk=900001015,
                batter_mlb_id=888011301,
                pitcher_mlb_id=888011302,
                batter_team_code="ZSC",
                pitcher_team_code="ZSD",
                outcome_code="ZRO_SINGLE",
            )
            second_game_id = _insert_game(
                connection,
                mlb_game_pk=900001016,
                season_id=first["season_id"],
                game_type_id=first["game_type_id"],
                official_game_date=date(2085, 4, 9),
            )
            second_batter_id = _insert_player(connection, 888011303, "Bea Batter")
            second_outcome_id = _insert_outcome_type(
                connection,
                "ZRO_WALK",
                "Walk",
            )

            extracted = [
                _statcast_plate_appearance(
                    mlb_game_pk=900001015,
                    at_bat_number=1,
                    batter_id=888011301,
                    pitcher_id=888011302,
                    batter_team_code="ZSC",
                    pitcher_team_code="ZSD",
                    inning=1,
                    inning_topbot="Top",
                    stand="L",
                    p_throws="R",
                    outcome_code="ZRO_SINGLE",
                ),
                _statcast_plate_appearance(
                    mlb_game_pk=900001016,
                    at_bat_number=3,
                    batter_id=888011303,
                    pitcher_id=888011302,
                    batter_team_code="ZSC",
                    pitcher_team_code="ZSD",
                    inning=8,
                    inning_topbot="Bot",
                    stand="R",
                    p_throws="L",
                    outcome_code="ZRO_WALK",
                ),
            ]

            result = transform_plate_appearances(connection, extracted)

            assert result == [
                CuratedPlateAppearance(
                    game_id=first["game_id"],
                    at_bat_number=1,
                    batter_id=first["batter_id"],
                    pitcher_id=first["pitcher_id"],
                    batter_team_id=first["batter_team_id"],
                    pitcher_team_id=first["pitcher_team_id"],
                    inning=1,
                    inning_topbot="Top",
                    outcome_type_id=first["outcome_type_id"],
                    stand="L",
                    p_throws="R",
                ),
                CuratedPlateAppearance(
                    game_id=second_game_id,
                    at_bat_number=3,
                    batter_id=second_batter_id,
                    pitcher_id=first["pitcher_id"],
                    batter_team_id=first["batter_team_id"],
                    pitcher_team_id=first["pitcher_team_id"],
                    inning=8,
                    inning_topbot="Bot",
                    outcome_type_id=second_outcome_id,
                    stand="R",
                    p_throws="L",
                ),
            ]
    finally:
        engine.dispose()


def test_transformation_does_not_manage_transactions():
    engine = _create_engine()
    mlb_game_pk = 900001017

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2086,
                game_type_code="ZRP",
                mlb_game_pk=mlb_game_pk,
                batter_team_code="ZSE",
                pitcher_team_code="ZSF",
                outcome_code="ZRP_SINGLE",
            )
            connection.commit = MagicMock()
            connection.rollback = MagicMock()

            transform_plate_appearances(
                connection,
                [_statcast_plate_appearance(
                    mlb_game_pk=mlb_game_pk,
                    batter_team_code="ZSE",
                    pitcher_team_code="ZSF",
                    outcome_code="ZRP_SINGLE",
                )],
            )

            connection.commit.assert_not_called()
            connection.rollback.assert_not_called()
    finally:
        engine.dispose()


def test_empty_load_returns_zero_counts():
    connection = MagicMock()

    result = load_plate_appearances(connection, [])

    assert result == PlateAppearanceLoadResult(
        plate_appearances_supplied=0,
        plate_appearances_loaded=0,
    )
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_curated_plate_appearance_is_inserted():
    engine = _create_engine()
    mlb_game_pk = 900001101

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2091,
                game_type_code="ZTA",
                mlb_game_pk=mlb_game_pk,
                batter_team_code="ZTA",
                pitcher_team_code="ZTB",
                outcome_code="ZTA_SINGLE",
            )
            curated = _curated_plate_appearance(
                game_id=ids["game_id"],
                batter_id=ids["batter_id"],
                pitcher_id=ids["pitcher_id"],
                batter_team_id=ids["batter_team_id"],
                pitcher_team_id=ids["pitcher_team_id"],
                outcome_type_id=ids["outcome_type_id"],
                stand="S",
                p_throws="L",
            )

            result = load_plate_appearances(connection, [curated])

            assert result == PlateAppearanceLoadResult(
                plate_appearances_supplied=1,
                plate_appearances_loaded=1,
            )
            row = _fetch_plate_appearance(connection, ids["game_id"], 1)
            assert row["game_id"] == ids["game_id"]
            assert row["at_bat_number"] == 1
            assert row["batter_id"] == ids["batter_id"]
            assert row["pitcher_id"] == ids["pitcher_id"]
            assert row["batter_team_id"] == ids["batter_team_id"]
            assert row["pitcher_team_id"] == ids["pitcher_team_id"]
            assert row["inning"] == 1
            assert row["inning_topbot"] == "Top"
            assert row["outcome_type_id"] == ids["outcome_type_id"]
            assert row["stand"] == "S"
            assert row["p_throws"] == "L"
            assert row["plate_appearance_id"] is not None
    finally:
        engine.dispose()


def test_upsert_updates_non_key_fields_and_preserves_plate_appearance_id():
    engine = _create_engine()
    mlb_game_pk = 900001102

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2092,
                game_type_code="ZTB",
                mlb_game_pk=mlb_game_pk,
                batter_mlb_id=888012101,
                pitcher_mlb_id=888012102,
                batter_team_code="ZTC",
                pitcher_team_code="ZTD",
                outcome_code="ZTB_SINGLE",
            )
            other_batter_id = _insert_player(connection, 888012103, "Bea Batter")
            other_outcome_id = _insert_outcome_type(connection, "ZTB_WALK", "Walk")
            original = _curated_plate_appearance(
                game_id=ids["game_id"],
                batter_id=ids["batter_id"],
                pitcher_id=ids["pitcher_id"],
                batter_team_id=ids["batter_team_id"],
                pitcher_team_id=ids["pitcher_team_id"],
                outcome_type_id=ids["outcome_type_id"],
                stand="L",
                p_throws="R",
            )

            load_plate_appearances(connection, [original])
            original_id = _fetch_plate_appearance(
                connection, ids["game_id"], 1
            )["plate_appearance_id"]

            updated = _curated_plate_appearance(
                game_id=ids["game_id"],
                batter_id=other_batter_id,
                pitcher_id=ids["pitcher_id"],
                batter_team_id=ids["batter_team_id"],
                pitcher_team_id=ids["pitcher_team_id"],
                inning=3,
                inning_topbot="Bot",
                outcome_type_id=other_outcome_id,
                stand="R",
                p_throws="L",
            )
            result = load_plate_appearances(connection, [updated])

            assert result == PlateAppearanceLoadResult(
                plate_appearances_supplied=1,
                plate_appearances_loaded=1,
            )
            row = _fetch_plate_appearance(connection, ids["game_id"], 1)
            assert row["plate_appearance_id"] == original_id
            assert row["game_id"] == ids["game_id"]
            assert row["at_bat_number"] == 1
            assert row["batter_id"] == other_batter_id
            assert row["inning"] == 3
            assert row["inning_topbot"] == "Bot"
            assert row["outcome_type_id"] == other_outcome_id
            assert row["stand"] == "R"
            assert row["p_throws"] == "L"
    finally:
        engine.dispose()


def test_load_does_not_manage_transactions():
    engine = _create_engine()
    mlb_game_pk = 900001103

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2093,
                game_type_code="ZTC",
                mlb_game_pk=mlb_game_pk,
                batter_team_code="ZTE",
                pitcher_team_code="ZTF",
                outcome_code="ZTC_SINGLE",
            )
            connection.commit = MagicMock()
            connection.rollback = MagicMock()

            load_plate_appearances(
                connection,
                [_curated_plate_appearance(
                    game_id=ids["game_id"],
                    batter_id=ids["batter_id"],
                    pitcher_id=ids["pitcher_id"],
                    batter_team_id=ids["batter_team_id"],
                    pitcher_team_id=ids["pitcher_team_id"],
                    outcome_type_id=ids["outcome_type_id"],
                )],
            )

            connection.commit.assert_not_called()
            connection.rollback.assert_not_called()
    finally:
        engine.dispose()


def _curated_plate_appearances(count: int) -> list[CuratedPlateAppearance]:
    return [
        _curated_plate_appearance(
            game_id=1,
            at_bat_number=index,
            batter_id=2,
            pitcher_id=3,
            batter_team_id=4,
            pitcher_team_id=5,
            outcome_type_id=6,
        )
        for index in range(1, count + 1)
    ]


def _patch_plate_appearance_insert():
    statement = MagicMock()
    statement.values.return_value = statement
    statement.on_conflict_do_update.return_value = statement
    table = MagicMock()
    return (
        patch(
            "app.curated.plate_appearance_data._curated_table",
            return_value=table,
        ),
        patch(
            "app.curated.plate_appearance_data.insert",
            return_value=statement,
        ),
        statement,
        table,
    )


def test_fewer_than_500_rows_makes_one_database_write():
    connection = MagicMock()
    count = _PLATE_APPEARANCE_INSERT_BATCH_SIZE - 1
    table_patch, insert_patch, statement, table = _patch_plate_appearance_insert()

    with table_patch, insert_patch:
        result = load_plate_appearances(
            connection,
            _curated_plate_appearances(count),
        )

    statement.values.assert_called_once()
    assert len(statement.values.call_args.args[0]) == count
    statement.on_conflict_do_update.assert_called_once()
    assert statement.on_conflict_do_update.call_args.kwargs["index_elements"] == [
        table.c.game_id,
        table.c.at_bat_number,
    ]
    connection.execute.assert_called_once_with(statement)
    assert result == PlateAppearanceLoadResult(
        plate_appearances_supplied=count,
        plate_appearances_loaded=count,
    )


def test_exactly_500_rows_makes_one_database_write():
    connection = MagicMock()
    count = _PLATE_APPEARANCE_INSERT_BATCH_SIZE
    table_patch, insert_patch, statement, table = _patch_plate_appearance_insert()

    with table_patch, insert_patch:
        result = load_plate_appearances(
            connection,
            _curated_plate_appearances(count),
        )

    statement.values.assert_called_once()
    assert len(statement.values.call_args.args[0]) == count
    statement.on_conflict_do_update.assert_called_once()
    assert statement.on_conflict_do_update.call_args.kwargs["index_elements"] == [
        table.c.game_id,
        table.c.at_bat_number,
    ]
    connection.execute.assert_called_once_with(statement)
    assert result == PlateAppearanceLoadResult(
        plate_appearances_supplied=count,
        plate_appearances_loaded=count,
    )


def test_more_than_500_rows_makes_multiple_database_writes():
    connection = MagicMock()
    count = _PLATE_APPEARANCE_INSERT_BATCH_SIZE + 1
    table_patch, insert_patch, statement, table = _patch_plate_appearance_insert()

    with table_patch, insert_patch:
        result = load_plate_appearances(
            connection,
            _curated_plate_appearances(count),
        )

    assert statement.values.call_count == 2
    assert len(statement.values.call_args_list[0].args[0]) == (
        _PLATE_APPEARANCE_INSERT_BATCH_SIZE
    )
    assert len(statement.values.call_args_list[1].args[0]) == 1
    assert statement.on_conflict_do_update.call_count == 2
    for call in statement.on_conflict_do_update.call_args_list:
        assert call.kwargs["index_elements"] == [
            table.c.game_id,
            table.c.at_bat_number,
        ]
    assert connection.execute.call_count == 2
    assert result == PlateAppearanceLoadResult(
        plate_appearances_supplied=count,
        plate_appearances_loaded=count,
    )
