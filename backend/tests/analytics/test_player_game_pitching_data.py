"""Tests for player-game pitching extraction and transformation."""

from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.analytics.player_game_pitching_data import (
    PlayerGamePitching,
    PlayerGamePitchingAppearance,
    get_player_game_pitching_appearances,
    transform_player_game_pitching,
)
from tests.db import create_test_engine


def _appearance(
    *,
    pitcher_id: int = 1,
    game_id: int = 10,
    team_id: int = 100,
    outcome_code: str | None = "single",
    pitches: int = 0,
) -> PlayerGamePitchingAppearance:
    return PlayerGamePitchingAppearance(
        pitcher_id=pitcher_id,
        game_id=game_id,
        team_id=team_id,
        outcome_code=outcome_code,
        pitches=pitches,
    )


def _row(
    *,
    pitcher_id: int = 1,
    game_id: int = 10,
    team_id: int = 100,
    batters_faced: int = 1,
    pitches: int = 0,
    hits_allowed: int = 0,
    home_runs_allowed: int = 0,
    walks: int = 0,
    hit_by_pitch: int = 0,
    strikeouts: int = 0,
) -> PlayerGamePitching:
    return PlayerGamePitching(
        pitcher_id=pitcher_id,
        game_id=game_id,
        team_id=team_id,
        batters_faced=batters_faced,
        pitches=pitches,
        hits_allowed=hits_allowed,
        home_runs_allowed=home_runs_allowed,
        walks=walks,
        hit_by_pitch=hit_by_pitch,
        strikeouts=strikeouts,
    )


def test_empty_input_returns_empty_list():
    connection = MagicMock()

    result = transform_player_game_pitching(connection, [])

    assert result == []
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_single_pitcher_game_team():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [_appearance(outcome_code="single", pitches=3)],
    )

    assert result == [_row(hits_allowed=1, pitches=3)]


def test_multiple_pitchers_remain_separate():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [
            _appearance(pitcher_id=1, outcome_code="walk"),
            _appearance(pitcher_id=2, outcome_code="strikeout"),
        ],
    )

    assert result == [
        _row(pitcher_id=1, walks=1),
        _row(pitcher_id=2, strikeouts=1),
    ]


def test_multiple_games_remain_separate():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [
            _appearance(game_id=10, outcome_code="single"),
            _appearance(game_id=20, outcome_code="double"),
        ],
    )

    assert result == [
        _row(game_id=10, hits_allowed=1),
        _row(game_id=20, hits_allowed=1),
    ]


def test_multiple_teams_remain_separate():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [
            _appearance(team_id=100, outcome_code="walk"),
            _appearance(team_id=200, outcome_code="hit_by_pitch"),
        ],
    )

    assert result == [
        _row(team_id=100, walks=1),
        _row(team_id=200, hit_by_pitch=1),
    ]


def test_single():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [_appearance(outcome_code="single")],
    )

    assert result == [_row(hits_allowed=1)]


def test_double():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [_appearance(outcome_code="double")],
    )

    assert result == [_row(hits_allowed=1)]


def test_triple():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [_appearance(outcome_code="triple")],
    )

    assert result == [_row(hits_allowed=1)]


def test_home_run():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [_appearance(outcome_code="home_run")],
    )

    assert result == [_row(hits_allowed=1, home_runs_allowed=1)]


def test_walk():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [_appearance(outcome_code="walk")],
    )

    assert result == [_row(walks=1)]


def test_intent_walk():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [_appearance(outcome_code="intent_walk")],
    )

    assert result == [_row(walks=1)]


def test_hit_by_pitch():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [_appearance(outcome_code="hit_by_pitch")],
    )

    assert result == [_row(hit_by_pitch=1)]


def test_strikeout():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [_appearance(outcome_code="strikeout")],
    )

    assert result == [_row(strikeouts=1)]


def test_strikeout_double_play():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [_appearance(outcome_code="strikeout_double_play")],
    )

    assert result == [_row(strikeouts=1)]


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
        "sac_fly",
        "sac_fly_double_play",
        "sac_bunt",
        "catcher_interf",
        "truncated_pa",
    ],
)
def test_other_outcomes_count_only_as_batters_faced(outcome_code: str):
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [_appearance(outcome_code=outcome_code)],
    )

    assert result == [_row()]


def test_none_outcome():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [_appearance(outcome_code=None)],
    )

    assert result == [_row()]


def test_unknown_outcome_raises_value_error():
    connection = MagicMock()

    with pytest.raises(
        ValueError,
        match="No pitching statistic mapping found for outcome code wild_pitch.",
    ):
        transform_player_game_pitching(
            connection,
            [_appearance(outcome_code="wild_pitch")],
        )


def test_multiple_outcomes_aggregate_correctly():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [
            _appearance(outcome_code="single"),
            _appearance(outcome_code="home_run"),
            _appearance(outcome_code="walk"),
            _appearance(outcome_code="intent_walk"),
            _appearance(outcome_code="hit_by_pitch"),
            _appearance(outcome_code="strikeout"),
            _appearance(outcome_code="field_out"),
        ],
    )

    assert result == [
        _row(
            batters_faced=7,
            hits_allowed=2,
            home_runs_allowed=1,
            walks=2,
            hit_by_pitch=1,
            strikeouts=1,
        )
    ]


def test_pitch_counts_aggregate_correctly():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [
            _appearance(outcome_code="single", pitches=3),
            _appearance(outcome_code="walk", pitches=5),
        ],
    )

    assert result == [
        _row(batters_faced=2, pitches=8, hits_allowed=1, walks=1)
    ]


def test_results_are_sorted_by_pitcher_game_team():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [
            _appearance(
                pitcher_id=2,
                game_id=20,
                team_id=200,
                outcome_code="double",
            ),
            _appearance(
                pitcher_id=1,
                game_id=10,
                team_id=100,
                outcome_code="single",
            ),
        ],
    )

    assert result == [
        _row(hits_allowed=1),
        _row(
            pitcher_id=2,
            game_id=20,
            team_id=200,
            hits_allowed=1,
        ),
    ]


def test_multiple_plate_appearances_for_the_same_grain_aggregate():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [
            _appearance(outcome_code="single"),
            _appearance(outcome_code="walk"),
            _appearance(outcome_code="field_out"),
        ],
    )

    assert result == [
        _row(batters_faced=3, hits_allowed=1, walks=1)
    ]


def test_multiple_pitches_associated_with_a_plate_appearance():
    connection = MagicMock()

    result = transform_player_game_pitching(
        connection,
        [_appearance(outcome_code="strikeout", pitches=6)],
    )

    assert result == [_row(pitches=6, strikeouts=1)]


def test_transformation_does_not_manage_transactions():
    connection = MagicMock()

    transform_player_game_pitching(
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


def _insert_pitch(
    connection: Connection,
    *,
    plate_appearance_id: int,
    pitch_number: int,
    balls: int | None = None,
    strikes: int | None = None,
) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.pitch (
                plate_appearance_id,
                pitch_number,
                balls,
                strikes
            )
            VALUES (
                :plate_appearance_id,
                :pitch_number,
                :balls,
                :strikes
            )
            RETURNING pitch_id
            """
        ),
        {
            "plate_appearance_id": plate_appearance_id,
            "pitch_number": pitch_number,
            "balls": balls,
            "strikes": strikes,
        },
    ).scalar_one()


def _seed_plate_appearance_lookups(
    connection: Connection,
    *,
    season_year: int,
    game_type_code: str,
    mlb_game_pk: int,
    batter_mlb_id: int = 888041101,
    pitcher_mlb_id: int = 888041102,
    batter_team_code: str = "ZPA",
    pitcher_team_code: str = "ZPB",
    outcome_code: str | None = "ZPA_SINGLE",
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

            assert get_player_game_pitching_appearances(connection) == []
    finally:
        engine.dispose()


def test_extraction_maps_a_single_plate_appearance():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_plate_appearances(connection)
            ids = _seed_plate_appearance_lookups(
                connection,
                season_year=2311,
                game_type_code="ZPA",
                mlb_game_pk=921001001,
                outcome_code="ZPA_SINGLE",
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

            result = get_player_game_pitching_appearances(connection)

            assert result == [
                PlayerGamePitchingAppearance(
                    pitcher_id=ids["pitcher_id"],
                    game_id=ids["game_id"],
                    team_id=ids["pitcher_team_id"],
                    outcome_code="ZPA_SINGLE",
                    pitches=0,
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
                season_year=2312,
                game_type_code="ZPB",
                mlb_game_pk=921001002,
                batter_mlb_id=888041201,
                pitcher_mlb_id=888041202,
                batter_team_code="ZPC",
                pitcher_team_code="ZPD",
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

            result = get_player_game_pitching_appearances(connection)

            assert result == [
                PlayerGamePitchingAppearance(
                    pitcher_id=ids["pitcher_id"],
                    game_id=ids["game_id"],
                    team_id=ids["pitcher_team_id"],
                    outcome_code=None,
                    pitches=0,
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
                season_year=2313,
                game_type_code="ZPC",
                mlb_game_pk=921001003,
                batter_mlb_id=888041301,
                pitcher_mlb_id=888041302,
                batter_team_code="ZPE",
                pitcher_team_code="ZPF",
                outcome_code="ZPC_SINGLE",
            )
            walk_id = _insert_outcome_type(connection, "ZPC_WALK", "Zeta Walk")
            first_pa = _insert_plate_appearance(
                connection,
                game_id=ids["game_id"],
                at_bat_number=1,
                batter_id=ids["batter_id"],
                pitcher_id=ids["pitcher_id"],
                batter_team_id=ids["batter_team_id"],
                pitcher_team_id=ids["pitcher_team_id"],
                outcome_type_id=ids["outcome_type_id"],
            )
            second_pa = _insert_plate_appearance(
                connection,
                game_id=ids["game_id"],
                at_bat_number=2,
                batter_id=ids["batter_id"],
                pitcher_id=ids["pitcher_id"],
                batter_team_id=ids["batter_team_id"],
                pitcher_team_id=ids["pitcher_team_id"],
                outcome_type_id=walk_id,
            )
            _insert_pitch(connection, plate_appearance_id=first_pa, pitch_number=1)
            _insert_pitch(connection, plate_appearance_id=second_pa, pitch_number=1)
            _insert_pitch(connection, plate_appearance_id=second_pa, pitch_number=2)

            result = get_player_game_pitching_appearances(connection)

            assert result == [
                PlayerGamePitchingAppearance(
                    pitcher_id=ids["pitcher_id"],
                    game_id=ids["game_id"],
                    team_id=ids["pitcher_team_id"],
                    outcome_code="ZPC_SINGLE",
                    pitches=1,
                ),
                PlayerGamePitchingAppearance(
                    pitcher_id=ids["pitcher_id"],
                    game_id=ids["game_id"],
                    team_id=ids["pitcher_team_id"],
                    outcome_code="ZPC_WALK",
                    pitches=2,
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
                season_year=2314,
                game_type_code="ZPD",
                mlb_game_pk=921001004,
                batter_mlb_id=888041401,
                pitcher_mlb_id=888041402,
                batter_team_code="ZPG",
                pitcher_team_code="ZPH",
                outcome_code="ZPD_DOUBLE",
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

            result = get_player_game_pitching_appearances(connection)

            assert stored_code == "ZPD_DOUBLE"
            assert result[0].outcome_code == stored_code
            assert result[0].team_id == ids["pitcher_team_id"]
    finally:
        engine.dispose()


def test_extraction_orders_by_game_id_and_at_bat_number():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_plate_appearances(connection)
            first = _seed_plate_appearance_lookups(
                connection,
                season_year=2315,
                game_type_code="ZPE",
                mlb_game_pk=921001005,
                batter_mlb_id=888041501,
                pitcher_mlb_id=888041502,
                batter_team_code="ZPI",
                pitcher_team_code="ZPJ",
                outcome_code="ZPE_FIRST",
            )
            second = _seed_plate_appearance_lookups(
                connection,
                season_year=2316,
                game_type_code="ZPF",
                mlb_game_pk=921001006,
                batter_mlb_id=888041601,
                pitcher_mlb_id=888041602,
                batter_team_code="ZPK",
                pitcher_team_code="ZPL",
                outcome_code="ZPF_SECOND",
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

            result = get_player_game_pitching_appearances(connection)

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
                "ZPE_FIRST",
                "ZPE_FIRST",
                "ZPF_SECOND",
            ]
    finally:
        engine.dispose()


def test_extraction_counts_pitch_rows_for_a_plate_appearance():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_plate_appearances(connection)
            ids = _seed_plate_appearance_lookups(
                connection,
                season_year=2317,
                game_type_code="ZPG",
                mlb_game_pk=921001007,
                batter_mlb_id=888041701,
                pitcher_mlb_id=888041702,
                batter_team_code="ZPM",
                pitcher_team_code="ZPN",
                outcome_code="ZPG_STRIKEOUT",
            )
            plate_appearance_id = _insert_plate_appearance(
                connection,
                game_id=ids["game_id"],
                at_bat_number=1,
                batter_id=ids["batter_id"],
                pitcher_id=ids["pitcher_id"],
                batter_team_id=ids["batter_team_id"],
                pitcher_team_id=ids["pitcher_team_id"],
                outcome_type_id=ids["outcome_type_id"],
            )
            _insert_pitch(
                connection,
                plate_appearance_id=plate_appearance_id,
                pitch_number=1,
            )
            _insert_pitch(
                connection,
                plate_appearance_id=plate_appearance_id,
                pitch_number=2,
            )
            _insert_pitch(
                connection,
                plate_appearance_id=plate_appearance_id,
                pitch_number=3,
            )

            result = get_player_game_pitching_appearances(connection)

            assert result == [
                PlayerGamePitchingAppearance(
                    pitcher_id=ids["pitcher_id"],
                    game_id=ids["game_id"],
                    team_id=ids["pitcher_team_id"],
                    outcome_code="ZPG_STRIKEOUT",
                    pitches=3,
                )
            ]
    finally:
        engine.dispose()


def test_extraction_pitch_count_is_row_count_not_balls_or_strikes():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_plate_appearances(connection)
            ids = _seed_plate_appearance_lookups(
                connection,
                season_year=2318,
                game_type_code="ZPH",
                mlb_game_pk=921001008,
                batter_mlb_id=888041801,
                pitcher_mlb_id=888041802,
                batter_team_code="ZPO",
                pitcher_team_code="ZPP",
                outcome_code="ZPH_WALK",
            )
            plate_appearance_id = _insert_plate_appearance(
                connection,
                game_id=ids["game_id"],
                at_bat_number=1,
                batter_id=ids["batter_id"],
                pitcher_id=ids["pitcher_id"],
                batter_team_id=ids["batter_team_id"],
                pitcher_team_id=ids["pitcher_team_id"],
                outcome_type_id=ids["outcome_type_id"],
            )
            _insert_pitch(
                connection,
                plate_appearance_id=plate_appearance_id,
                pitch_number=1,
                balls=3,
                strikes=2,
            )
            _insert_pitch(
                connection,
                plate_appearance_id=plate_appearance_id,
                pitch_number=2,
                balls=3,
                strikes=2,
            )

            result = get_player_game_pitching_appearances(connection)

            assert len(result) == 1
            assert result[0].pitches == 2
            assert result[0].pitches != 5
    finally:
        engine.dispose()


def test_extraction_uses_supplied_connection_and_does_not_manage_transactions():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_plate_appearances(connection)
            ids = _seed_plate_appearance_lookups(
                connection,
                season_year=2319,
                game_type_code="ZPI",
                mlb_game_pk=921001009,
                batter_mlb_id=888041901,
                pitcher_mlb_id=888041902,
                batter_team_code="ZPQ",
                pitcher_team_code="ZPR",
                outcome_code="ZPI_SINGLE",
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
                result = get_player_game_pitching_appearances(connection)
            finally:
                connection.commit = original_commit
                connection.begin = original_begin

            assert result == [
                PlayerGamePitchingAppearance(
                    pitcher_id=ids["pitcher_id"],
                    game_id=ids["game_id"],
                    team_id=ids["pitcher_team_id"],
                    outcome_code="ZPI_SINGLE",
                    pitches=0,
                )
            ]
            commit_spy.assert_not_called()
            begin_spy.assert_not_called()
    finally:
        engine.dispose()
