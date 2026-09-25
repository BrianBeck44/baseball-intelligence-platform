"""Extract distinct game-player-team triples from raw Statcast pitch data."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import MetaData, Table, case, select, union
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class StatcastGamePlayer:
    mlb_game_pk: int
    player_id: int
    team_code: str


def get_statcast_game_players(connection: Connection) -> list[StatcastGamePlayer]:
    """Return one StatcastGamePlayer per game, player, and team.

    Batters and pitchers are included. Rows missing ``game_pk``, player
    ID, or the half-inning context needed to assign a team are ignored.
    A player who both bats and pitches for the same team appears once.
    """
    metadata = MetaData()
    statcast_pitch = Table(
        "statcast_pitch",
        metadata,
        schema="raw",
        autoload_with=connection,
    )

    batter_team = case(
        (statcast_pitch.c.inning_topbot == "Top", statcast_pitch.c.away_team),
        (statcast_pitch.c.inning_topbot == "Bot", statcast_pitch.c.home_team),
    )
    pitcher_team = case(
        (statcast_pitch.c.inning_topbot == "Top", statcast_pitch.c.home_team),
        (statcast_pitch.c.inning_topbot == "Bot", statcast_pitch.c.away_team),
    )

    context_rows = (
        statcast_pitch.c.game_pk.is_not(None)
        & statcast_pitch.c.home_team.is_not(None)
        & statcast_pitch.c.away_team.is_not(None)
        & statcast_pitch.c.inning_topbot.in_(("Top", "Bot"))
    )

    batter_rows = select(
        statcast_pitch.c.game_pk.label("mlb_game_pk"),
        statcast_pitch.c.batter.label("player_id"),
        batter_team.label("team_code"),
    ).where(
        context_rows,
        statcast_pitch.c.batter.is_not(None),
    )
    pitcher_rows = select(
        statcast_pitch.c.game_pk.label("mlb_game_pk"),
        statcast_pitch.c.pitcher.label("player_id"),
        pitcher_team.label("team_code"),
    ).where(
        context_rows,
        statcast_pitch.c.pitcher.is_not(None),
    )

    game_players = union(batter_rows, pitcher_rows).subquery()
    rows = connection.execute(
        select(
            game_players.c.mlb_game_pk,
            game_players.c.player_id,
            game_players.c.team_code,
        ).order_by(
            game_players.c.mlb_game_pk,
            game_players.c.player_id,
            game_players.c.team_code,
        )
    ).all()

    return [
        StatcastGamePlayer(
            mlb_game_pk=int(row.mlb_game_pk),
            player_id=int(row.player_id),
            team_code=str(row.team_code),
        )
        for row in rows
    ]
