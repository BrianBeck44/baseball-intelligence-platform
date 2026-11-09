"""Read one player-season CA-OPS line from analytics."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping


@dataclass(frozen=True)
class PlayerSeasonCaOpsRow:
    player_id: int
    season_id: int
    plate_appearances: int
    observed_ops: float | None
    league_ops: float | None
    expected_opponent_ops: float | None
    ca_ops: float | None


@dataclass(frozen=True)
class PlayerSeasonCaOpsListRow:
    player_id: int
    full_name: str
    season_id: int
    season_year: int | None
    plate_appearances: int
    observed_ops: float | None
    league_ops: float | None
    expected_opponent_ops: float | None
    ca_ops: float | None


def get_player_season_ca_ops(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
) -> PlayerSeasonCaOpsRow | None:
    """Return the stored CA-OPS line for one player and season, if any.

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
                    plate_appearances,
                    observed_ops,
                    league_ops,
                    expected_opponent_ops,
                    ca_ops
                FROM analytics.player_season_ca_ops
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
    return _ca_ops_row(row)


def list_player_season_ca_ops_for_season(
    connection: Connection,
    *,
    season_id: int,
) -> list[PlayerSeasonCaOpsListRow]:
    """Return stored CA-OPS lines for every player in one season.

    Rates are returned as stored. Null rates stay null. An unknown or
    empty season returns an empty list. The caller owns the transaction.
    """
    rows = (
        connection.execute(
            text(
                """
                SELECT
                    ca_ops.player_id,
                    player.full_name,
                    ca_ops.season_id,
                    season.season_year,
                    ca_ops.plate_appearances,
                    ca_ops.observed_ops,
                    ca_ops.league_ops,
                    ca_ops.expected_opponent_ops,
                    ca_ops.ca_ops
                FROM analytics.player_season_ca_ops AS ca_ops
                INNER JOIN curated.player AS player
                  ON player.player_id = ca_ops.player_id
                LEFT JOIN curated.season AS season
                  ON season.season_id = ca_ops.season_id
                WHERE ca_ops.season_id = :season_id
                ORDER BY player.full_name, ca_ops.player_id
                """
            ),
            {"season_id": season_id},
        )
        .mappings()
        .all()
    )
    return [_ca_ops_list_row(row) for row in rows]


def _ca_ops_row(row: RowMapping) -> PlayerSeasonCaOpsRow:
    return PlayerSeasonCaOpsRow(
        player_id=int(row["player_id"]),
        season_id=int(row["season_id"]),
        plate_appearances=int(row["plate_appearances"]),
        observed_ops=_optional_float(row["observed_ops"]),
        league_ops=_optional_float(row["league_ops"]),
        expected_opponent_ops=_optional_float(row["expected_opponent_ops"]),
        ca_ops=_optional_float(row["ca_ops"]),
    )


def _ca_ops_list_row(row: RowMapping) -> PlayerSeasonCaOpsListRow:
    season_year = row["season_year"]
    return PlayerSeasonCaOpsListRow(
        player_id=int(row["player_id"]),
        full_name=str(row["full_name"]),
        season_id=int(row["season_id"]),
        season_year=None if season_year is None else int(season_year),
        plate_appearances=int(row["plate_appearances"]),
        observed_ops=_optional_float(row["observed_ops"]),
        league_ops=_optional_float(row["league_ops"]),
        expected_opponent_ops=_optional_float(row["expected_opponent_ops"]),
        ca_ops=_optional_float(row["ca_ops"]),
    )


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
