"""Extract and transform curated plate appearances into pitching rows."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

from sqlalchemy import MetaData, Table, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

_ANALYTICS_WRITE_BATCH_SIZE = 500


@dataclass(frozen=True)
class PlayerGamePitchingAppearance:
    pitcher_id: int
    game_id: int
    team_id: int
    outcome_code: str | None
    pitches: int


@dataclass(frozen=True)
class PlayerGamePitching:
    pitcher_id: int
    game_id: int
    team_id: int
    batters_faced: int
    pitches: int
    hits_allowed: int
    home_runs_allowed: int
    walks: int
    hit_by_pitch: int
    strikeouts: int


def get_player_game_pitching_appearances(
    connection: Connection,
) -> list[PlayerGamePitchingAppearance]:
    """Return one appearance per curated plate appearance.

    ``outcome_code`` is NULL when ``outcome_type_id`` is NULL. ``pitches``
    is the number of ``curated.pitch`` rows for the plate appearance.
    Rows are ordered by ``game_id``, ``at_bat_number``. The caller owns
    the transaction.
    """
    metadata = MetaData()
    plate_appearance = Table(
        "plate_appearance",
        metadata,
        schema="curated",
        autoload_with=connection,
    )
    outcome_type = Table(
        "outcome_type",
        metadata,
        schema="curated",
        autoload_with=connection,
    )
    pitch = Table(
        "pitch",
        metadata,
        schema="curated",
        autoload_with=connection,
    )

    pitch_counts = (
        select(
            pitch.c.plate_appearance_id,
            func.count(pitch.c.pitch_id).label("pitches"),
        )
        .group_by(pitch.c.plate_appearance_id)
        .subquery()
    )

    statement = (
        select(
            plate_appearance.c.pitcher_id,
            plate_appearance.c.game_id,
            plate_appearance.c.pitcher_team_id,
            outcome_type.c.code,
            func.coalesce(pitch_counts.c.pitches, 0).label("pitches"),
        )
        .select_from(
            plate_appearance.outerjoin(
                outcome_type,
                plate_appearance.c.outcome_type_id == outcome_type.c.id,
            ).outerjoin(
                pitch_counts,
                pitch_counts.c.plate_appearance_id
                == plate_appearance.c.plate_appearance_id,
            )
        )
        .order_by(
            plate_appearance.c.game_id,
            plate_appearance.c.at_bat_number,
        )
    )

    return [
        PlayerGamePitchingAppearance(
            pitcher_id=int(row.pitcher_id),
            game_id=int(row.game_id),
            team_id=int(row.pitcher_team_id),
            outcome_code=None if row.code is None else str(row.code),
            pitches=int(row.pitches),
        )
        for row in connection.execute(statement)
    ]


@dataclass(frozen=True)
class _PitchingIncrements:
    hits_allowed: int = 0
    home_runs_allowed: int = 0
    walks: int = 0
    hit_by_pitch: int = 0
    strikeouts: int = 0


_HIT = _PitchingIncrements(hits_allowed=1)
_HOME_RUN = _PitchingIncrements(hits_allowed=1, home_runs_allowed=1)
_WALK = _PitchingIncrements(walks=1)
_HIT_BY_PITCH = _PitchingIncrements(hit_by_pitch=1)
_STRIKEOUT = _PitchingIncrements(strikeouts=1)
_BF_ONLY = _PitchingIncrements()


@dataclass
class _PitchingTotals:
    batters_faced: int = 0
    pitches: int = 0
    hits_allowed: int = 0
    home_runs_allowed: int = 0
    walks: int = 0
    hit_by_pitch: int = 0
    strikeouts: int = 0

    def add(self, increments: _PitchingIncrements, pitches: int) -> None:
        self.batters_faced += 1
        self.pitches += pitches
        self.hits_allowed += increments.hits_allowed
        self.home_runs_allowed += increments.home_runs_allowed
        self.walks += increments.walks
        self.hit_by_pitch += increments.hit_by_pitch
        self.strikeouts += increments.strikeouts


_OUTCOME_INCREMENTS: dict[str | None, _PitchingIncrements] = {
    "single": _HIT,
    "double": _HIT,
    "triple": _HIT,
    "home_run": _HOME_RUN,
    "walk": _WALK,
    "intent_walk": _WALK,
    "hit_by_pitch": _HIT_BY_PITCH,
    "strikeout": _STRIKEOUT,
    "strikeout_double_play": _STRIKEOUT,
    "sac_fly": _BF_ONLY,
    "sac_fly_double_play": _BF_ONLY,
    "sac_bunt": _BF_ONLY,
    "field_out": _BF_ONLY,
    "field_error": _BF_ONLY,
    "force_out": _BF_ONLY,
    "grounded_into_double_play": _BF_ONLY,
    "double_play": _BF_ONLY,
    "triple_play": _BF_ONLY,
    "fielders_choice": _BF_ONLY,
    "fielders_choice_out": _BF_ONLY,
    "catcher_interf": _BF_ONLY,
    "truncated_pa": _BF_ONLY,
    None: _BF_ONLY,
}


def transform_player_game_pitching(
    connection: Connection,
    plate_appearances: Sequence[PlayerGamePitchingAppearance],
) -> list[PlayerGamePitching]:
    """Aggregate plate appearances into pitcher/game/team pitching rows.

    Outcome codes and pitch counts are taken from the input. The
    connection is accepted for caller consistency and is not queried.
    The caller owns the transaction. Unknown outcome codes raise
    ValueError.
    """
    if not plate_appearances:
        return []

    totals: dict[tuple[int, int, int], _PitchingTotals] = {}
    for appearance in plate_appearances:
        key = (appearance.pitcher_id, appearance.game_id, appearance.team_id)
        current = totals.get(key)
        if current is None:
            current = _PitchingTotals()
            totals[key] = current
        current.add(_increments_for(appearance.outcome_code), appearance.pitches)

    return [
        PlayerGamePitching(
            pitcher_id=pitcher_id,
            game_id=game_id,
            team_id=team_id,
            batters_faced=counts.batters_faced,
            pitches=counts.pitches,
            hits_allowed=counts.hits_allowed,
            home_runs_allowed=counts.home_runs_allowed,
            walks=counts.walks,
            hit_by_pitch=counts.hit_by_pitch,
            strikeouts=counts.strikeouts,
        )
        for (pitcher_id, game_id, team_id), counts in sorted(totals.items())
    ]


def load_player_game_pitching(
    connection: Connection,
    rows: Sequence[PlayerGamePitching],
) -> int:
    """Insert player-game pitching rows into analytics.player_game_pitching.

    ``player_game_pitching_id`` and ``created_at`` are generated by the
    database. Duplicate ``(pitcher_id, game_id, team_id)`` values raise
    a database integrity error. The caller owns the transaction.
    """
    if not rows:
        return 0

    table = _analytics_table(connection)
    for start in range(0, len(rows), _ANALYTICS_WRITE_BATCH_SIZE):
        batch = rows[start : start + _ANALYTICS_WRITE_BATCH_SIZE]
        statement = insert(table).values([asdict(row) for row in batch])
        connection.execute(statement)
    return len(rows)


def _analytics_table(connection: Connection) -> Table:
    metadata = MetaData()
    return Table(
        "player_game_pitching",
        metadata,
        schema="analytics",
        autoload_with=connection,
    )


def _increments_for(outcome_code: str | None) -> _PitchingIncrements:
    try:
        return _OUTCOME_INCREMENTS[outcome_code]
    except KeyError as exc:
        raise ValueError(
            "No pitching statistic mapping found for outcome code "
            f"{outcome_code}."
        ) from exc
