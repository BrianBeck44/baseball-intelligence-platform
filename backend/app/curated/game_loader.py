"""Orchestrate loading curated games from raw Statcast identities."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from app.curated.game_data import GameLoadResult, load_games
from app.curated.statcast_game_data import get_statcast_games


def load_games_from_statcast(connection: Connection) -> GameLoadResult:
    """Extract Statcast games and upsert them into curated.game.

    The caller owns the transaction. Exceptions from extraction or
    loading are not caught here.
    """
    games = get_statcast_games(connection)
    return load_games(connection, games)
