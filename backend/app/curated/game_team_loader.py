"""Orchestrate loading curated game-teams from raw Statcast data."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from app.curated.game_team_data import GameTeamLoadResult, load_game_teams
from app.curated.statcast_game_team_data import get_statcast_game_teams


def load_game_teams_from_statcast(connection: Connection) -> GameTeamLoadResult:
    """Extract Statcast game-teams and upsert them into curated.game_team.

    The caller owns the transaction. Exceptions from extraction or
    loading are not caught here.
    """
    game_teams = get_statcast_game_teams(connection)
    return load_game_teams(connection, game_teams)
