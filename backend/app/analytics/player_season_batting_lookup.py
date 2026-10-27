"""Read one player-season batting line from analytics."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping


@dataclass(frozen=True)
class SeasonIdentity:
    season_id: int
    season_year: int


@dataclass(frozen=True)
class PlayerSeasonBattingRow:
    player_id: int
    season_id: int
    games: int
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
    batting_average: float | None
    on_base_percentage: float | None
    slugging_percentage: float | None
    ops: float | None
    strikeout_rate: float | None
    walk_rate: float | None


def get_season(
    connection: Connection,
    season_id: int,
) -> SeasonIdentity | None:
    """Return curated season identity, or None if the season does not exist."""
    row = (
        connection.execute(
            text(
                """
                SELECT season_id, season_year
                FROM curated.season
                WHERE season_id = :season_id
                """
            ),
            {"season_id": season_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return SeasonIdentity(
        season_id=int(row["season_id"]),
        season_year=int(row["season_year"]),
    )


def get_player_season_batting(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
) -> PlayerSeasonBattingRow | None:
    """Return the stored batting line for one player and season, if any.

    Rates are returned as stored. Null rates stay null. The caller owns
    the transaction.
    """
    row = (
        connection.execute(
            text(
                """
                SELECT
                    player_id,
                    season_id,
                    games,
                    plate_appearances,
                    at_bats,
                    hits,
                    singles,
                    doubles,
                    triples,
                    home_runs,
                    walks,
                    hit_by_pitch,
                    strikeouts,
                    sacrifice_flies,
                    sacrifice_bunts,
                    batting_average,
                    on_base_percentage,
                    slugging_percentage,
                    ops,
                    strikeout_rate,
                    walk_rate
                FROM analytics.player_season_batting
                WHERE player_id = :player_id
                  AND season_id = :season_id
                """
            ),
            {"player_id": player_id, "season_id": season_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return _batting_row(row)


def _batting_row(row: RowMapping) -> PlayerSeasonBattingRow:
    return PlayerSeasonBattingRow(
        player_id=int(row["player_id"]),
        season_id=int(row["season_id"]),
        games=int(row["games"]),
        plate_appearances=int(row["plate_appearances"]),
        at_bats=int(row["at_bats"]),
        hits=int(row["hits"]),
        singles=int(row["singles"]),
        doubles=int(row["doubles"]),
        triples=int(row["triples"]),
        home_runs=int(row["home_runs"]),
        walks=int(row["walks"]),
        hit_by_pitch=int(row["hit_by_pitch"]),
        strikeouts=int(row["strikeouts"]),
        sacrifice_flies=int(row["sacrifice_flies"]),
        sacrifice_bunts=int(row["sacrifice_bunts"]),
        batting_average=_optional_float(row["batting_average"]),
        on_base_percentage=_optional_float(row["on_base_percentage"]),
        slugging_percentage=_optional_float(row["slugging_percentage"]),
        ops=_optional_float(row["ops"]),
        strikeout_rate=_optional_float(row["strikeout_rate"]),
        walk_rate=_optional_float(row["walk_rate"]),
    )


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
