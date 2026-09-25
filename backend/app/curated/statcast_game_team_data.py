"""Extract distinct game-team pairs from raw Statcast pitch data."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import MetaData, Table, func, select
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class StatcastGameTeam:
    mlb_game_pk: int
    team_code: str
    home_away: str


def get_statcast_game_teams(connection: Connection) -> list[StatcastGameTeam]:
    """Return home and away teams for each distinct game_pk.

    Rows missing ``home_team`` or ``away_team`` are ignored. Conflicting
    non-null team values for the same ``game_pk`` raise ValueError.
    """
    metadata = MetaData()
    statcast_pitch = Table(
        "statcast_pitch",
        metadata,
        schema="raw",
        autoload_with=connection,
    )

    complete_rows = (
        statcast_pitch.c.home_team.is_not(None)
        & statcast_pitch.c.away_team.is_not(None)
    )

    conflicting_home = connection.execute(
        select(statcast_pitch.c.game_pk)
        .where(complete_rows)
        .group_by(statcast_pitch.c.game_pk)
        .having(func.count(func.distinct(statcast_pitch.c.home_team)) > 1)
        .order_by(statcast_pitch.c.game_pk)
    ).scalars().all()
    if conflicting_home:
        game_pks = ", ".join(str(int(game_pk)) for game_pk in conflicting_home)
        raise ValueError(
            "Conflicting home_team values in raw.statcast_pitch for "
            f"game_pk={game_pks}"
        )

    conflicting_away = connection.execute(
        select(statcast_pitch.c.game_pk)
        .where(complete_rows)
        .group_by(statcast_pitch.c.game_pk)
        .having(func.count(func.distinct(statcast_pitch.c.away_team)) > 1)
        .order_by(statcast_pitch.c.game_pk)
    ).scalars().all()
    if conflicting_away:
        game_pks = ", ".join(str(int(game_pk)) for game_pk in conflicting_away)
        raise ValueError(
            "Conflicting away_team values in raw.statcast_pitch for "
            f"game_pk={game_pks}"
        )

    rows = connection.execute(
        select(
            statcast_pitch.c.game_pk,
            statcast_pitch.c.home_team,
            statcast_pitch.c.away_team,
        )
        .where(complete_rows)
        .distinct()
        .order_by(statcast_pitch.c.game_pk)
    ).all()

    game_teams: list[StatcastGameTeam] = []
    for row in rows:
        mlb_game_pk = int(row.game_pk)
        game_teams.append(
            StatcastGameTeam(
                mlb_game_pk=mlb_game_pk,
                team_code=str(row.away_team),
                home_away="AWAY",
            )
        )
        game_teams.append(
            StatcastGameTeam(
                mlb_game_pk=mlb_game_pk,
                team_code=str(row.home_team),
                home_away="HOME",
            )
        )
    return game_teams
