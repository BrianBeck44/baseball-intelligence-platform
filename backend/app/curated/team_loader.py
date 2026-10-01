"""Orchestrate loading curated teams from the MLB Stats API."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from app.curated.team_data import load_mlb_teams
from app.mlb.stats_api import fetch_mlb_teams


def load_teams_from_mlb_stats_api(connection: Connection) -> int:
    """Fetch MLB teams and upsert them into curated.team.

    The caller owns the transaction. Exceptions from the API client or
    database loader are not caught here.
    """
    teams = fetch_mlb_teams()
    return load_mlb_teams(connection, teams)
