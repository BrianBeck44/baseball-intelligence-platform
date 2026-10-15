"""Tests for player pitch-type effectiveness extraction and transformation."""

from contextlib import contextmanager
from dataclasses import asdict
from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.analytics.player_pitch_type_effectiveness_data import (
    PlayerPitchTypeEffectiveness,
    PlayerPitchTypeEffectivenessPitch,
    get_player_pitch_type_effectiveness_pitches,
    load_player_pitch_type_effectiveness,
    transform_player_pitch_type_effectiveness,
)
from tests.db import create_test_engine

SLIDER = 10
FASTBALL = 20


def _pitch(
    *,
    player_id: int = 1,
    pitch_type_id: int = SLIDER,
    plate_appearance_id: int = 100,
    pitch_outcome_code: str | None = "ball",
    pa_outcome_code: str | None = None,
    is_terminal_pitch: bool = False,
) -> PlayerPitchTypeEffectivenessPitch:
    return PlayerPitchTypeEffectivenessPitch(
        player_id=player_id,
        pitch_type_id=pitch_type_id,
        plate_appearance_id=plate_appearance_id,
        pitch_outcome_code=pitch_outcome_code,
        pa_outcome_code=pa_outcome_code,
        is_terminal_pitch=is_terminal_pitch,
    )


def _row(
    *,
    player_id: int = 1,
    pitch_type_id: int = SLIDER,
    pitches: int = 1,
    plate_appearances: int = 1,
    balls_in_play: int = 0,
    swings: int = 0,
    whiffs: int = 0,
    called_strikes: int = 0,
    fouls: int = 0,
    hits_allowed: int = 0,
    home_runs_allowed: int = 0,
    strikeouts: int = 0,
    walks: int = 0,
    hit_by_pitch: int = 0,
    whiff_rate: float | None | object = ...,
    called_strike_rate: float | None | object = ...,
    swing_rate: float | None | object = ...,
    contact_rate: float | None | object = ...,
    strikeout_rate: float | None | object = ...,
) -> PlayerPitchTypeEffectiveness:
    return PlayerPitchTypeEffectiveness(
        player_id=player_id,
        pitch_type_id=pitch_type_id,
        pitches=pitches,
        plate_appearances=plate_appearances,
        balls_in_play=balls_in_play,
        swings=swings,
        whiffs=whiffs,
        called_strikes=called_strikes,
        fouls=fouls,
        hits_allowed=hits_allowed,
        home_runs_allowed=home_runs_allowed,
        strikeouts=strikeouts,
        walks=walks,
        hit_by_pitch=hit_by_pitch,
        whiff_rate=(
            (whiffs / swings if swings else None)
            if whiff_rate is ...
            else whiff_rate
        ),
        called_strike_rate=(
            (called_strikes / pitches if pitches else None)
            if called_strike_rate is ...
            else called_strike_rate
        ),
        swing_rate=(
            (swings / pitches if pitches else None)
            if swing_rate is ...
            else swing_rate
        ),
        contact_rate=(
            ((swings - whiffs) / swings if swings else None)
            if contact_rate is ...
            else contact_rate
        ),
        strikeout_rate=(
            (strikeouts / plate_appearances if plate_appearances else None)
            if strikeout_rate is ...
            else strikeout_rate
        ),
    )


def _by_type(
    result: list[PlayerPitchTypeEffectiveness],
) -> dict[int, PlayerPitchTypeEffectiveness]:
    return {row.pitch_type_id: row for row in result}


def test_empty_input_returns_empty_list():
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(connection, [])

    assert result == []
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_basic_pitch_aggregation_and_rates():
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [
            _pitch(pitch_outcome_code="called_strike"),
            _pitch(pitch_outcome_code="swinging_strike"),
            _pitch(pitch_outcome_code="foul"),
            _pitch(
                pitch_outcome_code="hit_into_play",
                pa_outcome_code="single",
                is_terminal_pitch=True,
            ),
        ],
    )

    assert result == [
        _row(
            pitches=4,
            plate_appearances=1,
            swings=3,
            whiffs=1,
            called_strikes=1,
            balls_in_play=1,
            fouls=1,
            hits_allowed=1,
        )
    ]
    row = result[0]
    assert row.whiff_rate == 1 / 3
    assert row.called_strike_rate == 1 / 4
    assert row.swing_rate == 3 / 4
    assert row.contact_rate == 2 / 3
    assert row.strikeout_rate == 0.0


def test_multiple_pitches_in_one_pa_count_as_one_plate_appearance():
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [
            _pitch(pitch_outcome_code="ball"),
            _pitch(pitch_outcome_code="called_strike"),
            _pitch(
                pitch_outcome_code="swinging_strike",
                pa_outcome_code="strikeout",
                is_terminal_pitch=True,
            ),
        ],
    )

    assert result == [
        _row(
            pitches=3,
            plate_appearances=1,
            swings=1,
            whiffs=1,
            called_strikes=1,
            strikeouts=1,
        )
    ]


def test_distinct_plate_appearances_are_counted_once_each():
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [
            _pitch(plate_appearance_id=100, pitch_outcome_code="ball"),
            _pitch(
                plate_appearance_id=100,
                pitch_outcome_code="foul",
                is_terminal_pitch=True,
            ),
            _pitch(
                plate_appearance_id=101,
                pitch_outcome_code="called_strike",
                is_terminal_pitch=True,
            ),
        ],
    )

    assert result == [
        _row(
            pitches=3,
            plate_appearances=2,
            swings=1,
            fouls=1,
            called_strikes=1,
        )
    ]


def test_multiple_pitch_types_in_one_pa_attribute_strikeout_to_terminal_only():
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [
            _pitch(
                pitch_type_id=SLIDER,
                pitch_outcome_code="ball",
                pa_outcome_code="strikeout",
            ),
            _pitch(
                pitch_type_id=FASTBALL,
                pitch_outcome_code="swinging_strike",
                pa_outcome_code="strikeout",
                is_terminal_pitch=True,
            ),
        ],
    )

    by_type = _by_type(result)
    assert by_type[SLIDER] == _row(pitches=1, plate_appearances=1)
    assert by_type[FASTBALL] == _row(
        pitch_type_id=FASTBALL,
        pitches=1,
        plate_appearances=1,
        swings=1,
        whiffs=1,
        strikeouts=1,
    )


@pytest.mark.parametrize(
    ("pa_outcome_code", "hits_allowed", "home_runs_allowed"),
    [
        ("single", 1, 0),
        ("double", 1, 0),
        ("triple", 1, 0),
        ("home_run", 1, 1),
    ],
)
def test_terminal_pitch_receives_hit_credit(
    pa_outcome_code: str,
    hits_allowed: int,
    home_runs_allowed: int,
):
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [
            _pitch(
                pitch_type_id=SLIDER,
                pitch_outcome_code="ball",
                pa_outcome_code=pa_outcome_code,
            ),
            _pitch(
                pitch_type_id=FASTBALL,
                pitch_outcome_code="hit_into_play",
                pa_outcome_code=pa_outcome_code,
                is_terminal_pitch=True,
            ),
        ],
    )

    by_type = _by_type(result)
    assert by_type[SLIDER].hits_allowed == 0
    assert by_type[SLIDER].home_runs_allowed == 0
    assert by_type[FASTBALL].hits_allowed == hits_allowed
    assert by_type[FASTBALL].home_runs_allowed == home_runs_allowed
    assert by_type[FASTBALL].balls_in_play == 1


def test_terminal_pitch_receives_walk():
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [
            _pitch(
                pitch_type_id=SLIDER,
                pitch_outcome_code="ball",
                pa_outcome_code="walk",
            ),
            _pitch(
                pitch_type_id=FASTBALL,
                pitch_outcome_code="ball",
                pa_outcome_code="walk",
                is_terminal_pitch=True,
            ),
        ],
    )

    by_type = _by_type(result)
    assert by_type[SLIDER].walks == 0
    assert by_type[FASTBALL].walks == 1


def test_terminal_pa_hit_by_pitch_is_not_inferred_from_pitch_outcome():
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [
            _pitch(
                pitch_type_id=SLIDER,
                pitch_outcome_code="hit_by_pitch",
                pa_outcome_code="field_out",
                is_terminal_pitch=True,
            ),
            _pitch(
                player_id=1,
                pitch_type_id=FASTBALL,
                plate_appearance_id=101,
                pitch_outcome_code="ball",
                pa_outcome_code="hit_by_pitch",
                is_terminal_pitch=True,
            ),
        ],
    )

    by_type = _by_type(result)
    assert by_type[SLIDER].hit_by_pitch == 0
    assert by_type[FASTBALL].hit_by_pitch == 1


def test_terminal_pitch_receives_strikeout():
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [
            _pitch(
                pitch_type_id=SLIDER,
                pitch_outcome_code="foul",
                pa_outcome_code="strikeout",
            ),
            _pitch(
                pitch_type_id=FASTBALL,
                pitch_outcome_code="swinging_strike",
                pa_outcome_code="strikeout",
                is_terminal_pitch=True,
            ),
        ],
    )

    by_type = _by_type(result)
    assert by_type[SLIDER].strikeouts == 0
    assert by_type[FASTBALL].strikeouts == 1


@pytest.mark.parametrize(
    ("pitch_outcome_code", "whiffs", "balls_in_play", "fouls"),
    [
        ("bunt_foul_tip", 0, 0, 1),
        ("foul", 0, 0, 1),
        ("foul_bunt", 0, 0, 1),
        ("foul_tip", 0, 0, 1),
        ("hit_into_play", 0, 1, 0),
        ("missed_bunt", 0, 0, 0),
        ("swinging_strike", 1, 0, 0),
        ("swinging_strike_blocked", 1, 0, 0),
    ],
)
def test_swing_outcomes(
    pitch_outcome_code: str,
    whiffs: int,
    balls_in_play: int,
    fouls: int,
):
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [_pitch(pitch_outcome_code=pitch_outcome_code, is_terminal_pitch=True)],
    )

    assert result == [
        _row(
            swings=1,
            whiffs=whiffs,
            balls_in_play=balls_in_play,
            fouls=fouls,
        )
    ]


@pytest.mark.parametrize(
    ("pitch_outcome_code", "called_strikes"),
    [
        ("automatic_ball", 0),
        ("ball", 0),
        ("blocked_ball", 0),
        ("called_strike", 1),
        ("hit_by_pitch", 0),
        ("pitchout", 0),
    ],
)
def test_non_swing_pitch_outcomes(pitch_outcome_code: str, called_strikes: int):
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [_pitch(pitch_outcome_code=pitch_outcome_code, is_terminal_pitch=True)],
    )

    assert result == [_row(called_strikes=called_strikes)]
    assert result[0].swings == 0


def test_rate_calculations_are_unambiguous():
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [
            _pitch(plate_appearance_id=100, pitch_outcome_code="called_strike"),
            _pitch(plate_appearance_id=100, pitch_outcome_code="swinging_strike"),
            _pitch(
                plate_appearance_id=101,
                pitch_outcome_code="swinging_strike",
                pa_outcome_code="strikeout",
                is_terminal_pitch=True,
            ),
            _pitch(
                plate_appearance_id=100,
                pitch_outcome_code="foul",
                is_terminal_pitch=True,
            ),
        ],
    )

    assert len(result) == 1
    row = result[0]
    assert row.pitches == 4
    assert row.plate_appearances == 2
    assert row.swings == 3
    assert row.whiffs == 2
    assert row.called_strikes == 1
    assert row.fouls == 1
    assert row.strikeouts == 1
    assert row.whiff_rate == 2 / 3
    assert row.called_strike_rate == 1 / 4
    assert row.swing_rate == 3 / 4
    assert row.contact_rate == 1 / 3
    assert row.strikeout_rate == 1 / 2


def test_zero_swing_denominators_return_none():
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [_pitch(pitch_outcome_code="ball", is_terminal_pitch=True)],
    )

    row = result[0]
    assert row.whiff_rate is None
    assert row.contact_rate is None
    assert row.called_strike_rate == 0.0
    assert row.swing_rate == 0.0
    assert row.strikeout_rate == 0.0


def test_unknown_pitch_outcome_raises_value_error():
    connection = MagicMock()

    with pytest.raises(
        ValueError,
        match=(
            "No pitch-type effectiveness mapping found for pitch outcome "
            "code unknown_pitch_outcome."
        ),
    ):
        transform_player_pitch_type_effectiveness(
            connection,
            [_pitch(pitch_outcome_code="unknown_pitch_outcome")],
        )


def test_unknown_pa_outcome_raises_value_error():
    connection = MagicMock()

    with pytest.raises(
        ValueError,
        match=(
            "No pitch-type effectiveness mapping found for plate appearance "
            "outcome code unknown_pa_outcome."
        ),
    ):
        transform_player_pitch_type_effectiveness(
            connection,
            [_pitch(pa_outcome_code="unknown_pa_outcome")],
        )


def test_null_outcome_codes_count_only_pitches_and_plate_appearances():
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [
            _pitch(
                pitch_outcome_code=None,
                pa_outcome_code=None,
                is_terminal_pitch=True,
            )
        ],
    )

    assert result == [_row()]


@pytest.mark.parametrize(
    "pa_outcome_code",
    [
        "field_out",
        "intent_walk",
        "strikeout_double_play",
        "sac_fly_double_play",
        "triple_play",
    ],
)
def test_recognized_non_counted_pa_outcomes(pa_outcome_code: str):
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [
            _pitch(
                pitch_outcome_code="ball",
                pa_outcome_code=pa_outcome_code,
                is_terminal_pitch=True,
            )
        ],
    )

    assert result == [_row()]
    assert result[0].hits_allowed == 0
    assert result[0].strikeouts == 0
    assert result[0].walks == 0
    assert result[0].hit_by_pitch == 0


def test_results_are_sorted_by_player_and_pitch_type():
    connection = MagicMock()

    result = transform_player_pitch_type_effectiveness(
        connection,
        [
            _pitch(player_id=2, pitch_type_id=FASTBALL, is_terminal_pitch=True),
            _pitch(player_id=1, pitch_type_id=FASTBALL, is_terminal_pitch=True),
            _pitch(player_id=1, pitch_type_id=SLIDER, is_terminal_pitch=True),
        ],
    )

    assert [row.player_id for row in result] == [1, 1, 2]
    assert [row.pitch_type_id for row in result] == [SLIDER, FASTBALL, FASTBALL]


def test_transformation_does_not_manage_transactions():
    connection = MagicMock()

    transform_player_pitch_type_effectiveness(
        connection,
        [_pitch(is_terminal_pitch=True)],
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


def _clear_pitches(connection: Connection) -> None:
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


def _insert_pitch_type(connection: Connection, code: str, name: str) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.pitch_type (code, name)
            VALUES (:code, :name)
            RETURNING id
            """
        ),
        {"code": code, "name": name},
    ).scalar_one()


def _insert_pitch_outcome_type(connection: Connection, code: str, name: str) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.pitch_outcome_type (code, name)
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
    pitch_type_id: int | None = None,
    pitch_outcome_type_id: int | None = None,
) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO curated.pitch (
                plate_appearance_id,
                pitch_number,
                pitch_type_id,
                pitch_outcome_type_id
            )
            VALUES (
                :plate_appearance_id,
                :pitch_number,
                :pitch_type_id,
                :pitch_outcome_type_id
            )
            RETURNING pitch_id
            """
        ),
        {
            "plate_appearance_id": plate_appearance_id,
            "pitch_number": pitch_number,
            "pitch_type_id": pitch_type_id,
            "pitch_outcome_type_id": pitch_outcome_type_id,
        },
    ).scalar_one()


def _seed_lookups(
    connection: Connection,
    *,
    season_year: int,
    game_type_code: str,
    mlb_game_pk: int,
    batter_mlb_id: int,
    pitcher_mlb_id: int,
    batter_team_code: str,
    pitcher_team_code: str,
    outcome_code: str | None,
    pitch_type_code: str,
    pitch_outcome_code: str | None,
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
    pitch_type_id = _insert_pitch_type(connection, pitch_type_code, "Zeta Slider")
    pitch_outcome_type_id = (
        None
        if pitch_outcome_code is None
        else _insert_pitch_outcome_type(
            connection,
            pitch_outcome_code,
            "Zeta Ball",
        )
    )
    return {
        "game_id": game_id,
        "batter_id": batter_id,
        "pitcher_id": pitcher_id,
        "batter_team_id": batter_team_id,
        "pitcher_team_id": pitcher_team_id,
        "outcome_type_id": outcome_type_id,
        "pitch_type_id": pitch_type_id,
        "pitch_outcome_type_id": pitch_outcome_type_id,
    }


def test_extraction_empty_table_returns_empty_list():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_pitches(connection)

            assert get_player_pitch_type_effectiveness_pitches(connection) == []
    finally:
        engine.dispose()


def test_extraction_maps_joins_and_terminal_pitch():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_pitches(connection)
            ids = _seed_lookups(
                connection,
                season_year=2411,
                game_type_code="ZQA",
                mlb_game_pk=931001001,
                batter_mlb_id=888051101,
                pitcher_mlb_id=888051102,
                batter_team_code="ZQA",
                pitcher_team_code="ZQB",
                outcome_code="ZQA_STRIKEOUT",
                pitch_type_code="ZQA_SL",
                pitch_outcome_code="zqa_ball",
            )
            fastball_id = _insert_pitch_type(connection, "ZQA_FF", "Zeta Fastball")
            swinging_id = _insert_pitch_outcome_type(
                connection,
                "zqa_swinging_strike",
                "Zeta Swinging Strike",
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
                pitch_type_id=ids["pitch_type_id"],
                pitch_outcome_type_id=ids["pitch_outcome_type_id"],
            )
            _insert_pitch(
                connection,
                plate_appearance_id=plate_appearance_id,
                pitch_number=3,
                pitch_type_id=fastball_id,
                pitch_outcome_type_id=swinging_id,
            )
            _insert_pitch(
                connection,
                plate_appearance_id=plate_appearance_id,
                pitch_number=2,
                pitch_type_id=None,
                pitch_outcome_type_id=ids["pitch_outcome_type_id"],
            )

            result = get_player_pitch_type_effectiveness_pitches(connection)

            assert result == [
                PlayerPitchTypeEffectivenessPitch(
                    player_id=ids["pitcher_id"],
                    pitch_type_id=ids["pitch_type_id"],
                    plate_appearance_id=plate_appearance_id,
                    pitch_outcome_code="zqa_ball",
                    pa_outcome_code="ZQA_STRIKEOUT",
                    is_terminal_pitch=False,
                ),
                PlayerPitchTypeEffectivenessPitch(
                    player_id=ids["pitcher_id"],
                    pitch_type_id=fastball_id,
                    plate_appearance_id=plate_appearance_id,
                    pitch_outcome_code="zqa_swinging_strike",
                    pa_outcome_code="ZQA_STRIKEOUT",
                    is_terminal_pitch=True,
                ),
            ]
    finally:
        engine.dispose()


def test_extraction_null_outcome_codes_are_preserved():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_pitches(connection)
            ids = _seed_lookups(
                connection,
                season_year=2412,
                game_type_code="ZQB",
                mlb_game_pk=931001002,
                batter_mlb_id=888051201,
                pitcher_mlb_id=888051202,
                batter_team_code="ZQC",
                pitcher_team_code="ZQD",
                outcome_code=None,
                pitch_type_code="ZQB_CH",
                pitch_outcome_code=None,
            )
            plate_appearance_id = _insert_plate_appearance(
                connection,
                game_id=ids["game_id"],
                at_bat_number=1,
                batter_id=ids["batter_id"],
                pitcher_id=ids["pitcher_id"],
                batter_team_id=ids["batter_team_id"],
                pitcher_team_id=ids["pitcher_team_id"],
                outcome_type_id=None,
            )
            _insert_pitch(
                connection,
                plate_appearance_id=plate_appearance_id,
                pitch_number=1,
                pitch_type_id=ids["pitch_type_id"],
                pitch_outcome_type_id=None,
            )

            result = get_player_pitch_type_effectiveness_pitches(connection)

            assert result == [
                PlayerPitchTypeEffectivenessPitch(
                    player_id=ids["pitcher_id"],
                    pitch_type_id=ids["pitch_type_id"],
                    plate_appearance_id=plate_appearance_id,
                    pitch_outcome_code=None,
                    pa_outcome_code=None,
                    is_terminal_pitch=True,
                )
            ]
    finally:
        engine.dispose()


def test_extraction_does_not_manage_transactions():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_pitches(connection)
            ids = _seed_lookups(
                connection,
                season_year=2413,
                game_type_code="ZQC",
                mlb_game_pk=931001003,
                batter_mlb_id=888051301,
                pitcher_mlb_id=888051302,
                batter_team_code="ZQE",
                pitcher_team_code="ZQF",
                outcome_code="ZQC_WALK",
                pitch_type_code="ZQC_CU",
                pitch_outcome_code="zqc_ball",
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
                pitch_type_id=ids["pitch_type_id"],
                pitch_outcome_type_id=ids["pitch_outcome_type_id"],
            )

            original_commit = connection.commit
            original_begin = connection.begin
            commit_spy = MagicMock()
            begin_spy = MagicMock()
            connection.commit = commit_spy
            connection.begin = begin_spy
            try:
                result = get_player_pitch_type_effectiveness_pitches(connection)
            finally:
                connection.commit = original_commit
                connection.begin = original_begin

            assert len(result) == 1
            commit_spy.assert_not_called()
            begin_spy.assert_not_called()
    finally:
        engine.dispose()


def _seed_effectiveness_load_lookups(
    connection: Connection,
    *,
    player_mlb_id: int,
    pitch_type_code: str,
    extra_pitch_type_code: str | None = None,
) -> dict[str, int]:
    player_id = _insert_player(connection, player_mlb_id, "Pat Pitcher")
    pitch_type_id = _insert_pitch_type(connection, pitch_type_code, "Zeta Slider")
    ids = {"player_id": player_id, "pitch_type_id": pitch_type_id}
    if extra_pitch_type_code is not None:
        ids["extra_pitch_type_id"] = _insert_pitch_type(
            connection,
            extra_pitch_type_code,
            "Zeta Fastball",
        )
    return ids


def _fetch_player_pitch_type_effectiveness(
    connection: Connection,
    *,
    player_id: int,
    pitch_type_id: int,
):
    return (
        connection.execute(
            text(
                """
                SELECT *
                FROM analytics.player_pitch_type_effectiveness
                WHERE player_id = :player_id
                  AND pitch_type_id = :pitch_type_id
                """
            ),
            {"player_id": player_id, "pitch_type_id": pitch_type_id},
        )
        .mappings()
        .one()
    )


def _count_player_pitch_type_effectiveness(
    connection: Connection,
    *,
    player_id: int,
    pitch_type_id: int,
) -> int:
    return int(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM analytics.player_pitch_type_effectiveness
                WHERE player_id = :player_id
                  AND pitch_type_id = :pitch_type_id
                """
            ),
            {"player_id": player_id, "pitch_type_id": pitch_type_id},
        ).scalar_one()
    )


def _as_rate(value: object) -> float | None:
    return None if value is None else float(value)


def test_load_empty_input_returns_zero_and_does_not_execute():
    connection = MagicMock()

    result = load_player_pitch_type_effectiveness(connection, [])

    assert result == 0
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_load_inserts_a_single_row():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_effectiveness_load_lookups(
                connection,
                player_mlb_id=888061101,
                pitch_type_code="ZRA_SL",
            )
            row = _row(
                player_id=ids["player_id"],
                pitch_type_id=ids["pitch_type_id"],
                pitches=4,
                plate_appearances=1,
                swings=3,
                whiffs=1,
                called_strikes=1,
                balls_in_play=1,
                fouls=1,
                hits_allowed=1,
            )

            inserted = load_player_pitch_type_effectiveness(connection, [row])
            stored = _fetch_player_pitch_type_effectiveness(
                connection,
                player_id=ids["player_id"],
                pitch_type_id=ids["pitch_type_id"],
            )

            assert inserted == 1
            assert stored["player_id"] == ids["player_id"]
            assert stored["pitch_type_id"] == ids["pitch_type_id"]
            assert stored["pitches"] == 4
            assert stored["plate_appearances"] == 1
            assert stored["swings"] == 3
            assert stored["whiffs"] == 1
            assert stored["called_strikes"] == 1
            assert stored["balls_in_play"] == 1
            assert stored["fouls"] == 1
            assert stored["hits_allowed"] == 1
            assert _as_rate(stored["whiff_rate"]) == pytest.approx(1 / 3)
            assert _as_rate(stored["called_strike_rate"]) == pytest.approx(0.25)
            assert _as_rate(stored["swing_rate"]) == pytest.approx(0.75)
            assert _as_rate(stored["contact_rate"]) == pytest.approx(2 / 3)
            assert _as_rate(stored["strikeout_rate"]) == pytest.approx(0.0)
    finally:
        engine.dispose()


def test_load_inserts_multiple_rows():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_effectiveness_load_lookups(
                connection,
                player_mlb_id=888061201,
                pitch_type_code="ZRB_SL",
                extra_pitch_type_code="ZRB_FF",
            )
            rows = [
                _row(
                    player_id=ids["player_id"],
                    pitch_type_id=ids["pitch_type_id"],
                    pitches=2,
                    plate_appearances=1,
                    called_strikes=2,
                ),
                _row(
                    player_id=ids["player_id"],
                    pitch_type_id=ids["extra_pitch_type_id"],
                    pitches=1,
                    plate_appearances=1,
                    swings=1,
                    whiffs=1,
                    strikeouts=1,
                ),
            ]

            inserted = load_player_pitch_type_effectiveness(connection, rows)
            slider = _fetch_player_pitch_type_effectiveness(
                connection,
                player_id=ids["player_id"],
                pitch_type_id=ids["pitch_type_id"],
            )
            fastball = _fetch_player_pitch_type_effectiveness(
                connection,
                player_id=ids["player_id"],
                pitch_type_id=ids["extra_pitch_type_id"],
            )

            assert inserted == 2
            assert slider["called_strikes"] == 2
            assert _as_rate(slider["called_strike_rate"]) == pytest.approx(1.0)
            assert fastball["strikeouts"] == 1
            assert _as_rate(fastball["strikeout_rate"]) == pytest.approx(1.0)
    finally:
        engine.dispose()


def test_load_does_not_supply_created_at():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_effectiveness_load_lookups(
                connection,
                player_mlb_id=888061301,
                pitch_type_code="ZRC_SL",
            )
            row = _row(
                player_id=ids["player_id"],
                pitch_type_id=ids["pitch_type_id"],
            )

            payload = asdict(row)
            original_execute = connection.execute
            captured: list[object] = []

            def spy_execute(statement, *args, **kwargs):
                captured.append(statement)
                return original_execute(statement, *args, **kwargs)

            connection.execute = spy_execute
            try:
                inserted = load_player_pitch_type_effectiveness(connection, [row])
            finally:
                connection.execute = original_execute

            stored = _fetch_player_pitch_type_effectiveness(
                connection,
                player_id=ids["player_id"],
                pitch_type_id=ids["pitch_type_id"],
            )
            compiled = str(captured[0].compile(dialect=connection.dialect))

            assert inserted == 1
            assert "created_at" not in payload
            assert "created_at" not in compiled
            assert stored["created_at"] is not None
    finally:
        engine.dispose()


def test_load_upserts_existing_grain_to_current_metrics():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_effectiveness_load_lookups(
                connection,
                player_mlb_id=888061401,
                pitch_type_code="ZRD_SL",
            )
            original = _row(
                player_id=ids["player_id"],
                pitch_type_id=ids["pitch_type_id"],
                pitches=1,
                plate_appearances=1,
            )
            refreshed = _row(
                player_id=ids["player_id"],
                pitch_type_id=ids["pitch_type_id"],
                pitches=4,
                plate_appearances=2,
                swings=2,
                whiffs=2,
                called_strikes=2,
                strikeouts=1,
            )

            first = load_player_pitch_type_effectiveness(connection, [original])
            stored_before = _fetch_player_pitch_type_effectiveness(
                connection,
                player_id=ids["player_id"],
                pitch_type_id=ids["pitch_type_id"],
            )
            second = load_player_pitch_type_effectiveness(connection, [refreshed])
            stored_after = _fetch_player_pitch_type_effectiveness(
                connection,
                player_id=ids["player_id"],
                pitch_type_id=ids["pitch_type_id"],
            )

            assert first == 1
            assert second == 1
            assert (
                _count_player_pitch_type_effectiveness(
                    connection,
                    player_id=ids["player_id"],
                    pitch_type_id=ids["pitch_type_id"],
                )
                == 1
            )
            assert stored_before["pitches"] == 1
            assert stored_after["pitches"] == 4
            assert stored_after["plate_appearances"] == 2
            assert stored_after["swings"] == 2
            assert stored_after["whiffs"] == 2
            assert stored_after["called_strikes"] == 2
            assert stored_after["strikeouts"] == 1
            assert _as_rate(stored_after["whiff_rate"]) == pytest.approx(1.0)
            assert _as_rate(stored_after["called_strike_rate"]) == pytest.approx(0.5)
            assert _as_rate(stored_after["swing_rate"]) == pytest.approx(0.5)
            assert _as_rate(stored_after["contact_rate"]) == pytest.approx(0.0)
            assert _as_rate(stored_after["strikeout_rate"]) == pytest.approx(0.5)
            assert stored_after["created_at"] == stored_before["created_at"]
    finally:
        engine.dispose()


def test_load_persists_null_rates():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_effectiveness_load_lookups(
                connection,
                player_mlb_id=888061501,
                pitch_type_code="ZRE_SL",
            )
            row = _row(
                player_id=ids["player_id"],
                pitch_type_id=ids["pitch_type_id"],
                pitches=1,
                plate_appearances=1,
            )

            inserted = load_player_pitch_type_effectiveness(connection, [row])
            stored = _fetch_player_pitch_type_effectiveness(
                connection,
                player_id=ids["player_id"],
                pitch_type_id=ids["pitch_type_id"],
            )

            assert inserted == 1
            assert stored["whiff_rate"] is None
            assert stored["contact_rate"] is None
            assert _as_rate(stored["called_strike_rate"]) == pytest.approx(0.0)
            assert _as_rate(stored["swing_rate"]) == pytest.approx(0.0)
            assert _as_rate(stored["strikeout_rate"]) == pytest.approx(0.0)
    finally:
        engine.dispose()


def test_load_does_not_manage_transactions():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_effectiveness_load_lookups(
                connection,
                player_mlb_id=888061601,
                pitch_type_code="ZRF_SL",
            )
            row = _row(
                player_id=ids["player_id"],
                pitch_type_id=ids["pitch_type_id"],
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
                inserted = load_player_pitch_type_effectiveness(connection, [row])
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
