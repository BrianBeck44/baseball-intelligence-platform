"""Transform extracted Statcast pitches and persist curated records."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from weakref import WeakKeyDictionary

from sqlalchemy import MetaData, Table, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from app.curated.statcast_pitch_data import StatcastPitch

_PITCH_INSERT_BATCH_SIZE = 1000
_PLATE_APPEARANCE_LOOKUP_BATCH_SIZE = 500


@dataclass
class _PitchConnectionCache:
    metadata: MetaData = field(default_factory=MetaData)
    tables: dict[str, Table] = field(default_factory=dict)
    game_ids_by_mlb_game_pk: dict[int, int] | None = None
    pitch_type_ids_by_code: dict[str, int] | None = None
    pitch_outcome_type_ids_by_code: dict[str, int] | None = None


_PITCH_CONNECTION_CACHES: WeakKeyDictionary[
    Connection,
    _PitchConnectionCache,
] = WeakKeyDictionary()


@dataclass(frozen=True)
class CuratedPitch:
    plate_appearance_id: int
    pitch_number: int
    pitch_type_id: int | None
    pitch_outcome_type_id: int | None
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


def transform_pitches(
    connection: Connection,
    pitches: Sequence[StatcastPitch],
) -> list[CuratedPitch]:
    """Resolve Statcast pitches to curated identifiers.

    Lookups only; the caller owns the transaction. Missing required
    curated rows raise ValueError. Null pitch type and pitch outcome
    codes remain None.
    """
    if not pitches:
        return []

    game_ids = _game_ids_by_mlb_game_pk(
        connection,
        {pitch.mlb_game_pk for pitch in pitches},
    )
    missing_games = sorted(
        {pitch.mlb_game_pk for pitch in pitches} - game_ids.keys()
    )
    if missing_games:
        raise ValueError(
            "No curated game found for MLB game PK "
            + ", ".join(str(game_pk) for game_pk in missing_games)
        )

    plate_appearance_keys = {
        (game_ids[pitch.mlb_game_pk], pitch.at_bat_number) for pitch in pitches
    }
    plate_appearance_ids = _plate_appearance_ids_by_game_at_bat(
        connection,
        plate_appearance_keys,
    )
    missing_plate_appearances = sorted(
        {
            (pitch.mlb_game_pk, pitch.at_bat_number)
            for pitch in pitches
            if (
                game_ids[pitch.mlb_game_pk],
                pitch.at_bat_number,
            )
            not in plate_appearance_ids
        }
    )
    if missing_plate_appearances:
        details = ", ".join(
            f"MLB game PK {game_pk}, at_bat_number {at_bat_number}"
            for game_pk, at_bat_number in missing_plate_appearances
        )
        raise ValueError(f"No curated plate appearance found for {details}")

    pitch_type_ids = _pitch_type_ids_by_code(
        connection,
        {pitch.pitch_type_code for pitch in pitches},
    )
    missing_pitch_types = sorted(
        {
            pitch.pitch_type_code
            for pitch in pitches
            if pitch.pitch_type_code is not None
        }
        - pitch_type_ids.keys()
    )
    if missing_pitch_types:
        raise ValueError(
            "No curated pitch type found for pitch type code "
            + ", ".join(missing_pitch_types)
        )

    pitch_outcome_type_ids = _pitch_outcome_type_ids_by_code(
        connection,
        {pitch.pitch_outcome_code for pitch in pitches},
    )
    missing_pitch_outcomes = sorted(
        {
            pitch.pitch_outcome_code
            for pitch in pitches
            if pitch.pitch_outcome_code is not None
        }
        - pitch_outcome_type_ids.keys()
    )
    if missing_pitch_outcomes:
        raise ValueError(
            "No curated pitch outcome type found for pitch outcome code "
            + ", ".join(missing_pitch_outcomes)
        )

    return [
        _to_curated_pitch(
            pitch,
            plate_appearance_id=plate_appearance_ids[
                (game_ids[pitch.mlb_game_pk], pitch.at_bat_number)
            ],
            pitch_type_id=(
                None
                if pitch.pitch_type_code is None
                else pitch_type_ids[pitch.pitch_type_code]
            ),
            pitch_outcome_type_id=(
                None
                if pitch.pitch_outcome_code is None
                else pitch_outcome_type_ids[pitch.pitch_outcome_code]
            ),
        )
        for pitch in pitches
    ]


def _to_curated_pitch(
    pitch: StatcastPitch,
    *,
    plate_appearance_id: int,
    pitch_type_id: int | None,
    pitch_outcome_type_id: int | None,
) -> CuratedPitch:
    return CuratedPitch(
        plate_appearance_id=plate_appearance_id,
        pitch_number=pitch.pitch_number,
        pitch_type_id=pitch_type_id,
        pitch_outcome_type_id=pitch_outcome_type_id,
        balls=pitch.balls,
        strikes=pitch.strikes,
        zone=pitch.zone,
        plate_x=pitch.plate_x,
        plate_z=pitch.plate_z,
        sz_top=pitch.sz_top,
        sz_bot=pitch.sz_bot,
        release_speed=pitch.release_speed,
        effective_speed=pitch.effective_speed,
        release_spin=pitch.release_spin,
        spin_axis=pitch.spin_axis,
        release_pos_x=pitch.release_pos_x,
        release_pos_y=pitch.release_pos_y,
        release_pos_z=pitch.release_pos_z,
        release_extension=pitch.release_extension,
        pfx_x=pitch.pfx_x,
        pfx_z=pitch.pfx_z,
        vx0=pitch.vx0,
        vy0=pitch.vy0,
        vz0=pitch.vz0,
        ax=pitch.ax,
        ay=pitch.ay,
        az=pitch.az,
        home_score=pitch.home_score,
        away_score=pitch.away_score,
        post_home_score=pitch.post_home_score,
        post_away_score=pitch.post_away_score,
        home_win_exp=pitch.home_win_exp,
        bat_win_exp=pitch.bat_win_exp,
        delta_home_win_exp=pitch.delta_home_win_exp,
        delta_run_exp=pitch.delta_run_exp,
        estimated_ba_using_speedangle=pitch.estimated_ba_using_speedangle,
        estimated_woba_using_speedangle=pitch.estimated_woba_using_speedangle,
        woba_value=pitch.woba_value,
        hc_x=pitch.hc_x,
        hc_y=pitch.hc_y,
        hit_distance=pitch.hit_distance,
        launch_speed=pitch.launch_speed,
        launch_angle=pitch.launch_angle,
        hyper_speed=pitch.hyper_speed,
        arm_angle=pitch.arm_angle,
        attack_angle=pitch.attack_angle,
        attack_direction=pitch.attack_direction,
        swing_path_tilt=pitch.swing_path_tilt,
        intercept_ball_minus_batter_pos_x_inches=(
            pitch.intercept_ball_minus_batter_pos_x_inches
        ),
        intercept_ball_minus_batter_pos_y_inches=(
            pitch.intercept_ball_minus_batter_pos_y_inches
        ),
    )


def load_pitches(
    connection: Connection,
    pitches: Sequence[CuratedPitch],
) -> int:
    """Insert curated pitches into curated.pitch.

    Conflict is skipped on ``(plate_appearance_id, pitch_number)``.
    ``pitch_id`` and ``created_at`` are generated by the database. The
    caller owns the transaction.
    """
    if not pitches:
        return 0

    pitch_table = _curated_table(connection, "pitch")
    inserted = 0
    for start in range(0, len(pitches), _PITCH_INSERT_BATCH_SIZE):
        batch = pitches[start : start + _PITCH_INSERT_BATCH_SIZE]
        statement = insert(pitch_table).values(
            [asdict(pitch) for pitch in batch]
        )
        statement = statement.on_conflict_do_nothing(
            index_elements=[
                pitch_table.c.plate_appearance_id,
                pitch_table.c.pitch_number,
            ]
        ).returning(pitch_table.c.pitch_id)
        result = connection.execute(statement)
        inserted += len(result.all())
    return inserted


def _cache_for(connection: Connection) -> _PitchConnectionCache:
    cache = _PITCH_CONNECTION_CACHES.get(connection)
    if cache is None:
        cache = _PitchConnectionCache()
        _PITCH_CONNECTION_CACHES[connection] = cache
    return cache


def _curated_table(connection: Connection, table_name: str) -> Table:
    cache = _cache_for(connection)
    table = cache.tables.get(table_name)
    if table is None:
        table = Table(
            table_name,
            cache.metadata,
            schema="curated",
            autoload_with=connection,
        )
        cache.tables[table_name] = table
    return table


def _game_ids_by_mlb_game_pk(
    connection: Connection,
    mlb_game_pks: Iterable[int],
) -> dict[int, int]:
    game_pks = set(mlb_game_pks)
    if not game_pks:
        return {}

    cache = _cache_for(connection)
    if cache.game_ids_by_mlb_game_pk is None:
        game = _curated_table(connection, "game")
        rows = connection.execute(
            select(game.c.mlb_game_pk, game.c.game_id)
        ).all()
        cache.game_ids_by_mlb_game_pk = {
            int(mlb_game_pk): int(game_id) for mlb_game_pk, game_id in rows
        }
    return {
        mlb_game_pk: cache.game_ids_by_mlb_game_pk[mlb_game_pk]
        for mlb_game_pk in game_pks
        if mlb_game_pk in cache.game_ids_by_mlb_game_pk
    }


def _plate_appearance_ids_by_game_at_bat(
    connection: Connection,
    keys: Iterable[tuple[int, int]],
) -> dict[tuple[int, int], int]:
    appearance_keys = list(set(keys))
    if not appearance_keys:
        return {}

    plate_appearance = _curated_table(connection, "plate_appearance")
    mapping: dict[tuple[int, int], int] = {}
    for start in range(0, len(appearance_keys), _PLATE_APPEARANCE_LOOKUP_BATCH_SIZE):
        batch = appearance_keys[
            start : start + _PLATE_APPEARANCE_LOOKUP_BATCH_SIZE
        ]
        rows = connection.execute(
            select(
                plate_appearance.c.game_id,
                plate_appearance.c.at_bat_number,
                plate_appearance.c.plate_appearance_id,
            ).where(
                tuple_(
                    plate_appearance.c.game_id,
                    plate_appearance.c.at_bat_number,
                ).in_(batch)
            )
        ).all()
        mapping.update(
            {
                (int(game_id), int(at_bat_number)): int(plate_appearance_id)
                for game_id, at_bat_number, plate_appearance_id in rows
            }
        )
    return mapping


def _pitch_type_ids_by_code(
    connection: Connection,
    pitch_type_codes: Iterable[str | None],
) -> dict[str, int]:
    codes = {code for code in pitch_type_codes if code is not None}
    if not codes:
        return {}

    cache = _cache_for(connection)
    if cache.pitch_type_ids_by_code is None:
        pitch_type = _curated_table(connection, "pitch_type")
        rows = connection.execute(
            select(pitch_type.c.code, pitch_type.c.id)
        ).all()
        cache.pitch_type_ids_by_code = {
            str(code): int(type_id) for code, type_id in rows
        }
    return {
        code: cache.pitch_type_ids_by_code[code]
        for code in codes
        if code in cache.pitch_type_ids_by_code
    }


def _pitch_outcome_type_ids_by_code(
    connection: Connection,
    pitch_outcome_codes: Iterable[str | None],
) -> dict[str, int]:
    codes = {code for code in pitch_outcome_codes if code is not None}
    if not codes:
        return {}

    cache = _cache_for(connection)
    if cache.pitch_outcome_type_ids_by_code is None:
        pitch_outcome_type = _curated_table(connection, "pitch_outcome_type")
        rows = connection.execute(
            select(pitch_outcome_type.c.code, pitch_outcome_type.c.id)
        ).all()
        cache.pitch_outcome_type_ids_by_code = {
            str(code): int(type_id) for code, type_id in rows
        }
    return {
        code: cache.pitch_outcome_type_ids_by_code[code]
        for code in codes
        if code in cache.pitch_outcome_type_ids_by_code
    }
