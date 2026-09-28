"""Tests for pitch-level extraction from raw Statcast data."""

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.curated.statcast_pitch_data import StatcastPitch, get_statcast_pitches
from app.ingestion.batch import create_ingestion_batch


_OPTIONAL_COLUMNS = frozenset(
    {
        "pitch_type",
        "description",
        "balls",
        "strikes",
        "zone",
        "plate_x",
        "plate_z",
        "sz_top",
        "sz_bot",
        "release_speed",
        "effective_speed",
        "release_spin_rate",
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
        "hit_distance_sc",
        "launch_speed",
        "launch_angle",
        "hyper_speed",
        "arm_angle",
        "attack_angle",
        "attack_direction",
        "swing_path_tilt",
        "intercept_ball_minus_batter_pos_x_inches",
        "intercept_ball_minus_batter_pos_y_inches",
    }
)

_OPTIONAL_STATCAST_PITCH_FIELDS = (
    "pitch_type_code",
    "pitch_outcome_code",
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


def _clear_statcast_pitches(connection: Connection) -> None:
    connection.execute(text("DELETE FROM raw.statcast_pitch"))


def _insert_pitch(
    connection: Connection,
    *,
    game_pk: int,
    at_bat_number: int = 1,
    pitch_number: int = 1,
    **columns: object,
) -> None:
    unknown = set(columns) - _OPTIONAL_COLUMNS
    if unknown:
        raise ValueError(f"Unsupported raw.statcast_pitch columns: {sorted(unknown)}")

    batch_id = create_ingestion_batch(
        connection,
        source_name=(
            "pytest_statcast_pitch_data_"
            f"{game_pk}_{at_bat_number}_{pitch_number}"
        ),
        started_at=datetime.now(timezone.utc),
    )
    column_names = [
        "ingestion_batch_id",
        "game_pk",
        "at_bat_number",
        "pitch_number",
        *columns,
    ]
    connection.execute(
        text(
            f"""
            INSERT INTO raw.statcast_pitch ({", ".join(column_names)})
            VALUES ({", ".join(f":{name}" for name in column_names)})
            """
        ),
        {
            "ingestion_batch_id": batch_id,
            "game_pk": game_pk,
            "at_bat_number": at_bat_number,
            "pitch_number": pitch_number,
            **columns,
        },
    )


def test_returns_one_record_per_source_pitch():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(connection, game_pk=900003001, at_bat_number=1, pitch_number=1)
            _insert_pitch(connection, game_pk=900003001, at_bat_number=1, pitch_number=2)

            result = get_statcast_pitches(connection)

            assert len(result) == 2
            assert all(isinstance(pitch, StatcastPitch) for pitch in result)
            assert {
                (pitch.mlb_game_pk, pitch.at_bat_number, pitch.pitch_number)
                for pitch in result
            } == {
                (900003001, 1, 1),
                (900003001, 1, 2),
            }
    finally:
        engine.dispose()


def test_maps_natural_key():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900003002,
                at_bat_number=4,
                pitch_number=3,
            )

            result = get_statcast_pitches(connection)

            assert len(result) == 1
            assert result[0].mlb_game_pk == 900003002
            assert result[0].at_bat_number == 4
            assert result[0].pitch_number == 3
    finally:
        engine.dispose()


def test_maps_pitch_type_code():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900003003,
                pitch_type="FF",
            )

            result = get_statcast_pitches(connection)

            assert len(result) == 1
            assert result[0].pitch_type_code == "FF"
    finally:
        engine.dispose()


def test_maps_pitch_outcome_code_from_description():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900003004,
                description="called_strike",
            )

            result = get_statcast_pitches(connection)

            assert len(result) == 1
            assert result[0].pitch_outcome_code == "called_strike"
    finally:
        engine.dispose()


def test_maps_count_and_location_fields():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900003005,
                balls=2,
                strikes=1,
                zone=5,
                plate_x=0.12,
                plate_z=2.45,
                sz_top=3.41,
                sz_bot=1.59,
            )

            result = get_statcast_pitches(connection)

            assert len(result) == 1
            assert result[0].balls == 2
            assert result[0].strikes == 1
            assert result[0].zone == 5
            assert result[0].plate_x == 0.12
            assert result[0].plate_z == 2.45
            assert result[0].sz_top == 3.41
            assert result[0].sz_bot == 1.59
    finally:
        engine.dispose()


def test_maps_pitch_physics_fields():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900003006,
                release_speed=95.2,
                effective_speed=94.8,
                release_spin_rate=2450.0,
                spin_axis=212.0,
                release_pos_x=-1.5,
                release_pos_y=54.1,
                release_pos_z=5.8,
                release_extension=6.4,
                pfx_x=-0.8,
                pfx_z=1.2,
                vx0=4.1,
                vy0=-132.0,
                vz0=-6.2,
                ax=-12.3,
                ay=28.4,
                az=-16.7,
            )

            result = get_statcast_pitches(connection)

            assert len(result) == 1
            assert result[0].release_speed == 95.2
            assert result[0].effective_speed == 94.8
            assert result[0].release_spin == 2450.0
            assert result[0].spin_axis == 212.0
            assert result[0].release_pos_x == -1.5
            assert result[0].release_pos_y == 54.1
            assert result[0].release_pos_z == 5.8
            assert result[0].release_extension == 6.4
            assert result[0].pfx_x == -0.8
            assert result[0].pfx_z == 1.2
            assert result[0].vx0 == 4.1
            assert result[0].vy0 == -132.0
            assert result[0].vz0 == -6.2
            assert result[0].ax == -12.3
            assert result[0].ay == 28.4
            assert result[0].az == -16.7
    finally:
        engine.dispose()


def test_maps_game_state_fields():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900003007,
                home_score=3,
                away_score=1,
                post_home_score=3,
                post_away_score=2,
                home_win_exp=0.72,
                bat_win_exp=0.28,
                delta_home_win_exp=-0.04,
                delta_run_exp=0.18,
            )

            result = get_statcast_pitches(connection)

            assert len(result) == 1
            assert result[0].home_score == 3
            assert result[0].away_score == 1
            assert result[0].post_home_score == 3
            assert result[0].post_away_score == 2
            assert result[0].home_win_exp == 0.72
            assert result[0].bat_win_exp == 0.28
            assert result[0].delta_home_win_exp == -0.04
            assert result[0].delta_run_exp == 0.18
    finally:
        engine.dispose()


def test_maps_expected_analytical_metrics():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900003008,
                estimated_ba_using_speedangle=0.62,
                estimated_woba_using_speedangle=0.91,
                woba_value=1.25,
            )

            result = get_statcast_pitches(connection)

            assert len(result) == 1
            assert result[0].estimated_ba_using_speedangle == 0.62
            assert result[0].estimated_woba_using_speedangle == 0.91
            assert result[0].woba_value == 1.25
    finally:
        engine.dispose()


def test_maps_batted_ball_fields():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900003009,
                hc_x=118.4,
                hc_y=98.2,
                hit_distance_sc=392.0,
                launch_speed=106.3,
                launch_angle=28.0,
                hyper_speed=107.1,
            )

            result = get_statcast_pitches(connection)

            assert len(result) == 1
            assert result[0].hc_x == 118.4
            assert result[0].hc_y == 98.2
            assert result[0].hit_distance == 392.0
            assert result[0].launch_speed == 106.3
            assert result[0].launch_angle == 28.0
            assert result[0].hyper_speed == 107.1
    finally:
        engine.dispose()


def test_maps_bat_tracking_fields():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(
                connection,
                game_pk=900003010,
                arm_angle=41.2,
                attack_angle=12.5,
                attack_direction=-4.8,
                swing_path_tilt=32.1,
                intercept_ball_minus_batter_pos_x_inches=6.4,
                intercept_ball_minus_batter_pos_y_inches=-2.1,
            )

            result = get_statcast_pitches(connection)

            assert len(result) == 1
            assert result[0].arm_angle == 41.2
            assert result[0].attack_angle == 12.5
            assert result[0].attack_direction == -4.8
            assert result[0].swing_path_tilt == 32.1
            assert result[0].intercept_ball_minus_batter_pos_x_inches == 6.4
            assert result[0].intercept_ball_minus_batter_pos_y_inches == -2.1
    finally:
        engine.dispose()


def test_preserves_null_source_values_as_none():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(connection, game_pk=900003011)

            result = get_statcast_pitches(connection)

            assert len(result) == 1
            for field_name in _OPTIONAL_STATCAST_PITCH_FIELDS:
                assert getattr(result[0], field_name) is None
    finally:
        engine.dispose()


def test_results_are_ordered_by_game_at_bat_and_pitch_number():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(connection, game_pk=900003014, at_bat_number=2, pitch_number=1)
            _insert_pitch(connection, game_pk=900003012, at_bat_number=1, pitch_number=2)
            _insert_pitch(connection, game_pk=900003012, at_bat_number=1, pitch_number=1)
            _insert_pitch(connection, game_pk=900003013, at_bat_number=3, pitch_number=1)
            _insert_pitch(connection, game_pk=900003012, at_bat_number=2, pitch_number=1)

            result = get_statcast_pitches(connection)

            assert [
                (pitch.mlb_game_pk, pitch.at_bat_number, pitch.pitch_number)
                for pitch in result
            ] == [
                (900003012, 1, 1),
                (900003012, 1, 2),
                (900003012, 2, 1),
                (900003013, 3, 1),
                (900003014, 2, 1),
            ]
    finally:
        engine.dispose()


def test_extraction_does_not_manage_transactions():
    engine = _create_engine()

    try:
        with _isolated_connection(engine) as connection:
            _clear_statcast_pitches(connection)
            _insert_pitch(connection, game_pk=900003015)
            connection.commit = MagicMock()
            connection.rollback = MagicMock()

            get_statcast_pitches(connection)

            connection.commit.assert_not_called()
            connection.rollback.assert_not_called()
    finally:
        engine.dispose()
