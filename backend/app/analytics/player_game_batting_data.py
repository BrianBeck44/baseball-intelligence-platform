"""Extract and transform curated plate appearances into batting rows."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

from sqlalchemy import MetaData, Table, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class PlayerGameBattingAppearance:
    player_id: int
    game_id: int
    team_id: int
    outcome_code: str | None


@dataclass(frozen=True)
class PlayerGameBatting:
    player_id: int
    game_id: int
    team_id: int
    plate_appearances: int
    at_bats: int
    hits: int
    singles: int
    doubles: int
    triples: int
    home_runs: int
    walks: int
    hit_by_pitch: int
    strikeouts: int
    sacrifice_flies: int
    sacrifice_bunts: int


def get_player_game_batting_appearances(
    connection: Connection,
) -> list[PlayerGameBattingAppearance]:
    """Return one appearance per curated plate appearance.

    ``outcome_code`` is NULL when ``outcome_type_id`` is NULL. Rows are
    ordered by ``game_id``, ``at_bat_number``. The caller owns the
    transaction.
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

    statement = (
        select(
            plate_appearance.c.batter_id,
            plate_appearance.c.game_id,
            plate_appearance.c.batter_team_id,
            outcome_type.c.code,
        )
        .select_from(
            plate_appearance.outerjoin(
                outcome_type,
                plate_appearance.c.outcome_type_id == outcome_type.c.id,
            )
        )
        .order_by(
            plate_appearance.c.game_id,
            plate_appearance.c.at_bat_number,
        )
    )

    return [
        PlayerGameBattingAppearance(
            player_id=int(row.batter_id),
            game_id=int(row.game_id),
            team_id=int(row.batter_team_id),
            outcome_code=None if row.code is None else str(row.code),
        )
        for row in connection.execute(statement)
    ]


@dataclass(frozen=True)
class _BattingIncrements:
    at_bats: int = 0
    hits: int = 0
    singles: int = 0
    doubles: int = 0
    triples: int = 0
    home_runs: int = 0
    walks: int = 0
    hit_by_pitch: int = 0
    strikeouts: int = 0
    sacrifice_flies: int = 0
    sacrifice_bunts: int = 0


_AB = _BattingIncrements(at_bats=1)
_SINGLE = _BattingIncrements(at_bats=1, hits=1, singles=1)
_DOUBLE = _BattingIncrements(at_bats=1, hits=1, doubles=1)
_TRIPLE = _BattingIncrements(at_bats=1, hits=1, triples=1)
_HOME_RUN = _BattingIncrements(at_bats=1, hits=1, home_runs=1)
_WALK = _BattingIncrements(walks=1)
_HIT_BY_PITCH = _BattingIncrements(hit_by_pitch=1)
_STRIKEOUT = _BattingIncrements(at_bats=1, strikeouts=1)
_SAC_FLY = _BattingIncrements(sacrifice_flies=1)
_SAC_BUNT = _BattingIncrements(sacrifice_bunts=1)
_PA_ONLY = _BattingIncrements()

@dataclass
class _BattingTotals:
    plate_appearances: int = 0
    at_bats: int = 0
    hits: int = 0
    singles: int = 0
    doubles: int = 0
    triples: int = 0
    home_runs: int = 0
    walks: int = 0
    hit_by_pitch: int = 0
    strikeouts: int = 0
    sacrifice_flies: int = 0
    sacrifice_bunts: int = 0

    def add(self, increments: _BattingIncrements) -> None:
        self.plate_appearances += 1
        self.at_bats += increments.at_bats
        self.hits += increments.hits
        self.singles += increments.singles
        self.doubles += increments.doubles
        self.triples += increments.triples
        self.home_runs += increments.home_runs
        self.walks += increments.walks
        self.hit_by_pitch += increments.hit_by_pitch
        self.strikeouts += increments.strikeouts
        self.sacrifice_flies += increments.sacrifice_flies
        self.sacrifice_bunts += increments.sacrifice_bunts


_OUTCOME_INCREMENTS: dict[str | None, _BattingIncrements] = {
    "single": _SINGLE,
    "double": _DOUBLE,
    "triple": _TRIPLE,
    "home_run": _HOME_RUN,
    "walk": _WALK,
    "intent_walk": _WALK,
    "hit_by_pitch": _HIT_BY_PITCH,
    "strikeout": _STRIKEOUT,
    "strikeout_double_play": _STRIKEOUT,
    "sac_fly": _SAC_FLY,
    "sac_bunt": _SAC_BUNT,
    "field_out": _AB,
    "field_error": _AB,
    "force_out": _AB,
    "grounded_into_double_play": _AB,
    "double_play": _AB,
    "fielders_choice": _AB,
    "fielders_choice_out": _AB,
    "catcher_interf": _PA_ONLY,
    "truncated_pa": _PA_ONLY,
    None: _PA_ONLY,
}


def transform_player_game_batting(
    connection: Connection,
    plate_appearances: Sequence[PlayerGameBattingAppearance],
) -> list[PlayerGameBatting]:
    """Aggregate plate appearances into player/game/team batting rows.

    Outcome codes are taken from the input. The connection is accepted
    for caller consistency and is not queried. The caller owns the
    transaction. Unknown outcome codes raise ValueError.
    """
    if not plate_appearances:
        return []

    totals: dict[tuple[int, int, int], _BattingTotals] = {}
    for appearance in plate_appearances:
        key = (appearance.player_id, appearance.game_id, appearance.team_id)
        current = totals.get(key)
        if current is None:
            current = _BattingTotals()
            totals[key] = current
        current.add(_increments_for(appearance.outcome_code))

    return [
        PlayerGameBatting(
            player_id=player_id,
            game_id=game_id,
            team_id=team_id,
            plate_appearances=counts.plate_appearances,
            at_bats=counts.at_bats,
            hits=counts.hits,
            singles=counts.singles,
            doubles=counts.doubles,
            triples=counts.triples,
            home_runs=counts.home_runs,
            walks=counts.walks,
            hit_by_pitch=counts.hit_by_pitch,
            strikeouts=counts.strikeouts,
            sacrifice_flies=counts.sacrifice_flies,
            sacrifice_bunts=counts.sacrifice_bunts,
        )
        for (player_id, game_id, team_id), counts in sorted(totals.items())
    ]


def load_player_game_batting(
    connection: Connection,
    rows: Sequence[PlayerGameBatting],
) -> int:
    """Insert player-game batting rows into analytics.player_game_batting.

    ``player_game_batting_id`` and ``created_at`` are generated by the
    database. Duplicate ``(player_id, game_id, team_id)`` values raise
    a database integrity error. The caller owns the transaction.
    """
    if not rows:
        return 0

    table = _analytics_table(connection)
    statement = insert(table).values([asdict(row) for row in rows])
    connection.execute(statement)
    return len(rows)


def _analytics_table(connection: Connection) -> Table:
    metadata = MetaData()
    return Table(
        "player_game_batting",
        metadata,
        schema="analytics",
        autoload_with=connection,
    )


def _increments_for(outcome_code: str | None) -> _BattingIncrements:
    try:
        return _OUTCOME_INCREMENTS[outcome_code]
    except KeyError as exc:
        raise ValueError(
            "No batting statistic mapping found for outcome code "
            f"{outcome_code}."
        ) from exc
