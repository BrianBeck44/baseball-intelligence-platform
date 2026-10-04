"""Extract and transform curated pitches into pitch-type effectiveness rows."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field

from sqlalchemy import MetaData, Table, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class PlayerPitchTypeEffectivenessPitch:
    player_id: int
    pitch_type_id: int
    plate_appearance_id: int
    pitch_outcome_code: str | None
    pa_outcome_code: str | None
    is_terminal_pitch: bool


@dataclass(frozen=True)
class PlayerPitchTypeEffectiveness:
    player_id: int
    pitch_type_id: int
    pitches: int
    plate_appearances: int
    balls_in_play: int
    swings: int
    whiffs: int
    called_strikes: int
    fouls: int
    hits_allowed: int
    home_runs_allowed: int
    strikeouts: int
    walks: int
    hit_by_pitch: int
    whiff_rate: float | None
    called_strike_rate: float | None
    swing_rate: float | None
    contact_rate: float | None
    strikeout_rate: float | None


def get_player_pitch_type_effectiveness_pitches(
    connection: Connection,
) -> list[PlayerPitchTypeEffectivenessPitch]:
    """Return one row per curated pitch with a pitch type.

    ``pitch_outcome_code`` and ``pa_outcome_code`` are NULL when the
    corresponding type IDs are NULL. ``is_terminal_pitch`` is true for
    the maximum ``pitch_number`` in each plate appearance. The caller
    owns the transaction.
    """
    metadata = MetaData()
    pitch = Table(
        "pitch",
        metadata,
        schema="curated",
        autoload_with=connection,
    )
    plate_appearance = Table(
        "plate_appearance",
        metadata,
        schema="curated",
        autoload_with=connection,
    )
    pitch_outcome_type = Table(
        "pitch_outcome_type",
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

    terminal_pitches = (
        select(
            pitch.c.plate_appearance_id,
            func.max(pitch.c.pitch_number).label("pitch_number"),
        )
        .group_by(pitch.c.plate_appearance_id)
        .subquery()
    )

    statement = (
        select(
            plate_appearance.c.pitcher_id,
            pitch.c.pitch_type_id,
            pitch.c.plate_appearance_id,
            pitch_outcome_type.c.code.label("pitch_outcome_code"),
            outcome_type.c.code.label("pa_outcome_code"),
            terminal_pitches.c.plate_appearance_id.is_not(None).label(
                "is_terminal_pitch"
            ),
        )
        .select_from(
            pitch.join(
                plate_appearance,
                plate_appearance.c.plate_appearance_id
                == pitch.c.plate_appearance_id,
            )
            .outerjoin(
                pitch_outcome_type,
                pitch.c.pitch_outcome_type_id == pitch_outcome_type.c.id,
            )
            .outerjoin(
                outcome_type,
                plate_appearance.c.outcome_type_id == outcome_type.c.id,
            )
            .outerjoin(
                terminal_pitches,
                (
                    terminal_pitches.c.plate_appearance_id
                    == pitch.c.plate_appearance_id
                )
                & (terminal_pitches.c.pitch_number == pitch.c.pitch_number),
            )
        )
        .where(pitch.c.pitch_type_id.is_not(None))
        .order_by(
            pitch.c.plate_appearance_id,
            pitch.c.pitch_number,
        )
    )

    return [
        PlayerPitchTypeEffectivenessPitch(
            player_id=int(row.pitcher_id),
            pitch_type_id=int(row.pitch_type_id),
            plate_appearance_id=int(row.plate_appearance_id),
            pitch_outcome_code=(
                None
                if row.pitch_outcome_code is None
                else str(row.pitch_outcome_code)
            ),
            pa_outcome_code=(
                None if row.pa_outcome_code is None else str(row.pa_outcome_code)
            ),
            is_terminal_pitch=bool(row.is_terminal_pitch),
        )
        for row in connection.execute(statement)
    ]


_SWING_OUTCOMES = frozenset(
    {
        "foul",
        "foul_bunt",
        "foul_tip",
        "hit_into_play",
        "missed_bunt",
        "swinging_strike",
        "swinging_strike_blocked",
    }
)
_WHIFF_OUTCOMES = frozenset(
    {
        "swinging_strike",
        "swinging_strike_blocked",
    }
)
_FOUL_OUTCOMES = frozenset(
    {
        "foul",
        "foul_bunt",
        "foul_tip",
    }
)
_RECOGNIZED_PITCH_OUTCOMES = frozenset(
    {
        "automatic_ball",
        "ball",
        "blocked_ball",
        "called_strike",
        "foul",
        "foul_bunt",
        "foul_tip",
        "hit_by_pitch",
        "hit_into_play",
        "missed_bunt",
        "swinging_strike",
        "swinging_strike_blocked",
    }
)
_RECOGNIZED_PA_OUTCOMES = frozenset(
    {
        "catcher_interf",
        "double",
        "double_play",
        "field_error",
        "fielders_choice",
        "fielders_choice_out",
        "field_out",
        "force_out",
        "grounded_into_double_play",
        "hit_by_pitch",
        "home_run",
        "intent_walk",
        "sac_bunt",
        "sac_fly",
        "single",
        "strikeout",
        "strikeout_double_play",
        "triple",
        "truncated_pa",
        "walk",
    }
)


@dataclass(frozen=True)
class _PitchIncrements:
    swings: int = 0
    whiffs: int = 0
    called_strikes: int = 0
    balls_in_play: int = 0
    fouls: int = 0


@dataclass(frozen=True)
class _PaIncrements:
    hits_allowed: int = 0
    home_runs_allowed: int = 0
    strikeouts: int = 0
    walks: int = 0
    hit_by_pitch: int = 0


_NO_PITCH_INCREMENTS = _PitchIncrements()
_NO_PA_INCREMENTS = _PaIncrements()
_HIT = _PaIncrements(hits_allowed=1)
_HOME_RUN = _PaIncrements(hits_allowed=1, home_runs_allowed=1)
_STRIKEOUT = _PaIncrements(strikeouts=1)
_WALK = _PaIncrements(walks=1)
_HIT_BY_PITCH = _PaIncrements(hit_by_pitch=1)

_PA_OUTCOME_INCREMENTS: dict[str | None, _PaIncrements] = {
    "single": _HIT,
    "double": _HIT,
    "triple": _HIT,
    "home_run": _HOME_RUN,
    "strikeout": _STRIKEOUT,
    "walk": _WALK,
    "hit_by_pitch": _HIT_BY_PITCH,
    None: _NO_PA_INCREMENTS,
}
for _code in _RECOGNIZED_PA_OUTCOMES:
    _PA_OUTCOME_INCREMENTS.setdefault(_code, _NO_PA_INCREMENTS)


@dataclass
class _Totals:
    pitches: int = 0
    plate_appearance_ids: set[int] = field(default_factory=set)
    balls_in_play: int = 0
    swings: int = 0
    whiffs: int = 0
    called_strikes: int = 0
    fouls: int = 0
    hits_allowed: int = 0
    home_runs_allowed: int = 0
    strikeouts: int = 0
    walks: int = 0
    hit_by_pitch: int = 0

    def add(
        self,
        pitch: PlayerPitchTypeEffectivenessPitch,
        pitch_increments: _PitchIncrements,
        pa_increments: _PaIncrements,
    ) -> None:
        self.pitches += 1
        self.plate_appearance_ids.add(pitch.plate_appearance_id)
        self.balls_in_play += pitch_increments.balls_in_play
        self.swings += pitch_increments.swings
        self.whiffs += pitch_increments.whiffs
        self.called_strikes += pitch_increments.called_strikes
        self.fouls += pitch_increments.fouls
        if pitch.is_terminal_pitch:
            self.hits_allowed += pa_increments.hits_allowed
            self.home_runs_allowed += pa_increments.home_runs_allowed
            self.strikeouts += pa_increments.strikeouts
            self.walks += pa_increments.walks
            self.hit_by_pitch += pa_increments.hit_by_pitch


def transform_player_pitch_type_effectiveness(
    connection: Connection,
    pitches: Sequence[PlayerPitchTypeEffectivenessPitch],
) -> list[PlayerPitchTypeEffectiveness]:
    """Aggregate pitches into player/pitch-type effectiveness rows.

    Outcome codes and terminal-pitch flags are taken from the input. The
    connection is accepted for caller consistency and is not queried.
    The caller owns the transaction. Unknown outcome codes raise
    ValueError.
    """
    if not pitches:
        return []

    totals: dict[tuple[int, int], _Totals] = {}
    for pitch in pitches:
        key = (pitch.player_id, pitch.pitch_type_id)
        current = totals.get(key)
        if current is None:
            current = _Totals()
            totals[key] = current
        current.add(
            pitch,
            _pitch_increments_for(pitch.pitch_outcome_code),
            _pa_increments_for(pitch.pa_outcome_code),
        )

    return [
        PlayerPitchTypeEffectiveness(
            player_id=player_id,
            pitch_type_id=pitch_type_id,
            pitches=counts.pitches,
            plate_appearances=len(counts.plate_appearance_ids),
            balls_in_play=counts.balls_in_play,
            swings=counts.swings,
            whiffs=counts.whiffs,
            called_strikes=counts.called_strikes,
            fouls=counts.fouls,
            hits_allowed=counts.hits_allowed,
            home_runs_allowed=counts.home_runs_allowed,
            strikeouts=counts.strikeouts,
            walks=counts.walks,
            hit_by_pitch=counts.hit_by_pitch,
            whiff_rate=_rate(counts.whiffs, counts.swings),
            called_strike_rate=_rate(counts.called_strikes, counts.pitches),
            swing_rate=_rate(counts.swings, counts.pitches),
            contact_rate=_rate(
                counts.swings - counts.whiffs,
                counts.swings,
            ),
            strikeout_rate=_rate(
                counts.strikeouts,
                len(counts.plate_appearance_ids),
            ),
        )
        for (player_id, pitch_type_id), counts in sorted(totals.items())
    ]


def _pitch_increments_for(outcome_code: str | None) -> _PitchIncrements:
    if outcome_code is not None and outcome_code not in _RECOGNIZED_PITCH_OUTCOMES:
        raise ValueError(
            "No pitch-type effectiveness mapping found for pitch outcome "
            f"code {outcome_code}."
        )
    if outcome_code is None:
        return _NO_PITCH_INCREMENTS
    return _PitchIncrements(
        swings=1 if outcome_code in _SWING_OUTCOMES else 0,
        whiffs=1 if outcome_code in _WHIFF_OUTCOMES else 0,
        called_strikes=1 if outcome_code == "called_strike" else 0,
        balls_in_play=1 if outcome_code == "hit_into_play" else 0,
        fouls=1 if outcome_code in _FOUL_OUTCOMES else 0,
    )


def _pa_increments_for(outcome_code: str | None) -> _PaIncrements:
    try:
        return _PA_OUTCOME_INCREMENTS[outcome_code]
    except KeyError as exc:
        raise ValueError(
            "No pitch-type effectiveness mapping found for plate "
            f"appearance outcome code {outcome_code}."
        ) from exc


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


_METRIC_COLUMNS = (
    "pitches",
    "plate_appearances",
    "balls_in_play",
    "swings",
    "whiffs",
    "called_strikes",
    "fouls",
    "hits_allowed",
    "home_runs_allowed",
    "strikeouts",
    "walks",
    "hit_by_pitch",
    "whiff_rate",
    "called_strike_rate",
    "swing_rate",
    "contact_rate",
    "strikeout_rate",
)


def load_player_pitch_type_effectiveness(
    connection: Connection,
    rows: Sequence[PlayerPitchTypeEffectiveness],
) -> int:
    """Insert or refresh pitch-type effectiveness rows.

    ``created_at`` is generated by the database on insert and is left
    unchanged on conflict. Existing ``(player_id, pitch_type_id)`` rows
    are updated to the current derived metrics. The caller owns the
    transaction.
    """
    if not rows:
        return 0

    table = _analytics_table(connection)
    statement = insert(table).values([asdict(row) for row in rows])
    statement = statement.on_conflict_do_update(
        index_elements=["player_id", "pitch_type_id"],
        set_={
            column: statement.excluded[column]
            for column in _METRIC_COLUMNS
        },
    )
    connection.execute(statement)
    return len(rows)


def _analytics_table(connection: Connection) -> Table:
    metadata = MetaData()
    return Table(
        "player_pitch_type_effectiveness",
        metadata,
        schema="analytics",
        autoload_with=connection,
    )
