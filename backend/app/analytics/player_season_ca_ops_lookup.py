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


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
