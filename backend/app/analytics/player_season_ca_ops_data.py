"""Extract and transform plate appearances into season CA-OPS rows.

Competition-Adjusted OPS is a custom retrospective batter-season
metric. It is not an official MLB statistic and not a projection of
future performance.

v1 attributes each plate appearance to
``curated.plate_appearance.pitcher_id``. The current PA extract stores
the first-pitch pitcher there. A mid-PA pitching change can therefore
differ from terminal-pitcher credit. That limitation is accepted so
CA-OPS matches existing pitching analytics.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import MetaData, Table, select
from sqlalchemy.engine import Connection

from app.analytics.player_game_batting_data import (
    _BattingIncrements,
    batting_increments_for,
)

SHRINKAGE_K = 150


@dataclass(frozen=True)
class PlayerSeasonCaOpsAppearance:
    batter_id: int
    pitcher_id: int
    season_id: int
    outcome_code: str | None


@dataclass(frozen=True)
class PlayerSeasonBattingOps:
    player_id: int
    season_id: int
    ops: float | None


@dataclass(frozen=True)
class PlayerSeasonCaOps:
    player_id: int
    season_id: int
    plate_appearances: int
    observed_ops: float | None
    league_ops: float | None
    expected_opponent_ops: float | None
    ca_ops: float | None


def get_player_season_ca_ops_appearances(
    connection: Connection,
) -> list[PlayerSeasonCaOpsAppearance]:
    """Return one row per curated plate appearance.

    Pitcher identity is ``curated.plate_appearance.pitcher_id`` (first
    pitch in the current extract). ``outcome_code`` is NULL when
    ``outcome_type_id`` is NULL. The caller owns the transaction.
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
    game = Table(
        "game",
        metadata,
        schema="curated",
        autoload_with=connection,
    )

    statement = (
        select(
            plate_appearance.c.batter_id,
            plate_appearance.c.pitcher_id,
            game.c.season_id,
            outcome_type.c.code,
        )
        .select_from(
            plate_appearance.join(
                game,
                game.c.game_id == plate_appearance.c.game_id,
            ).outerjoin(
                outcome_type,
                plate_appearance.c.outcome_type_id == outcome_type.c.id,
            )
        )
        .order_by(
            game.c.season_id,
            plate_appearance.c.batter_id,
            plate_appearance.c.pitcher_id,
            plate_appearance.c.plate_appearance_id,
        )
    )

    return [
        PlayerSeasonCaOpsAppearance(
            batter_id=int(row.batter_id),
            pitcher_id=int(row.pitcher_id),
            season_id=int(row.season_id),
            outcome_code=None if row.code is None else str(row.code),
        )
        for row in connection.execute(statement)
    ]


def get_player_season_ca_ops_targets(
    connection: Connection,
) -> list[PlayerSeasonBattingOps]:
    """Return one observed-OPS row per season batting grain.

    OPS is taken from ``analytics.player_season_batting`` and is not
    recomputed. The caller owns the transaction.
    """
    metadata = MetaData()
    player_season_batting = Table(
        "player_season_batting",
        metadata,
        schema="analytics",
        autoload_with=connection,
    )

    statement = select(
        player_season_batting.c.player_id,
        player_season_batting.c.season_id,
        player_season_batting.c.ops,
    ).order_by(
        player_season_batting.c.player_id,
        player_season_batting.c.season_id,
    )

    return [
        PlayerSeasonBattingOps(
            player_id=int(row.player_id),
            season_id=int(row.season_id),
            ops=None if row.ops is None else float(row.ops),
        )
        for row in connection.execute(statement)
    ]


@dataclass
class _Counts:
    plate_appearances: int = 0
    at_bats: int = 0
    hits: int = 0
    singles: int = 0
    doubles: int = 0
    triples: int = 0
    home_runs: int = 0
    walks: int = 0
    hit_by_pitch: int = 0
    sacrifice_flies: int = 0

    def add_increments(self, increments: _BattingIncrements) -> None:
        self.plate_appearances += 1
        self.at_bats += increments.at_bats
        self.hits += increments.hits
        self.singles += increments.singles
        self.doubles += increments.doubles
        self.triples += increments.triples
        self.home_runs += increments.home_runs
        self.walks += increments.walks
        self.hit_by_pitch += increments.hit_by_pitch
        self.sacrifice_flies += increments.sacrifice_flies

    def minus(self, other: _Counts) -> _Counts:
        remaining = _Counts(
            plate_appearances=self.plate_appearances - other.plate_appearances,
            at_bats=self.at_bats - other.at_bats,
            hits=self.hits - other.hits,
            singles=self.singles - other.singles,
            doubles=self.doubles - other.doubles,
            triples=self.triples - other.triples,
            home_runs=self.home_runs - other.home_runs,
            walks=self.walks - other.walks,
            hit_by_pitch=self.hit_by_pitch - other.hit_by_pitch,
            sacrifice_flies=self.sacrifice_flies - other.sacrifice_flies,
        )
        negatives = [
            name
            for name, value in (
                ("plate_appearances", remaining.plate_appearances),
                ("at_bats", remaining.at_bats),
                ("hits", remaining.hits),
                ("singles", remaining.singles),
                ("doubles", remaining.doubles),
                ("triples", remaining.triples),
                ("home_runs", remaining.home_runs),
                ("walks", remaining.walks),
                ("hit_by_pitch", remaining.hit_by_pitch),
                ("sacrifice_flies", remaining.sacrifice_flies),
            )
            if value < 0
        ]
        if negatives:
            raise ValueError(
                "Leave-one-out counting statistics produced negative "
                + ", ".join(negatives)
                + "."
            )
        return remaining


def transform_player_season_ca_ops(
    connection: Connection,
    appearances: Sequence[PlayerSeasonCaOpsAppearance],
    targets: Sequence[PlayerSeasonBattingOps],
) -> list[PlayerSeasonCaOps]:
    """Build one CA-OPS row per season batting target.

    Counting statistics use the authoritative batting-outcome mapping.
    League OPS and pitcher OPS allowed exclude the target batter.
    Pitcher OPS allowed is shrunk toward that leave-one-out league OPS
    with ``k = 150``. The connection is accepted for caller consistency
    and is not queried. The caller owns the transaction.
    """
    if not targets:
        return []

    season_totals: dict[int, _Counts] = {}
    pitcher_totals: dict[tuple[int, int], _Counts] = {}
    batter_totals: dict[tuple[int, int], _Counts] = {}
    matchups: dict[tuple[int, int, int], _Counts] = {}

    for appearance in appearances:
        increments = batting_increments_for(appearance.outcome_code)
        season_totals.setdefault(appearance.season_id, _Counts()).add_increments(
            increments
        )
        pitcher_totals.setdefault(
            (appearance.season_id, appearance.pitcher_id),
            _Counts(),
        ).add_increments(increments)
        batter_totals.setdefault(
            (appearance.season_id, appearance.batter_id),
            _Counts(),
        ).add_increments(increments)
        matchups.setdefault(
            (appearance.season_id, appearance.batter_id, appearance.pitcher_id),
            _Counts(),
        ).add_increments(increments)

    matchups_by_batter: dict[tuple[int, int], list[tuple[int, _Counts]]] = {}
    for (season_id, batter_id, pitcher_id), counts in matchups.items():
        matchups_by_batter.setdefault((season_id, batter_id), []).append(
            (pitcher_id, counts)
        )

    rows: list[PlayerSeasonCaOps] = []
    for target in targets:
        batter_key = (target.season_id, target.player_id)
        batter_counts = batter_totals.get(batter_key, _Counts())
        season_counts = season_totals.get(target.season_id, _Counts())
        league_ops = _ops_from_counts(season_counts.minus(batter_counts))
        faced = matchups_by_batter.get(batter_key, [])
        expected_opponent_ops = _expected_opponent_ops(
            season_id=target.season_id,
            faced=faced,
            pitcher_totals=pitcher_totals,
            league_ops=league_ops,
        )
        ca_ops = _ca_ops(
            league_ops=league_ops,
            observed_ops=target.ops,
            expected_opponent_ops=expected_opponent_ops,
        )
        rows.append(
            PlayerSeasonCaOps(
                player_id=target.player_id,
                season_id=target.season_id,
                plate_appearances=batter_counts.plate_appearances,
                observed_ops=target.ops,
                league_ops=league_ops,
                expected_opponent_ops=expected_opponent_ops,
                ca_ops=ca_ops,
            )
        )
    return rows


def _expected_opponent_ops(
    *,
    season_id: int,
    faced: Sequence[tuple[int, _Counts]],
    pitcher_totals: dict[tuple[int, int], _Counts],
    league_ops: float | None,
) -> float | None:
    if not faced:
        return None
    weighted_sum = 0.0
    weight = 0
    for pitcher_id, matchup in faced:
        remaining = pitcher_totals[(season_id, pitcher_id)].minus(matchup)
        shrunk = _shrunk_pitcher_ops_allowed(
            remaining_plate_appearances=remaining.plate_appearances,
            pitcher_ops_allowed=_ops_from_counts(remaining),
            league_ops=league_ops,
        )
        if shrunk is None:
            return None
        weighted_sum += matchup.plate_appearances * shrunk
        weight += matchup.plate_appearances
    if weight == 0:
        return None
    return weighted_sum / weight


def _shrunk_pitcher_ops_allowed(
    *,
    remaining_plate_appearances: int,
    pitcher_ops_allowed: float | None,
    league_ops: float | None,
) -> float | None:
    if league_ops is None:
        return None
    if remaining_plate_appearances == 0 or pitcher_ops_allowed is None:
        return league_ops
    n = remaining_plate_appearances
    return (n * pitcher_ops_allowed + SHRINKAGE_K * league_ops) / (n + SHRINKAGE_K)


def _ca_ops(
    *,
    league_ops: float | None,
    observed_ops: float | None,
    expected_opponent_ops: float | None,
) -> float | None:
    if (
        league_ops is None
        or observed_ops is None
        or expected_opponent_ops is None
    ):
        return None
    return league_ops + (observed_ops - expected_opponent_ops)


def _ops_from_counts(counts: _Counts) -> float | None:
    on_base_percentage = _rate(
        counts.hits + counts.walks + counts.hit_by_pitch,
        counts.at_bats
        + counts.walks
        + counts.hit_by_pitch
        + counts.sacrifice_flies,
    )
    slugging_percentage = _rate(_total_bases(counts), counts.at_bats)
    return _ops(on_base_percentage, slugging_percentage)


def _total_bases(counts: _Counts) -> int:
    return (
        counts.singles
        + (2 * counts.doubles)
        + (3 * counts.triples)
        + (4 * counts.home_runs)
    )


def _ops(
    on_base_percentage: float | None,
    slugging_percentage: float | None,
) -> float | None:
    if on_base_percentage is None or slugging_percentage is None:
        return None
    return on_base_percentage + slugging_percentage


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator
