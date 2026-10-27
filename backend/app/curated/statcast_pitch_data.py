"""Extract pitch-level records from raw Statcast pitch data."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy import MetaData, Table, select, tuple_
from sqlalchemy.engine import Connection
from sqlalchemy.sql import Select

PITCH_EXTRACT_CHUNK_SIZE = 10000
PitchKey = tuple[int, int, int]


@dataclass(frozen=True)
class StatcastPitch:
    mlb_game_pk: int
    at_bat_number: int
    pitch_number: int
    pitch_type_code: str | None
    pitch_outcome_code: str | None
    balls: int | None
    strikes: int | None
    zone: int | None
    plate_x: float | None
    plate_z: float | None
    sz_top: float | None
    sz_bot: float | None
    release_speed: float | None
    effective_speed: float | None
    release_spin: float | None
    spin_axis: float | None
    release_pos_x: float | None
    release_pos_y: float | None
    release_pos_z: float | None
    release_extension: float | None
    pfx_x: float | None
    pfx_z: float | None
    vx0: float | None
    vy0: float | None
    vz0: float | None
    ax: float | None
    ay: float | None
    az: float | None
    home_score: int | None
    away_score: int | None
    post_home_score: int | None
    post_away_score: int | None
    home_win_exp: float | None
    bat_win_exp: float | None
    delta_home_win_exp: float | None
    delta_run_exp: float | None
    estimated_ba_using_speedangle: float | None
    estimated_woba_using_speedangle: float | None
    woba_value: float | None
    hc_x: float | None
    hc_y: float | None
    hit_distance: float | None
    launch_speed: float | None
    launch_angle: float | None
    hyper_speed: float | None
    arm_angle: float | None
    attack_angle: float | None
    attack_direction: float | None
    swing_path_tilt: float | None
    intercept_ball_minus_batter_pos_x_inches: float | None
    intercept_ball_minus_batter_pos_y_inches: float | None


def iter_statcast_pitch_chunks(
    connection: Connection,
    *,
    chunk_size: int = PITCH_EXTRACT_CHUNK_SIZE,
) -> Iterator[list[StatcastPitch]]:
    """Yield bounded chunks of Statcast pitches in natural-key order.

    Uses keyset pagination on ``(game_pk, at_bat_number, pitch_number)``
    so each query is a complete ``LIMIT`` fetch. Lookups and inserts on
    the same connection cannot invalidate an open streaming cursor
    because no cursor is held between chunks. There is no season or
    year filter. The caller owns the transaction.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")

    statcast_pitch = _statcast_pitch_table(connection)
    after: PitchKey | None = None
    while True:
        rows = connection.execute(
            _statcast_pitch_chunk_statement(
                statcast_pitch,
                after=after,
                chunk_size=chunk_size,
            )
        ).all()
        if not rows:
            return
        chunk = [_row_to_statcast_pitch(row) for row in rows]
        yield chunk
        if len(chunk) < chunk_size:
            return
        last = chunk[-1]
        after = (last.mlb_game_pk, last.at_bat_number, last.pitch_number)


def get_statcast_pitches(connection: Connection) -> list[StatcastPitch]:
    """Return one StatcastPitch per raw.statcast_pitch row.

    Small-result convenience over ``iter_statcast_pitch_chunks``. Large
    loads should iterate chunks instead of calling this function.
    Source values are preserved. The caller owns the transaction.
    """
    pitches: list[StatcastPitch] = []
    for chunk in iter_statcast_pitch_chunks(connection):
        pitches.extend(chunk)
    return pitches


def _statcast_pitch_table(connection: Connection) -> Table:
    metadata = MetaData()
    return Table(
        "statcast_pitch",
        metadata,
        schema="raw",
        autoload_with=connection,
    )


def _statcast_pitch_chunk_statement(
    statcast_pitch: Table,
    *,
    after: PitchKey | None,
    chunk_size: int,
) -> Select:
    statement = select(
            statcast_pitch.c.game_pk,
            statcast_pitch.c.at_bat_number,
            statcast_pitch.c.pitch_number,
            statcast_pitch.c.pitch_type,
            statcast_pitch.c.description,
            statcast_pitch.c.balls,
            statcast_pitch.c.strikes,
            statcast_pitch.c.zone,
            statcast_pitch.c.plate_x,
            statcast_pitch.c.plate_z,
            statcast_pitch.c.sz_top,
            statcast_pitch.c.sz_bot,
            statcast_pitch.c.release_speed,
            statcast_pitch.c.effective_speed,
            statcast_pitch.c.release_spin_rate,
            statcast_pitch.c.spin_axis,
            statcast_pitch.c.release_pos_x,
            statcast_pitch.c.release_pos_y,
            statcast_pitch.c.release_pos_z,
            statcast_pitch.c.release_extension,
            statcast_pitch.c.pfx_x,
            statcast_pitch.c.pfx_z,
            statcast_pitch.c.vx0,
            statcast_pitch.c.vy0,
            statcast_pitch.c.vz0,
            statcast_pitch.c.ax,
            statcast_pitch.c.ay,
            statcast_pitch.c.az,
            statcast_pitch.c.home_score,
            statcast_pitch.c.away_score,
            statcast_pitch.c.post_home_score,
            statcast_pitch.c.post_away_score,
            statcast_pitch.c.home_win_exp,
            statcast_pitch.c.bat_win_exp,
            statcast_pitch.c.delta_home_win_exp,
            statcast_pitch.c.delta_run_exp,
            statcast_pitch.c.estimated_ba_using_speedangle,
            statcast_pitch.c.estimated_woba_using_speedangle,
            statcast_pitch.c.woba_value,
            statcast_pitch.c.hc_x,
            statcast_pitch.c.hc_y,
            statcast_pitch.c.hit_distance_sc,
            statcast_pitch.c.launch_speed,
            statcast_pitch.c.launch_angle,
            statcast_pitch.c.hyper_speed,
            statcast_pitch.c.arm_angle,
            statcast_pitch.c.attack_angle,
            statcast_pitch.c.attack_direction,
            statcast_pitch.c.swing_path_tilt,
            statcast_pitch.c.intercept_ball_minus_batter_pos_x_inches,
            statcast_pitch.c.intercept_ball_minus_batter_pos_y_inches,
        ).order_by(
            statcast_pitch.c.game_pk,
            statcast_pitch.c.at_bat_number,
            statcast_pitch.c.pitch_number,
        ).limit(chunk_size)
    if after is not None:
        statement = statement.where(
            tuple_(
                statcast_pitch.c.game_pk,
                statcast_pitch.c.at_bat_number,
                statcast_pitch.c.pitch_number,
            )
            > after
        )
    return statement


def _row_to_statcast_pitch(row: Any) -> StatcastPitch:
    return StatcastPitch(
            mlb_game_pk=int(row.game_pk),
            at_bat_number=int(row.at_bat_number),
            pitch_number=int(row.pitch_number),
            pitch_type_code=_optional_str(row.pitch_type),
            pitch_outcome_code=_optional_str(row.description),
            balls=_optional_int(row.balls),
            strikes=_optional_int(row.strikes),
            zone=_optional_int(row.zone),
            plate_x=_optional_float(row.plate_x),
            plate_z=_optional_float(row.plate_z),
            sz_top=_optional_float(row.sz_top),
            sz_bot=_optional_float(row.sz_bot),
            release_speed=_optional_float(row.release_speed),
            effective_speed=_optional_float(row.effective_speed),
            release_spin=_optional_float(row.release_spin_rate),
            spin_axis=_optional_float(row.spin_axis),
            release_pos_x=_optional_float(row.release_pos_x),
            release_pos_y=_optional_float(row.release_pos_y),
            release_pos_z=_optional_float(row.release_pos_z),
            release_extension=_optional_float(row.release_extension),
            pfx_x=_optional_float(row.pfx_x),
            pfx_z=_optional_float(row.pfx_z),
            vx0=_optional_float(row.vx0),
            vy0=_optional_float(row.vy0),
            vz0=_optional_float(row.vz0),
            ax=_optional_float(row.ax),
            ay=_optional_float(row.ay),
            az=_optional_float(row.az),
            home_score=_optional_int(row.home_score),
            away_score=_optional_int(row.away_score),
            post_home_score=_optional_int(row.post_home_score),
            post_away_score=_optional_int(row.post_away_score),
            home_win_exp=_optional_float(row.home_win_exp),
            bat_win_exp=_optional_float(row.bat_win_exp),
            delta_home_win_exp=_optional_float(row.delta_home_win_exp),
            delta_run_exp=_optional_float(row.delta_run_exp),
            estimated_ba_using_speedangle=_optional_float(
                row.estimated_ba_using_speedangle
            ),
            estimated_woba_using_speedangle=_optional_float(
                row.estimated_woba_using_speedangle
            ),
            woba_value=_optional_float(row.woba_value),
            hc_x=_optional_float(row.hc_x),
            hc_y=_optional_float(row.hc_y),
            hit_distance=_optional_float(row.hit_distance_sc),
            launch_speed=_optional_float(row.launch_speed),
            launch_angle=_optional_float(row.launch_angle),
            hyper_speed=_optional_float(row.hyper_speed),
            arm_angle=_optional_float(row.arm_angle),
            attack_angle=_optional_float(row.attack_angle),
            attack_direction=_optional_float(row.attack_direction),
            swing_path_tilt=_optional_float(row.swing_path_tilt),
            intercept_ball_minus_batter_pos_x_inches=_optional_float(
                row.intercept_ball_minus_batter_pos_x_inches
            ),
            intercept_ball_minus_batter_pos_y_inches=_optional_float(
                row.intercept_ball_minus_batter_pos_y_inches
            ),
        )


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)
