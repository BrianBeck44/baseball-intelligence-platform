"""Read player identity and game history from analytics views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping


@dataclass(frozen=True)
class PlayerIdentity:
    player_id: int
    full_name: str


@dataclass(frozen=True)
class PlayerGameHistoryRow:
    game_id: int
    team_id: int
    game_date: date
    season_game_number: int
    plate_appearances: int
    rolling_14_ops: float | None
    season_ops: float | None
    ops_difference: float | None


def get_player(
    connection: Connection,
    player_id: int,
) -> PlayerIdentity | None:
    """Return curated player identity, or None if the player does not exist."""
    row = (
        connection.execute(
            text(
                """
                SELECT player_id, full_name
                FROM curated.player
                WHERE player_id = :player_id
                """
            ),
            {"player_id": player_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return PlayerIdentity(
        player_id=int(row["player_id"]),
        full_name=str(row["full_name"]),
    )


def list_player_game_history(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
    limit: int,
) -> list[PlayerGameHistoryRow]:
    """Return season game history ordered by game date, game, and team."""
    rows = (
        connection.execute(
            text(
                """
                SELECT
                    game_id,
                    team_id,
                    game_date,
                    season_game_number,
                    plate_appearances,
                    rolling_14_ops,
                    season_ops,
                    rolling_14_ops - season_ops AS ops_difference
                FROM analytics.player_performance_trends
                WHERE player_id = :player_id
                  AND season_id = :season_id
                ORDER BY game_date, game_id, team_id
                LIMIT :row_limit
                """
            ),
            {
                "player_id": player_id,
                "season_id": season_id,
                "row_limit": limit,
            },
        )
        .mappings()
        .all()
    )
    return [_history_row(row) for row in rows]


def _history_row(row: RowMapping) -> PlayerGameHistoryRow:
    return PlayerGameHistoryRow(
        game_id=int(row["game_id"]),
        team_id=int(row["team_id"]),
        game_date=row["game_date"],
        season_game_number=int(row["season_game_number"]),
        plate_appearances=int(row["plate_appearances"]),
        rolling_14_ops=_optional_float(row["rolling_14_ops"]),
        season_ops=_optional_float(row["season_ops"]),
        ops_difference=_optional_float(row["ops_difference"]),
    )


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
