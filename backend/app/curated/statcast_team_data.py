"""Extract distinct team codes and years from raw Statcast pitch data."""

from __future__ import annotations

from sqlalchemy import MetaData, Table, select, union
from sqlalchemy.engine import Connection


def get_statcast_team_codes(connection: Connection) -> list[str]:
    """Return sorted distinct home and away team codes from raw.statcast_pitch."""
    metadata = MetaData()
    statcast_pitch = Table(
        "statcast_pitch",
        metadata,
        schema="raw",
        autoload_with=connection,
    )

    home_codes = select(statcast_pitch.c.home_team.label("team_code")).where(
        statcast_pitch.c.home_team.is_not(None)
    )
    away_codes = select(statcast_pitch.c.away_team.label("team_code")).where(
        statcast_pitch.c.away_team.is_not(None)
    )
    team_codes = union(home_codes, away_codes).subquery()
    statement = select(team_codes.c.team_code).order_by(team_codes.c.team_code)

    return [str(team_code) for team_code in connection.execute(statement).scalars()]


def get_statcast_game_years(connection: Connection) -> list[int]:
    """Return sorted distinct game_year values from raw.statcast_pitch."""
    metadata = MetaData()
    statcast_pitch = Table(
        "statcast_pitch",
        metadata,
        schema="raw",
        autoload_with=connection,
    )

    statement = (
        select(statcast_pitch.c.game_year)
        .where(statcast_pitch.c.game_year.is_not(None))
        .distinct()
        .order_by(statcast_pitch.c.game_year)
    )
    return [int(game_year) for game_year in connection.execute(statement).scalars()]
