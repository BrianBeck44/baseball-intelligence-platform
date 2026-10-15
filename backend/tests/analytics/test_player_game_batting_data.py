"""Tests for player-game batting extraction and transformation."""

from contextlib import contextmanager
from dataclasses import asdict
from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from sqlalchemy.exc import IntegrityError

from app.analytics.player_game_batting_data import (
    PlayerGameBatting,
    PlayerGameBattingAppearance,
    get_player_game_batting_appearances,
    load_player_game_batting,
    transform_player_game_batting,
)
from tests.db import create_test_engine


def _appearance(
    *,
    player_id: int = 1,
    game_id: int = 10,
    team_id: int = 100,
    outcome_code: str | None = "single",
) -> PlayerGameBattingAppearance:
    return PlayerGameBattingAppearance(
        player_id=player_id,
        game_id=game_id,
        team_id=team_id,
        outcome_code=outcome_code,
    )


def _row(
    *,
    player_id: int = 1,
    game_id: int = 10,
    team_id: int = 100,
    plate_appearances: int = 1,
    at_bats: int = 0,
    hits: int = 0,
    singles: int = 0,
    doubles: int = 0,
    triples: int = 0,
    home_runs: int = 0,
    walks: int = 0,
    hit_by_pitch: int = 0,
    strikeouts: int = 0,
    sacrifice_flies: int = 0,
    sacrifice_bunts: int = 0,
) -> PlayerGameBatting:
    return PlayerGameBatting(
        player_id=player_id,
        game_id=game_id,
        team_id=team_id,
        plate_appearances=plate_appearances,
        at_bats=at_bats,
        hits=hits,
        singles=singles,
        doubles=doubles,
        triples=triples,
        home_runs=home_runs,
        walks=walks,
        hit_by_pitch=hit_by_pitch,
        strikeouts=strikeouts,
        sacrifice_flies=sacrifice_flies,
        sacrifice_bunts=sacrifice_bunts,
    )


def test_empty_input_returns_empty_list():
    connection = MagicMock()

    result = transform_player_game_batting(connection, [])

    assert result == []
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_single():
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [_appearance(outcome_code="single")],
    )

    assert result == [_row(at_bats=1, hits=1, singles=1)]


def test_double():
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [_appearance(outcome_code="double")],
    )

    assert result == [_row(at_bats=1, hits=1, doubles=1)]


def test_triple():
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [_appearance(outcome_code="triple")],
    )

    assert result == [_row(at_bats=1, hits=1, triples=1)]


def test_home_run():
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [_appearance(outcome_code="home_run")],
    )

    assert result == [_row(at_bats=1, hits=1, home_runs=1)]


@pytest.mark.parametrize("outcome_code", ["walk", "intent_walk"])
def test_walk_and_intent_walk(outcome_code: str):
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [_appearance(outcome_code=outcome_code)],
    )

    assert result == [_row(walks=1)]


def test_hit_by_pitch():
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [_appearance(outcome_code="hit_by_pitch")],
    )

    assert result == [_row(hit_by_pitch=1)]


@pytest.mark.parametrize("outcome_code", ["strikeout", "strikeout_double_play"])
def test_strikeout_and_strikeout_double_play(outcome_code: str):
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [_appearance(outcome_code=outcome_code)],
    )

    assert result == [_row(at_bats=1, strikeouts=1)]


@pytest.mark.parametrize("outcome_code", ["sac_fly", "sac_fly_double_play"])
def test_sacrifice_fly(outcome_code: str):
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [_appearance(outcome_code=outcome_code)],
    )

    assert result == [_row(sacrifice_flies=1)]
    assert result[0].at_bats == 0


def test_sacrifice_bunt():
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [_appearance(outcome_code="sac_bunt")],
    )

    assert result == [_row(sacrifice_bunts=1)]


@pytest.mark.parametrize(
    "outcome_code",
    [
        "field_out",
        "field_error",
        "force_out",
        "grounded_into_double_play",
        "double_play",
        "triple_play",
        "fielders_choice",
        "fielders_choice_out",
    ],
)
def test_ordinary_out_outcomes(outcome_code: str):
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [_appearance(outcome_code=outcome_code)],
    )

    assert result == [_row(at_bats=1)]
    assert result[0].sacrifice_flies == 0


def test_catcher_interf():
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [_appearance(outcome_code="catcher_interf")],
    )

    assert result == [_row()]


def test_truncated_pa():
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [_appearance(outcome_code="truncated_pa")],
    )

    assert result == [_row()]


def test_none_outcome():
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [_appearance(outcome_code=None)],
    )

    assert result == [_row()]


def test_unknown_outcome_raises_value_error():
    connection = MagicMock()

    with pytest.raises(
        ValueError,
        match="No batting statistic mapping found for outcome code wild_pitch.",
    ):
        transform_player_game_batting(
            connection,
            [_appearance(outcome_code="wild_pitch")],
        )


def test_multiple_appearances_for_the_same_grain_aggregate():
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [
            _appearance(outcome_code="single"),
            _appearance(outcome_code="walk"),
            _appearance(outcome_code="field_out"),
        ],
    )

    assert result == [
        _row(plate_appearances=3, at_bats=2, hits=1, singles=1, walks=1)
    ]


def test_different_grains_remain_separate_and_sorted():
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [
            _appearance(
                player_id=2,
                game_id=20,
                team_id=200,
                outcome_code="double",
            ),
            _appearance(
                player_id=1,
                game_id=10,
                team_id=100,
                outcome_code="single",
            ),
        ],
    )

    assert result == [
        _row(at_bats=1, hits=1, singles=1),
        _row(
            player_id=2,
            game_id=20,
            team_id=200,
            at_bats=1,
            hits=1,
            doubles=1,
        ),
    ]


def test_hits_equal_singles_doubles_triples_and_home_runs():
    connection = MagicMock()

    result = transform_player_game_batting(
        connection,
        [
            _appearance(outcome_code="single"),
            _appearance(outcome_code="single"),
            _appearance(outcome_code="double"),
            _appearance(outcome_code="triple"),
            _appearance(outcome_code="home_run"),
            _appearance(outcome_code="walk"),
        ],
    )

    assert len(result) == 1
    row = result[0]
    assert row.singles == 2
    assert row.doubles == 1
    assert row.triples == 1
    assert row.home_runs == 1
    assert row.hits == row.singles + row.doubles + row.triples + row.home_runs
    assert row.hits == 5
    assert row.walks == 1
    assert row.plate_appearances == 6
    assert row.at_bats == 5


def test_transformation_does_not_manage_transactions():
    connection = MagicMock()

    transform_player_game_batting(
        connection,
        [_appearance(outcome_code="single")],
    )

    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


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


def _clear_plate_appearances(connection: Connection) -> None:
    connection.execute(text("DELETE FROM curated.pitch"))
    connection.execute(text("DELETE FROM curated.plate_appearance"))


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


def _insert_plate_appearance(
    connection: Connection,
    *,
    game_id: int,
    at_bat_number: int,
    batter_id: int,
    pitcher_id: int,
    batter_team_id: int,
    pitcher_team_id: int,
    outcome_type_id: int | None,
) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.plate_appearance (
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
            )
            VALUES (
                :game_id,
                :at_bat_number,
                :batter_id,
                :pitcher_id,
                :batter_team_id,
                :pitcher_team_id,
                1,
                'Top',
                :outcome_type_id,
                'L',
                'R'
            )
            RETURNING plate_appearance_id
            """
        ),
        {
            "game_id": game_id,
            "at_bat_number": at_bat_number,
            "batter_id": batter_id,
            "pitcher_id": pitcher_id,
            "batter_team_id": batter_team_id,
            "pitcher_team_id": pitcher_team_id,
            "outcome_type_id": outcome_type_id,
        },
    ).scalar_one()


def _seed_plate_appearance_lookups(
    connection: Connection,
    *,
    season_year: int,
    game_type_code: str,
    mlb_game_pk: int,
    batter_mlb_id: int = 888021101,
    pitcher_mlb_id: int = 888021102,
    batter_team_code: str = "ZYA",
    pitcher_team_code: str = "ZYB",
    outcome_code: str | None = "ZYA_SINGLE",
) -> dict[str, int | None]:
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
    outcome_type_id = (
        None
        if outcome_code is None
        else _insert_outcome_type(connection, outcome_code, "Zeta Single")
    )
    return {
        "game_id": game_id,
        "batter_id": batter_id,
        "pitcher_id": pitcher_id,
        "batter_team_id": batter_team_id,
        "pitcher_team_id": pitcher_team_id,
        "outcome_type_id": outcome_type_id,
    }


def test_extraction_empty_table_returns_empty_list():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_plate_appearances(connection)

            assert get_player_game_batting_appearances(connection) == []
    finally:
        engine.dispose()


def test_extraction_maps_a_single_plate_appearance():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_plate_appearances(connection)
            ids = _seed_plate_appearance_lookups(
                connection,
                season_year=2211,
                game_type_code="ZYA",
                mlb_game_pk=911001001,
                outcome_code="ZYA_SINGLE",
            )
            _insert_plate_appearance(
                connection,
                game_id=ids["game_id"],
                at_bat_number=1,
                batter_id=ids["batter_id"],
                pitcher_id=ids["pitcher_id"],
                batter_team_id=ids["batter_team_id"],
                pitcher_team_id=ids["pitcher_team_id"],
                outcome_type_id=ids["outcome_type_id"],
            )

            result = get_player_game_batting_appearances(connection)

            assert result == [
                PlayerGameBattingAppearance(
                    player_id=ids["batter_id"],
                    game_id=ids["game_id"],
                    team_id=ids["batter_team_id"],
                    outcome_code="ZYA_SINGLE",
                )
            ]
    finally:
        engine.dispose()


def test_extraction_null_outcome_type_id_produces_none_outcome_code():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_plate_appearances(connection)
            ids = _seed_plate_appearance_lookups(
                connection,
                season_year=2212,
                game_type_code="ZYB",
                mlb_game_pk=911001002,
                batter_mlb_id=888021201,
                pitcher_mlb_id=888021202,
                batter_team_code="ZYC",
                pitcher_team_code="ZYD",
                outcome_code=None,
            )
            _insert_plate_appearance(
                connection,
                game_id=ids["game_id"],
                at_bat_number=1,
                batter_id=ids["batter_id"],
                pitcher_id=ids["pitcher_id"],
                batter_team_id=ids["batter_team_id"],
                pitcher_team_id=ids["pitcher_team_id"],
                outcome_type_id=None,
            )

            result = get_player_game_batting_appearances(connection)

            assert result == [
                PlayerGameBattingAppearance(
                    player_id=ids["batter_id"],
                    game_id=ids["game_id"],
                    team_id=ids["batter_team_id"],
                    outcome_code=None,
                )
            ]
    finally:
        engine.dispose()


def test_extraction_returns_one_object_per_plate_appearance():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_plate_appearances(connection)
            ids = _seed_plate_appearance_lookups(
                connection,
                season_year=2213,
                game_type_code="ZYC",
                mlb_game_pk=911001003,
                batter_mlb_id=888021301,
                pitcher_mlb_id=888021302,
                batter_team_code="ZYE",
                pitcher_team_code="ZYF",
                outcome_code="ZYC_SINGLE",
            )
            walk_id = _insert_outcome_type(connection, "ZYC_WALK", "Zeta Walk")
            _insert_plate_appearance(
                connection,
                game_id=ids["game_id"],
                at_bat_number=1,
                batter_id=ids["batter_id"],
                pitcher_id=ids["pitcher_id"],
                batter_team_id=ids["batter_team_id"],
                pitcher_team_id=ids["pitcher_team_id"],
                outcome_type_id=ids["outcome_type_id"],
            )
            _insert_plate_appearance(
                connection,
                game_id=ids["game_id"],
                at_bat_number=2,
                batter_id=ids["batter_id"],
                pitcher_id=ids["pitcher_id"],
                batter_team_id=ids["batter_team_id"],
                pitcher_team_id=ids["pitcher_team_id"],
                outcome_type_id=walk_id,
            )

            result = get_player_game_batting_appearances(connection)

            assert result == [
                PlayerGameBattingAppearance(
                    player_id=ids["batter_id"],
                    game_id=ids["game_id"],
                    team_id=ids["batter_team_id"],
                    outcome_code="ZYC_SINGLE",
                ),
                PlayerGameBattingAppearance(
                    player_id=ids["batter_id"],
                    game_id=ids["game_id"],
                    team_id=ids["batter_team_id"],
                    outcome_code="ZYC_WALK",
                ),
            ]
    finally:
        engine.dispose()


def test_extraction_joins_outcome_type_by_id():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_plate_appearances(connection)
            ids = _seed_plate_appearance_lookups(
                connection,
                season_year=2214,
                game_type_code="ZYD",
                mlb_game_pk=911001004,
                batter_mlb_id=888021401,
                pitcher_mlb_id=888021402,
                batter_team_code="ZYG",
                pitcher_team_code="ZYH",
                outcome_code="ZYD_DOUBLE",
            )
            _insert_plate_appearance(
                connection,
                game_id=ids["game_id"],
                at_bat_number=1,
                batter_id=ids["batter_id"],
                pitcher_id=ids["pitcher_id"],
                batter_team_id=ids["batter_team_id"],
                pitcher_team_id=ids["pitcher_team_id"],
                outcome_type_id=ids["outcome_type_id"],
            )

            stored_code = connection.execute(
                text(
                    """
                    SELECT ot.code
                    FROM curated.plate_appearance AS pa
                    JOIN curated.outcome_type AS ot
                      ON ot.id = pa.outcome_type_id
                    WHERE pa.game_id = :game_id
                      AND pa.at_bat_number = 1
                    """
                ),
                {"game_id": ids["game_id"]},
            ).scalar_one()

            result = get_player_game_batting_appearances(connection)

            assert stored_code == "ZYD_DOUBLE"
            assert result[0].outcome_code == stored_code
    finally:
        engine.dispose()


def test_extraction_orders_by_game_id_and_at_bat_number():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_plate_appearances(connection)
            first = _seed_plate_appearance_lookups(
                connection,
                season_year=2215,
                game_type_code="ZYE",
                mlb_game_pk=911001005,
                batter_mlb_id=888021501,
                pitcher_mlb_id=888021502,
                batter_team_code="ZYI",
                pitcher_team_code="ZYJ",
                outcome_code="ZYE_FIRST",
            )
            second = _seed_plate_appearance_lookups(
                connection,
                season_year=2216,
                game_type_code="ZYF",
                mlb_game_pk=911001006,
                batter_mlb_id=888021601,
                pitcher_mlb_id=888021602,
                batter_team_code="ZYK",
                pitcher_team_code="ZYL",
                outcome_code="ZYF_SECOND",
            )
            _insert_plate_appearance(
                connection,
                game_id=second["game_id"],
                at_bat_number=2,
                batter_id=second["batter_id"],
                pitcher_id=second["pitcher_id"],
                batter_team_id=second["batter_team_id"],
                pitcher_team_id=second["pitcher_team_id"],
                outcome_type_id=second["outcome_type_id"],
            )
            _insert_plate_appearance(
                connection,
                game_id=first["game_id"],
                at_bat_number=3,
                batter_id=first["batter_id"],
                pitcher_id=first["pitcher_id"],
                batter_team_id=first["batter_team_id"],
                pitcher_team_id=first["pitcher_team_id"],
                outcome_type_id=first["outcome_type_id"],
            )
            _insert_plate_appearance(
                connection,
                game_id=first["game_id"],
                at_bat_number=1,
                batter_id=first["batter_id"],
                pitcher_id=first["pitcher_id"],
                batter_team_id=first["batter_team_id"],
                pitcher_team_id=first["pitcher_team_id"],
                outcome_type_id=first["outcome_type_id"],
            )

            result = get_player_game_batting_appearances(connection)

            assert [row.game_id for row in result] == [
                first["game_id"],
                first["game_id"],
                second["game_id"],
            ]
            assert first["game_id"] < second["game_id"]
            first_game_at_bats = connection.execute(
                text(
                    """
                    SELECT at_bat_number
                    FROM curated.plate_appearance
                    WHERE game_id = :game_id
                    ORDER BY at_bat_number
                    """
                ),
                {"game_id": first["game_id"]},
            ).scalars().all()
            assert list(first_game_at_bats) == [1, 3]
            assert [row.outcome_code for row in result] == [
                "ZYE_FIRST",
                "ZYE_FIRST",
                "ZYF_SECOND",
            ]
    finally:
        engine.dispose()


def test_extraction_uses_supplied_connection_and_does_not_manage_transactions():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_plate_appearances(connection)
            ids = _seed_plate_appearance_lookups(
                connection,
                season_year=2217,
                game_type_code="ZYG",
                mlb_game_pk=911001007,
                batter_mlb_id=888021701,
                pitcher_mlb_id=888021702,
                batter_team_code="ZYM",
                pitcher_team_code="ZYN",
                outcome_code="ZYG_SINGLE",
            )
            _insert_plate_appearance(
                connection,
                game_id=ids["game_id"],
                at_bat_number=1,
                batter_id=ids["batter_id"],
                pitcher_id=ids["pitcher_id"],
                batter_team_id=ids["batter_team_id"],
                pitcher_team_id=ids["pitcher_team_id"],
                outcome_type_id=ids["outcome_type_id"],
            )

            original_commit = connection.commit
            original_begin = connection.begin
            commit_spy = MagicMock()
            begin_spy = MagicMock()
            connection.commit = commit_spy
            connection.begin = begin_spy
            try:
                result = get_player_game_batting_appearances(connection)
            finally:
                connection.commit = original_commit
                connection.begin = original_begin

            assert result == [
                PlayerGameBattingAppearance(
                    player_id=ids["batter_id"],
                    game_id=ids["game_id"],
                    team_id=ids["batter_team_id"],
                    outcome_code="ZYG_SINGLE",
                )
            ]
            commit_spy.assert_not_called()
            begin_spy.assert_not_called()
    finally:
        engine.dispose()


def _insert_game_team(
    connection: Connection,
    *,
    game_id: int,
    team_id: int,
    home_away: str,
) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.game_team (game_id, team_id, home_away)
            VALUES (:game_id, :team_id, :home_away)
            RETURNING game_team_id
            """
        ),
        {"game_id": game_id, "team_id": team_id, "home_away": home_away},
    ).scalar_one()


def _fetch_player_game_batting(
    connection: Connection,
    *,
    player_id: int,
    game_id: int,
    team_id: int,
):
    return connection.execute(
        text(
            """
            SELECT
                player_game_batting_id,
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
                sacrifice_bunts,
                created_at
            FROM analytics.player_game_batting
            WHERE player_id = :player_id
              AND game_id = :game_id
              AND team_id = :team_id
            """
        ),
        {
            "player_id": player_id,
            "game_id": game_id,
            "team_id": team_id,
        },
    ).mappings().one()


def _seed_batting_load_lookups(
    connection: Connection,
    *,
    season_year: int,
    game_type_code: str,
    mlb_game_pk: int,
    batter_mlb_id: int,
    pitcher_mlb_id: int,
    batter_team_code: str,
    pitcher_team_code: str,
) -> dict[str, int]:
    ids = _seed_plate_appearance_lookups(
        connection,
        season_year=season_year,
        game_type_code=game_type_code,
        mlb_game_pk=mlb_game_pk,
        batter_mlb_id=batter_mlb_id,
        pitcher_mlb_id=pitcher_mlb_id,
        batter_team_code=batter_team_code,
        pitcher_team_code=pitcher_team_code,
        outcome_code=None,
    )
    _insert_game_team(
        connection,
        game_id=ids["game_id"],
        team_id=ids["batter_team_id"],
        home_away="HOME",
    )
    _insert_game_team(
        connection,
        game_id=ids["game_id"],
        team_id=ids["pitcher_team_id"],
        home_away="AWAY",
    )
    return {
        "game_id": ids["game_id"],
        "batter_id": ids["batter_id"],
        "pitcher_id": ids["pitcher_id"],
        "batter_team_id": ids["batter_team_id"],
        "pitcher_team_id": ids["pitcher_team_id"],
    }


def test_load_empty_input_returns_zero_and_does_not_execute():
    connection = MagicMock()

    result = load_player_game_batting(connection, [])

    assert result == 0
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_load_inserts_a_single_row():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_batting_load_lookups(
                connection,
                season_year=2221,
                game_type_code="ZZA",
                mlb_game_pk=912001001,
                batter_mlb_id=888031101,
                pitcher_mlb_id=888031102,
                batter_team_code="ZZA",
                pitcher_team_code="ZZB",
            )
            row = _row(
                player_id=ids["batter_id"],
                game_id=ids["game_id"],
                team_id=ids["batter_team_id"],
                plate_appearances=3,
                at_bats=2,
                hits=1,
                singles=1,
            )

            inserted = load_player_game_batting(connection, [row])
            stored = _fetch_player_game_batting(
                connection,
                player_id=ids["batter_id"],
                game_id=ids["game_id"],
                team_id=ids["batter_team_id"],
            )

            assert inserted == 1
            assert stored["player_id"] == ids["batter_id"]
            assert stored["game_id"] == ids["game_id"]
            assert stored["team_id"] == ids["batter_team_id"]
            assert stored["plate_appearances"] == 3
            assert stored["at_bats"] == 2
            assert stored["hits"] == 1
            assert stored["singles"] == 1
            assert stored["doubles"] == 0
            assert stored["walks"] == 0
    finally:
        engine.dispose()


def test_load_inserts_multiple_rows():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_batting_load_lookups(
                connection,
                season_year=2222,
                game_type_code="ZZC",
                mlb_game_pk=912001002,
                batter_mlb_id=888031201,
                pitcher_mlb_id=888031202,
                batter_team_code="ZZC",
                pitcher_team_code="ZZD",
            )
            rows = [
                _row(
                    player_id=ids["batter_id"],
                    game_id=ids["game_id"],
                    team_id=ids["batter_team_id"],
                    plate_appearances=2,
                    at_bats=2,
                    hits=1,
                    doubles=1,
                ),
                _row(
                    player_id=ids["pitcher_id"],
                    game_id=ids["game_id"],
                    team_id=ids["pitcher_team_id"],
                    plate_appearances=1,
                    walks=1,
                ),
            ]

            inserted = load_player_game_batting(connection, rows)

            assert inserted == 2
            home = _fetch_player_game_batting(
                connection,
                player_id=ids["batter_id"],
                game_id=ids["game_id"],
                team_id=ids["batter_team_id"],
            )
            away = _fetch_player_game_batting(
                connection,
                player_id=ids["pitcher_id"],
                game_id=ids["game_id"],
                team_id=ids["pitcher_team_id"],
            )
            assert home["doubles"] == 1
            assert away["walks"] == 1
    finally:
        engine.dispose()


def test_load_does_not_supply_generated_primary_key_or_created_at():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_batting_load_lookups(
                connection,
                season_year=2223,
                game_type_code="ZZE",
                mlb_game_pk=912001003,
                batter_mlb_id=888031301,
                pitcher_mlb_id=888031302,
                batter_team_code="ZZE",
                pitcher_team_code="ZZF",
            )
            row = _row(
                player_id=ids["batter_id"],
                game_id=ids["game_id"],
                team_id=ids["batter_team_id"],
                plate_appearances=1,
                at_bats=1,
                hits=1,
                home_runs=1,
            )

            payload = asdict(row)
            original_execute = connection.execute
            captured: list[object] = []

            def spy_execute(statement, *args, **kwargs):
                captured.append(statement)
                return original_execute(statement, *args, **kwargs)

            connection.execute = spy_execute
            try:
                inserted = load_player_game_batting(connection, [row])
            finally:
                connection.execute = original_execute

            stored = _fetch_player_game_batting(
                connection,
                player_id=ids["batter_id"],
                game_id=ids["game_id"],
                team_id=ids["batter_team_id"],
            )
            compiled = str(captured[0].compile(dialect=connection.dialect))

            assert inserted == 1
            assert "player_game_batting_id" not in payload
            assert "created_at" not in payload
            assert "player_game_batting_id" not in compiled
            assert "created_at" not in compiled
            assert stored["player_game_batting_id"] is not None
            assert stored["created_at"] is not None
    finally:
        engine.dispose()


def test_load_duplicate_business_key_raises_integrity_error():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_batting_load_lookups(
                connection,
                season_year=2224,
                game_type_code="ZZG",
                mlb_game_pk=912001004,
                batter_mlb_id=888031401,
                pitcher_mlb_id=888031402,
                batter_team_code="ZZG",
                pitcher_team_code="ZZH",
            )
            row = _row(
                player_id=ids["batter_id"],
                game_id=ids["game_id"],
                team_id=ids["batter_team_id"],
                plate_appearances=1,
                at_bats=1,
                hits=1,
                singles=1,
            )
            load_player_game_batting(connection, [row])

            with pytest.raises(IntegrityError):
                load_player_game_batting(connection, [row])
    finally:
        engine.dispose()


def test_load_does_not_manage_transactions():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_batting_load_lookups(
                connection,
                season_year=2225,
                game_type_code="ZZI",
                mlb_game_pk=912001005,
                batter_mlb_id=888031501,
                pitcher_mlb_id=888031502,
                batter_team_code="ZZI",
                pitcher_team_code="ZZJ",
            )
            row = _row(
                player_id=ids["batter_id"],
                game_id=ids["game_id"],
                team_id=ids["batter_team_id"],
                plate_appearances=1,
                at_bats=1,
            )

            original_commit = connection.commit
            original_rollback = connection.rollback
            original_begin = connection.begin
            commit_spy = MagicMock()
            rollback_spy = MagicMock()
            begin_spy = MagicMock()
            connection.commit = commit_spy
            connection.rollback = rollback_spy
            connection.begin = begin_spy
            try:
                inserted = load_player_game_batting(connection, [row])
            finally:
                connection.commit = original_commit
                connection.rollback = original_rollback
                connection.begin = original_begin

            assert inserted == 1
            commit_spy.assert_not_called()
            rollback_spy.assert_not_called()
            begin_spy.assert_not_called()
    finally:
        engine.dispose()


