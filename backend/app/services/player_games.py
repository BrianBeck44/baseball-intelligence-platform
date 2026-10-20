"""Coordinate player existence checks and game-history retrieval."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from app.analytics.player_performance_trends_data import (
    get_player,
    list_player_game_history,
)
from app.api.schemas import PlayerGameHistoryResponse, PlayerGameRecord


class PlayerNotFoundError(LookupError):
    """Raised when a requested player does not exist."""


def get_player_game_history(
    connection: Connection,
    *,
    player_id: int,
    season_id: int,
    limit: int,
) -> PlayerGameHistoryResponse:
    """Return a player's season game history, or raise if unknown."""
    player = get_player(connection, player_id)
    if player is None:
        raise PlayerNotFoundError(f"Player {player_id} was not found.")

    rows = list_player_game_history(
        connection,
        player_id=player_id,
        season_id=season_id,
        limit=limit,
    )
    return PlayerGameHistoryResponse(
        player_id=player.player_id,
        player_name=player.full_name,
        season_id=season_id,
        games=[
            PlayerGameRecord(
                game_id=row.game_id,
                team_id=row.team_id,
                game_date=row.game_date,
                season_game_number=row.season_game_number,
                plate_appearances=row.plate_appearances,
                rolling_14_ops=row.rolling_14_ops,
                season_ops=row.season_ops,
                ops_difference=row.ops_difference,
            )
            for row in rows
        ],
    )
