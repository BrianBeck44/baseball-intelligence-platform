"""Orchestrate loading curated teams from the MLB Stats API."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from app.curated.statcast_team_data import (
    get_statcast_game_years,
    get_statcast_team_codes,
)
from app.curated.team_data import load_mlb_teams
from app.mlb.stats_api import fetch_mlb_teams


def load_teams_from_mlb_stats_api(connection: Connection) -> int:
    """Resolve Statcast team codes through the MLB API and upsert them.

    The caller owns the transaction. Exceptions from extraction, the API
    client, or the database loader are not caught here.
    """
    team_codes = get_statcast_team_codes(connection)
    if not team_codes:
        return 0

    seasons = get_statcast_game_years(connection)
    teams = fetch_mlb_teams(team_codes, seasons)
    return load_mlb_teams(connection, teams)
