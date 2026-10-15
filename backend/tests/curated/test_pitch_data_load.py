"""Tests for the curated pitch persistence contract."""

from contextlib import contextmanager
from dataclasses import fields
from datetime import date
from unittest.mock import MagicMock

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from tests.db import create_test_engine
from app.curated import pitch_data as pitch_data_module
from app.curated.pitch_data import CuratedPitch


def load_pitches(*args, **kwargs):
    return pitch_data_module.load_pitches(*args, **kwargs)


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

_MEASUREMENTS = {
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


def _seed_required_lookups(
    connection: Connection,
    *,
    season_year: int,
    game_type_code: str,
    mlb_game_pk: int,
    pitch_type_code: str,
    pitch_outcome_code: str,
    batter_team_code: str,
    pitcher_team_code: str,
    batter_mlb_id: int,
    pitcher_mlb_id: int,
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
    batter_id = _insert_player(connection, batter_mlb_id, "Ada Batter")
    pitcher_id = _insert_player(connection, pitcher_mlb_id, "Pat Pitcher")
    batter_team_id = _insert_team(connection, batter_team_code, "Zeta Aces")
    pitcher_team_id = _insert_team(connection, pitcher_team_code, "Zeta Bats")
    plate_appearance_id = _insert_plate_appearance(
        connection,
        game_id=game_id,
        at_bat_number=1,
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
        "plate_appearance_id": plate_appearance_id,
        "pitch_type_id": pitch_type_id,
        "pitch_outcome_type_id": pitch_outcome_type_id,
    }


def _curated_pitch(
    *,
    plate_appearance_id: int,
    pitch_number: int = 1,
    pitch_type_id: int | None = None,
    pitch_outcome_type_id: int | None = None,
    **overrides: object,
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
    values.update(overrides)
    return CuratedPitch(
        plate_appearance_id=plate_appearance_id,
        pitch_number=pitch_number,
        pitch_type_id=pitch_type_id,
        pitch_outcome_type_id=pitch_outcome_type_id,
        **values,  # type: ignore[arg-type]
    )


def _fetch_pitch(
    connection: Connection,
    plate_appearance_id: int,
    pitch_number: int,
):
    return connection.execute(
        text(
            """
            SELECT
                pitch_id,
                plate_appearance_id,
                pitch_number,
                pitch_type_id,
                pitch_outcome_type_id,
                balls,
                strikes,
                zone,
                plate_x,
                plate_z,
                sz_top,
                sz_bot,
                release_speed,
                effective_speed,
                release_spin,
                spin_axis,
                release_pos_x,
                release_pos_y,
                release_pos_z,
                release_extension,
                pfx_x,
                pfx_z,
                vx0,
                vy0,
                vz0,
                ax,
                ay,
                az,
                home_score,
                away_score,
                post_home_score,
                post_away_score,
                home_win_exp,
                bat_win_exp,
                delta_home_win_exp,
                delta_run_exp,
                estimated_ba_using_speedangle,
                estimated_woba_using_speedangle,
                woba_value,
                hc_x,
                hc_y,
                hit_distance,
                launch_speed,
                launch_angle,
                hyper_speed,
                arm_angle,
                attack_angle,
                attack_direction,
                swing_path_tilt,
                intercept_ball_minus_batter_pos_x_inches,
                intercept_ball_minus_batter_pos_y_inches,
                created_at
            FROM curated.pitch
            WHERE plate_appearance_id = :plate_appearance_id
              AND pitch_number = :pitch_number
            """
        ),
        {
            "plate_appearance_id": plate_appearance_id,
            "pitch_number": pitch_number,
        },
    ).mappings().one()


def _count_pitches(connection: Connection, plate_appearance_id: int) -> int:
    return connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM curated.pitch
            WHERE plate_appearance_id = :plate_appearance_id
            """
        ),
        {"plate_appearance_id": plate_appearance_id},
    ).scalar_one()


def test_load_pitches_empty_input_returns_zero():
    connection = MagicMock()

    result = load_pitches(connection, [])

    assert result == 0
    connection.execute.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_load_pitches_inserts_single_pitch():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2131,
                game_type_code="ZVA",
                mlb_game_pk=900005001,
                pitch_type_code="ZVA_FF",
                pitch_outcome_code="zva_called_strike",
                batter_team_code="ZVA",
                pitcher_team_code="ZVB",
                batter_mlb_id=888015101,
                pitcher_mlb_id=888015102,
            )
            pitch = _curated_pitch(
                plate_appearance_id=ids["plate_appearance_id"],
                pitch_number=1,
                pitch_type_id=ids["pitch_type_id"],
                pitch_outcome_type_id=ids["pitch_outcome_type_id"],
            )

            result = load_pitches(connection, [pitch])

            assert result == 1
            assert _count_pitches(connection, ids["plate_appearance_id"]) == 1
            row = _fetch_pitch(connection, ids["plate_appearance_id"], 1)
            assert row["plate_appearance_id"] == ids["plate_appearance_id"]
            assert row["pitch_number"] == 1
            assert row["pitch_id"] is not None
            assert row["created_at"] is not None
    finally:
        engine.dispose()


def test_load_pitches_persists_measurement_fields():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2132,
                game_type_code="ZVB",
                mlb_game_pk=900005002,
                pitch_type_code="ZVB_SL",
                pitch_outcome_code="zvb_hit_into_play",
                batter_team_code="ZVC",
                pitcher_team_code="ZVD",
                batter_mlb_id=888015103,
                pitcher_mlb_id=888015104,
            )
            pitch = _curated_pitch(
                plate_appearance_id=ids["plate_appearance_id"],
                pitch_number=1,
                pitch_type_id=ids["pitch_type_id"],
                pitch_outcome_type_id=ids["pitch_outcome_type_id"],
                **_MEASUREMENTS,
            )

            result = load_pitches(connection, [pitch])

            assert result == 1
            row = _fetch_pitch(connection, ids["plate_appearance_id"], 1)
            for field_name in _MEASUREMENT_FIELDS:
                assert row[field_name] == _MEASUREMENTS[field_name]
    finally:
        engine.dispose()


def test_load_pitches_preserves_null_lookup_ids():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2133,
                game_type_code="ZVC",
                mlb_game_pk=900005003,
                pitch_type_code="ZVC_CH",
                pitch_outcome_code="zvc_ball",
                batter_team_code="ZVE",
                pitcher_team_code="ZVF",
                batter_mlb_id=888015105,
                pitcher_mlb_id=888015106,
            )
            pitch = _curated_pitch(
                plate_appearance_id=ids["plate_appearance_id"],
                pitch_number=1,
                pitch_type_id=None,
                pitch_outcome_type_id=None,
            )

            result = load_pitches(connection, [pitch])

            assert result == 1
            row = _fetch_pitch(connection, ids["plate_appearance_id"], 1)
            assert row["pitch_type_id"] is None
            assert row["pitch_outcome_type_id"] is None
    finally:
        engine.dispose()


def test_load_pitches_inserts_multiple_pitches():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2134,
                game_type_code="ZVD",
                mlb_game_pk=900005004,
                pitch_type_code="ZVD_CU",
                pitch_outcome_code="zvd_foul",
                batter_team_code="ZVG",
                pitcher_team_code="ZVH",
                batter_mlb_id=888015107,
                pitcher_mlb_id=888015108,
            )
            pitches = [
                _curated_pitch(
                    plate_appearance_id=ids["plate_appearance_id"],
                    pitch_number=1,
                    pitch_type_id=ids["pitch_type_id"],
                    pitch_outcome_type_id=ids["pitch_outcome_type_id"],
                    balls=0,
                    strikes=0,
                ),
                _curated_pitch(
                    plate_appearance_id=ids["plate_appearance_id"],
                    pitch_number=2,
                    pitch_type_id=ids["pitch_type_id"],
                    pitch_outcome_type_id=ids["pitch_outcome_type_id"],
                    balls=0,
                    strikes=1,
                ),
                _curated_pitch(
                    plate_appearance_id=ids["plate_appearance_id"],
                    pitch_number=3,
                    pitch_type_id=ids["pitch_type_id"],
                    pitch_outcome_type_id=ids["pitch_outcome_type_id"],
                    balls=1,
                    strikes=1,
                ),
            ]

            result = load_pitches(connection, pitches)

            assert result == 3
            assert _count_pitches(connection, ids["plate_appearance_id"]) == 3
            assert _fetch_pitch(connection, ids["plate_appearance_id"], 1)["balls"] == 0
            assert _fetch_pitch(connection, ids["plate_appearance_id"], 1)["strikes"] == 0
            assert _fetch_pitch(connection, ids["plate_appearance_id"], 2)["strikes"] == 1
            assert _fetch_pitch(connection, ids["plate_appearance_id"], 3)["balls"] == 1
            assert _fetch_pitch(connection, ids["plate_appearance_id"], 3)["strikes"] == 1
    finally:
        engine.dispose()


def test_load_pitches_skips_duplicate_natural_key():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2135,
                game_type_code="ZVE",
                mlb_game_pk=900005005,
                pitch_type_code="ZVE_SI",
                pitch_outcome_code="zve_called_strike",
                batter_team_code="ZVI",
                pitcher_team_code="ZVJ",
                batter_mlb_id=888015109,
                pitcher_mlb_id=888015110,
            )
            original = _curated_pitch(
                plate_appearance_id=ids["plate_appearance_id"],
                pitch_number=1,
                pitch_type_id=ids["pitch_type_id"],
                pitch_outcome_type_id=ids["pitch_outcome_type_id"],
                release_speed=95.2,
                balls=1,
            )
            duplicate = _curated_pitch(
                plate_appearance_id=ids["plate_appearance_id"],
                pitch_number=1,
                pitch_type_id=ids["pitch_type_id"],
                pitch_outcome_type_id=ids["pitch_outcome_type_id"],
                release_speed=88.4,
                balls=3,
            )

            first_result = load_pitches(connection, [original])
            original_row = _fetch_pitch(connection, ids["plate_appearance_id"], 1)
            second_result = load_pitches(connection, [duplicate])
            row = _fetch_pitch(connection, ids["plate_appearance_id"], 1)

            assert first_result == 1
            assert second_result == 0
            assert _count_pitches(connection, ids["plate_appearance_id"]) == 1
            assert row["pitch_id"] == original_row["pitch_id"]
            assert row["created_at"] == original_row["created_at"]
            assert row["release_speed"] == 95.2
            assert row["balls"] == 1
    finally:
        engine.dispose()


def test_load_pitches_return_count_is_newly_inserted_rows():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2136,
                game_type_code="ZVF",
                mlb_game_pk=900005006,
                pitch_type_code="ZVF_FC",
                pitch_outcome_code="zvf_swinging_strike",
                batter_team_code="ZVK",
                pitcher_team_code="ZVL",
                batter_mlb_id=888015111,
                pitcher_mlb_id=888015112,
            )
            pitches = [
                _curated_pitch(
                    plate_appearance_id=ids["plate_appearance_id"],
                    pitch_number=1,
                    pitch_type_id=ids["pitch_type_id"],
                    pitch_outcome_type_id=ids["pitch_outcome_type_id"],
                ),
                _curated_pitch(
                    plate_appearance_id=ids["plate_appearance_id"],
                    pitch_number=2,
                    pitch_type_id=ids["pitch_type_id"],
                    pitch_outcome_type_id=ids["pitch_outcome_type_id"],
                ),
            ]

            first_result = load_pitches(connection, pitches)
            second_result = load_pitches(connection, pitches)

            assert first_result == 2
            assert second_result == 0
            assert _count_pitches(connection, ids["plate_appearance_id"]) == 2
    finally:
        engine.dispose()


def test_load_pitches_does_not_manage_transactions():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            ids = _seed_required_lookups(
                connection,
                season_year=2137,
                game_type_code="ZVG",
                mlb_game_pk=900005007,
                pitch_type_code="ZVG_FF",
                pitch_outcome_code="zvg_ball",
                batter_team_code="ZVM",
                pitcher_team_code="ZVN",
                batter_mlb_id=888015113,
                pitcher_mlb_id=888015114,
            )
            connection.commit = MagicMock()
            connection.rollback = MagicMock()

            load_pitches(
                connection,
                [_curated_pitch(
                    plate_appearance_id=ids["plate_appearance_id"],
                    pitch_number=1,
                    pitch_type_id=ids["pitch_type_id"],
                    pitch_outcome_type_id=ids["pitch_outcome_type_id"],
                )],
            )

            connection.commit.assert_not_called()
            connection.rollback.assert_not_called()
    finally:
        engine.dispose()
