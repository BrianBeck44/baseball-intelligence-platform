"""Orchestrate loading curated game-players from raw Statcast identities."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from app.curated.game_player_data import GamePlayerLoadResult, load_game_players
from app.curated.statcast_game_player_data import get_statcast_game_players


def load_game_players_from_statcast(connection: Connection) -> GamePlayerLoadResult:
    """Extract Statcast game-players and upsert them into curated.game_player.

    The caller owns the transaction. Exceptions from extraction or
    loading are not caught here.
    """
    game_players = get_statcast_game_players(connection)
    return load_game_players(connection, game_players)
