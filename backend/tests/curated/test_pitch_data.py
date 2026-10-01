"""Tests for Statcast pitch transformation into curated records."""

from contextlib import contextmanager
from dataclasses import fields
from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.curated.pitch_data import (
    CuratedPitch,
    _PITCH_INSERT_BATCH_SIZE,
    load_pitches,
    transform_pitches,
)
from app.curated.statcast_pitch_data import StatcastPitch


_MEASUREMENT_FIELDS = (
    "balls",
    "strikes",
    "zone",
    "plate_x",
    "plate_z",
    "sz_top",
    "sz_bot",
    "release_speed",
    "effective_speed",
    "release_spin",
    "spin_axis",
    "release_pos_x",
    "release_pos_y",
    "release_pos_z",
    "release_extension",
    "pfx_x",
    "pfx_z",
    "vx0",
    "vy0",
    "vz0",
    "ax",
    "ay",
    "az",
    "home_score",
    "away_score",
    "post_home_score",
    "post_away_score",
    "home_win_exp",
    "bat_win_exp",
    "delta_home_win_exp",
    "delta_run_exp",
    "estimated_ba_using_speedangle",
    "estimated_woba_using_speedangle",
    "woba_value",
    "hc_x",
    "hc_y",
    "hit_distance",
    "launch_speed",
    "launch_angle",
    "hyper_speed",
    "arm_angle",
    "attack_angle",
    "attack_direction",
    "swing_path_tilt",
    "intercept_ball_minus_batter_pos_x_inches",
    "intercept_ball_minus_batter_pos_y_inches",
)


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


def _insert_plate_appearance(
    connection: Connection,
    *,
    game_id: int,
    at_bat_number: int,
    batter_id: int,
    pitcher_id: int,
    batter_team_id: int,
    pitcher_team_id: int,
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
        },
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


def _statcast_pitch(**overrides: object) -> StatcastPitch:
    values: dict[str, object] = {
        field.name: None
        for field in fields(StatcastPitch)
        if field.name not in {"mlb_game_pk", "at_bat_number", "pitch_number"}
    }
    values["at_bat_number"] = 1
    values["pitch_number"] = 1
    values.update(overrides)
    return StatcastPitch(**values)  # type: ignore[arg-type]


def _curated_pitch(
    *,
    plate_appearance_id: int,
    pitch_number: int,
    pitch_type_id: int | None = None,
    pitch_outcome_type_id: int | None = None,
) -> CuratedPitch:
    values: dict[str, object] = {
        field.name: None
        for field in fields(CuratedPitch)
        if field.name
        not in {
            "plate_appearance_id",
            "pitch_number",
            "pitch_type_id",
            "pitch_outcome_type_id",
        }
    }
    return CuratedPitch(
        plate_appearance_id=plate_appearance_id,
        pitch_number=pitch_number,
        pitch_type_id=pitch_type_id,
        pitch_outcome_type_id=pitch_outcome_type_id,
        **values,  # type: ignore[arg-type]
    )


def _seed_required_lookups(
    connection: Connection,
    *,
    season_year: int,
    game_type_code: str,
    mlb_game_pk: int,
    at_bat_number: int = 1,
    pitch_type_code: str = "ZUA_FF",
    pitch_outcome_code: str = "zua_called_strike",
    batter_team_code: str = "ZUA",
    pitcher_team_code: str = "ZUB",
) -> dict[str, int]:
    season_id = _insert_season(connection, season_year)
    game_type_id = _insert_game_type(connection, game_type_code, "Zeta Regular")
    game_id = _insert_game(
        connection,
        mlb_game_pk=mlb_game_pk,
        season_id=season_id,
        game_type_id=game_type_id,
        official_game_date=date(season_year, 4, 8),
    )
    batter_id = _insert_player(connection, 888014101, "Ada Batter")
    pitcher_id = _insert_player(connection, 888014102, "Pat Pitcher")
    batter_team_id = _insert_team(connection, batter_team_code, "Zeta Aces")
    pitcher_team_id = _insert_team(connection, pitcher_team_code, "Zeta Bats")
    plate_appearance_id = _insert_plate_appearance(
        connection,
        game_id=game_id,
        at_bat_number=at_bat_number,
        batter_id=batter_id,
        pitcher_id=pitcher_id,
        batter_team_id=batter_team_id,
        pitcher_team_id=pitcher_team_id,
    )
    pitch_type_id = _insert_pitch_type(connection, pitch_type_code, "Zeta Fastball")
    pitch_outcome_type_id = _insert_pitch_outcome_type(
        connection,
        pitch_outcome_code,
        "Zeta Called Strike",
    )
    return {
        "game_id": game_id,
        "batter_id": batter_id,
        "pitcher_id": pitcher_id,
        "batter_team_id": batter_team_id,
        "pitcher_team_id": pitcher_team_id,
        "plate_appearance_id": plate_appearance_id,
        "pitch_type_id": pitch_type_id,
        "pitch_outcome_type_id": pitch_outcome_type_id,
    }


def test_successful_pitch_transformation():
    engine = _create_engine()
    mlb_game_pk = 900004001

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2111,
                game_type_code="ZUA",
                mlb_game_pk=mlb_game_pk,
            )
            extracted = _statcast_pitch(
                mlb_game_pk=mlb_game_pk,
                pitch_number=2,
                pitch_type_code="ZUA_FF",
                pitch_outcome_code="zua_called_strike",
                balls=1,
                strikes=1,
            )

            result = transform_pitches(connection, [extracted])

            assert result == [
                CuratedPitch(
                    plate_appearance_id=ids["plate_appearance_id"],
                    pitch_number=2,
                    pitch_type_id=ids["pitch_type_id"],
                    pitch_outcome_type_id=ids["pitch_outcome_type_id"],
                    balls=1,
                    strikes=1,
                    zone=None,
                    plate_x=None,
                    plate_z=None,
                    sz_top=None,
                    sz_bot=None,
                    release_speed=None,
                    effective_speed=None,
                    release_spin=None,
                    spin_axis=None,
                    release_pos_x=None,
                    release_pos_y=None,
                    release_pos_z=None,
                    release_extension=None,
                    pfx_x=None,
                    pfx_z=None,
                    vx0=None,
                    vy0=None,
                    vz0=None,
                    ax=None,
                    ay=None,
                    az=None,
                    home_score=None,
                    away_score=None,
                    post_home_score=None,
                    post_away_score=None,
                    home_win_exp=None,
                    bat_win_exp=None,
                    delta_home_win_exp=None,
                    delta_run_exp=None,
                    estimated_ba_using_speedangle=None,
                    estimated_woba_using_speedangle=None,
                    woba_value=None,
                    hc_x=None,
                    hc_y=None,
                    hit_distance=None,
                    launch_speed=None,
                    launch_angle=None,
                    hyper_speed=None,
                    arm_angle=None,
                    attack_angle=None,
                    attack_direction=None,
                    swing_path_tilt=None,
                    intercept_ball_minus_batter_pos_x_inches=None,
                    intercept_ball_minus_batter_pos_y_inches=None,
                )
            ]
    finally:
        engine.dispose()


def test_resolves_plate_appearance_id():
    engine = _create_engine()
    mlb_game_pk = 900004002

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2112,
                game_type_code="ZUB",
                mlb_game_pk=mlb_game_pk,
                at_bat_number=4,
                pitch_type_code="ZUB_FF",
                pitch_outcome_code="zub_ball",
                batter_team_code="ZUC",
                pitcher_team_code="ZUD",
            )

            result = transform_pitches(
                connection,
                [_statcast_pitch(
                    mlb_game_pk=mlb_game_pk,
                    at_bat_number=4,
                    pitch_type_code="ZUB_FF",
                    pitch_outcome_code="zub_ball",
                )],
            )

            assert len(result) == 1
            assert result[0].plate_appearance_id == ids["plate_appearance_id"]
    finally:
        engine.dispose()


def test_resolves_pitch_type_id():
    engine = _create_engine()
    mlb_game_pk = 900004003

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2113,
                game_type_code="ZUC",
                mlb_game_pk=mlb_game_pk,
                pitch_type_code="ZUC_SL",
                pitch_outcome_code="zuc_foul",
                batter_team_code="ZUE",
                pitcher_team_code="ZUF",
            )

            result = transform_pitches(
                connection,
                [_statcast_pitch(
                    mlb_game_pk=mlb_game_pk,
                    pitch_type_code="ZUC_SL",
                    pitch_outcome_code="zuc_foul",
                )],
            )

            assert len(result) == 1
            assert result[0].pitch_type_id == ids["pitch_type_id"]
    finally:
        engine.dispose()


def test_resolves_pitch_outcome_type_id():
    engine = _create_engine()
    mlb_game_pk = 900004004

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2114,
                game_type_code="ZUD",
                mlb_game_pk=mlb_game_pk,
                pitch_type_code="ZUD_CH",
                pitch_outcome_code="zud_swinging_strike",
                batter_team_code="ZUG",
                pitcher_team_code="ZUH",
            )

            result = transform_pitches(
                connection,
                [_statcast_pitch(
                    mlb_game_pk=mlb_game_pk,
                    pitch_type_code="ZUD_CH",
                    pitch_outcome_code="zud_swinging_strike",
                )],
            )

            assert len(result) == 1
            assert result[0].pitch_outcome_type_id == ids["pitch_outcome_type_id"]
    finally:
        engine.dispose()


def test_null_pitch_type_remains_none():
    engine = _create_engine()
    mlb_game_pk = 900004005

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2115,
                game_type_code="ZUE",
                mlb_game_pk=mlb_game_pk,
                pitch_type_code="ZUE_CU",
                pitch_outcome_code="zue_blocked_ball",
                batter_team_code="ZUI",
                pitcher_team_code="ZUJ",
            )

            result = transform_pitches(
                connection,
                [_statcast_pitch(
                    mlb_game_pk=mlb_game_pk,
                    pitch_type_code=None,
                    pitch_outcome_code="zue_blocked_ball",
                )],
            )

            assert len(result) == 1
            assert result[0].pitch_type_id is None
    finally:
        engine.dispose()


def test_null_pitch_outcome_remains_none():
    engine = _create_engine()
    mlb_game_pk = 900004006

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2116,
                game_type_code="ZUF",
                mlb_game_pk=mlb_game_pk,
                pitch_type_code="ZUF_SI",
                pitch_outcome_code="zuf_hit_into_play",
                batter_team_code="ZUK",
                pitcher_team_code="ZUL",
            )

            result = transform_pitches(
                connection,
                [_statcast_pitch(
                    mlb_game_pk=mlb_game_pk,
                    pitch_type_code="ZUF_SI",
                    pitch_outcome_code=None,
                )],
            )

            assert len(result) == 1
            assert result[0].pitch_outcome_type_id is None
    finally:
        engine.dispose()


def test_unresolved_game_raises_value_error():
    engine = _create_engine()
    missing_game_pk = 900004099

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2117,
                game_type_code="ZUG",
                mlb_game_pk=900004007,
                pitch_type_code="ZUG_FC",
                pitch_outcome_code="zug_foul_tip",
                batter_team_code="ZUM",
                pitcher_team_code="ZUN",
            )

            with pytest.raises(
                ValueError,
                match=rf"No curated game found for MLB game PK {missing_game_pk}",
            ):
                transform_pitches(
                    connection,
                    [_statcast_pitch(
                        mlb_game_pk=missing_game_pk,
                        pitch_type_code="ZUG_FC",
                        pitch_outcome_code="zug_foul_tip",
                    )],
                )
    finally:
        engine.dispose()


def test_unresolved_plate_appearance_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900004008
    missing_at_bat_number = 9

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2118,
                game_type_code="ZUH",
                mlb_game_pk=mlb_game_pk,
                at_bat_number=1,
                pitch_type_code="ZUH_ST",
                pitch_outcome_code="zuh_hit_by_pitch",
                batter_team_code="ZUO",
                pitcher_team_code="ZUP",
            )

            with pytest.raises(
                ValueError,
                match=(
                    rf"No curated plate appearance found for MLB game PK "
                    rf"{mlb_game_pk}, at_bat_number {missing_at_bat_number}"
                ),
            ):
                transform_pitches(
                    connection,
                    [_statcast_pitch(
                        mlb_game_pk=mlb_game_pk,
                        at_bat_number=missing_at_bat_number,
                        pitch_type_code="ZUH_ST",
                        pitch_outcome_code="zuh_hit_by_pitch",
                    )],
                )
    finally:
        engine.dispose()


def test_unresolved_pitch_type_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900004009
    missing_code = "ZZZ_MISSING_PITCH_TYPE"

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2119,
                game_type_code="ZUI",
                mlb_game_pk=mlb_game_pk,
                pitch_type_code="ZUI_FS",
                pitch_outcome_code="zui_missed_bunt",
                batter_team_code="ZUQ",
                pitcher_team_code="ZUR",
            )

            with pytest.raises(
                ValueError,
                match=(
                    rf"No curated pitch type found for pitch type code "
                    rf"{missing_code}"
                ),
            ):
                transform_pitches(
                    connection,
                    [_statcast_pitch(
                        mlb_game_pk=mlb_game_pk,
                        pitch_type_code=missing_code,
                        pitch_outcome_code="zui_missed_bunt",
                    )],
                )
    finally:
        engine.dispose()


def test_unresolved_pitch_outcome_raises_value_error():
    engine = _create_engine()
    mlb_game_pk = 900004010
    missing_code = "zzz_missing_pitch_outcome"

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2120,
                game_type_code="ZUJ",
                mlb_game_pk=mlb_game_pk,
                pitch_type_code="ZUJ_KC",
                pitch_outcome_code="zuj_automatic_ball",
                batter_team_code="ZUS",
                pitcher_team_code="ZUT",
            )

            with pytest.raises(
                ValueError,
                match=(
                    rf"No curated pitch outcome type found for pitch outcome "
                    rf"code {missing_code}"
                ),
            ):
                transform_pitches(
                    connection,
                    [_statcast_pitch(
                        mlb_game_pk=mlb_game_pk,
                        pitch_type_code="ZUJ_KC",
                        pitch_outcome_code=missing_code,
                    )],
                )
    finally:
        engine.dispose()


def test_preserves_pitch_measurement_fields():
    engine = _create_engine()
    mlb_game_pk = 900004011
    measurements = {
        "balls": 2,
        "strikes": 1,
        "zone": 5,
        "plate_x": 0.12,
        "plate_z": 2.45,
        "sz_top": 3.41,
        "sz_bot": 1.59,
        "release_speed": 95.2,
        "effective_speed": 94.8,
        "release_spin": 2450.0,
        "spin_axis": 212.0,
        "release_pos_x": -1.5,
        "release_pos_y": 54.1,
        "release_pos_z": 5.8,
        "release_extension": 6.4,
        "pfx_x": -0.8,
        "pfx_z": 1.2,
        "vx0": 4.1,
        "vy0": -132.0,
        "vz0": -6.2,
        "ax": -12.3,
        "ay": 28.4,
        "az": -16.7,
        "home_score": 3,
        "away_score": 1,
        "post_home_score": 3,
        "post_away_score": 2,
        "home_win_exp": 0.72,
        "bat_win_exp": 0.28,
        "delta_home_win_exp": -0.04,
        "delta_run_exp": 0.18,
        "estimated_ba_using_speedangle": 0.62,
        "estimated_woba_using_speedangle": 0.91,
        "woba_value": 1.25,
        "hc_x": 118.4,
        "hc_y": 98.2,
        "hit_distance": 392.0,
        "launch_speed": 106.3,
        "launch_angle": 28.0,
        "hyper_speed": 107.1,
        "arm_angle": 41.2,
        "attack_angle": 12.5,
        "attack_direction": -4.8,
        "swing_path_tilt": 32.1,
        "intercept_ball_minus_batter_pos_x_inches": 6.4,
        "intercept_ball_minus_batter_pos_y_inches": -2.1,
    }

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2121,
                game_type_code="ZUK",
                mlb_game_pk=mlb_game_pk,
                pitch_type_code="ZUK_FF",
                pitch_outcome_code="zuk_hit_into_play",
                batter_team_code="ZUU",
                pitcher_team_code="ZUV",
            )
            extracted = _statcast_pitch(
                mlb_game_pk=mlb_game_pk,
                pitch_type_code="ZUK_FF",
                pitch_outcome_code="zuk_hit_into_play",
                **measurements,
            )

            result = transform_pitches(connection, [extracted])

            assert len(result) == 1
            for field_name in _MEASUREMENT_FIELDS:
                assert getattr(result[0], field_name) == measurements[field_name]
    finally:
        engine.dispose()


def test_multiple_pitches_preserve_input_order():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            first = _seed_required_lookups(
                connection,
                season_year=2122,
                game_type_code="ZUL",
                mlb_game_pk=900004012,
                at_bat_number=1,
                pitch_type_code="ZUL_FF",
                pitch_outcome_code="zul_called_strike",
                batter_team_code="ZUW",
                pitcher_team_code="ZUX",
            )
            second_pa_id = _insert_plate_appearance(
                connection,
                game_id=first["game_id"],
                at_bat_number=2,
                batter_id=first["batter_id"],
                pitcher_id=first["pitcher_id"],
                batter_team_id=first["batter_team_id"],
                pitcher_team_id=first["pitcher_team_id"],
            )
            extracted = [
                _statcast_pitch(
                    mlb_game_pk=900004012,
                    at_bat_number=2,
                    pitch_number=1,
                    pitch_type_code="ZUL_FF",
                    pitch_outcome_code="zul_called_strike",
                ),
                _statcast_pitch(
                    mlb_game_pk=900004012,
                    at_bat_number=1,
                    pitch_number=3,
                    pitch_type_code="ZUL_FF",
                    pitch_outcome_code="zul_called_strike",
                ),
            ]

            result = transform_pitches(connection, extracted)

            assert [
                (pitch.plate_appearance_id, pitch.pitch_number) for pitch in result
            ] == [
                (second_pa_id, 1),
                (first["plate_appearance_id"], 3),
            ]
    finally:
        engine.dispose()


def test_transformation_does_not_manage_transactions():
    engine = _create_engine()
    mlb_game_pk = 900004013

    try:
        with _isolated_connection(engine) as connection:
            _seed_required_lookups(
                connection,
                season_year=2123,
                game_type_code="ZUM",
                mlb_game_pk=mlb_game_pk,
                pitch_type_code="ZUM_FF",
                pitch_outcome_code="zum_ball",
                batter_team_code="ZUY",
                pitcher_team_code="ZUZ",
            )
            connection.commit = MagicMock()
            connection.rollback = MagicMock()

            transform_pitches(
                connection,
                [_statcast_pitch(
                    mlb_game_pk=mlb_game_pk,
                    pitch_type_code="ZUM_FF",
                    pitch_outcome_code="zum_ball",
                )],
            )

            connection.commit.assert_not_called()
            connection.rollback.assert_not_called()
    finally:
        engine.dispose()


def test_load_pitches_inserts_more_than_one_batch():
    engine = _create_engine()
    pitch_count = _PITCH_INSERT_BATCH_SIZE + 1

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2188,
                game_type_code="ZWA",
                mlb_game_pk=900009001,
                pitch_type_code="ZWA_FF",
                pitch_outcome_code="zwa_called_strike",
                batter_team_code="ZWA",
                pitcher_team_code="ZWB",
            )
            pitches = [
                _curated_pitch(
                    plate_appearance_id=ids["plate_appearance_id"],
                    pitch_number=pitch_number,
                    pitch_type_id=ids["pitch_type_id"],
                    pitch_outcome_type_id=ids["pitch_outcome_type_id"],
                )
                for pitch_number in range(1, pitch_count + 1)
            ]

            result = load_pitches(connection, pitches)
            stored = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM curated.pitch
                    WHERE plate_appearance_id = :plate_appearance_id
                    """
                ),
                {"plate_appearance_id": ids["plate_appearance_id"]},
            ).scalar_one()

            assert result == pitch_count
            assert stored == pitch_count
    finally:
        engine.dispose()
