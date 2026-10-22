"""Coordinate season, team, and player selector lookups."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from app.analytics.lookup_data import (
    list_available_seasons,
    list_players_for_season,
    list_teams_for_season,
)
from app.api.schemas import (
    PlayerListResponse,
    PlayerOption,
    SeasonListResponse,
    SeasonRecord,
    TeamListResponse,
    TeamRecord,
)


def get_available_seasons(connection: Connection) -> SeasonListResponse:
    """Return seasons that have batting history."""
    return SeasonListResponse(
        seasons=[
            SeasonRecord(
                season_id=row.season_id,
                season_year=row.season_year,
            )
            for row in list_available_seasons(connection)
        ]
    )


def get_teams_for_season(
    connection: Connection,
    *,
    season_id: int,
) -> TeamListResponse:
    """Return teams with batting history in one season."""
    return TeamListResponse(
        teams=[
            TeamRecord(team_id=row.team_id, name=row.name)
            for row in list_teams_for_season(connection, season_id=season_id)
        ]
    )


def get_players_for_season(
    connection: Connection,
    *,
    season_id: int,
    team_id: int | None,
) -> PlayerListResponse:
    """Return distinct players with batting history in one season."""
    return PlayerListResponse(
        players=[
            PlayerOption(player_id=row.player_id, full_name=row.full_name)
            for row in list_players_for_season(
                connection,
                season_id=season_id,
                team_id=team_id,
            )
        ]
    )
