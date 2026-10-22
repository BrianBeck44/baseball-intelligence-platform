"""Read season, team, and player options for the history selector."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping


@dataclass(frozen=True)
class SeasonOptionRow:
    season_id: int
    season_year: int


@dataclass(frozen=True)
class TeamOptionRow:
    team_id: int
    name: str


@dataclass(frozen=True)
class PlayerOptionRow:
    player_id: int
    full_name: str


def list_available_seasons(connection: Connection) -> list[SeasonOptionRow]:
    """Return seasons that have player batting history, newest year first."""
    rows = (
        connection.execute(
            text(
                """
                SELECT s.season_id, s.season_year
                FROM curated.season s
                WHERE EXISTS (
                    SELECT 1
                    FROM analytics.player_performance_trends t
                    WHERE t.season_id = s.season_id
                )
                ORDER BY s.season_year DESC, s.season_id
                """
            )
        )
        .mappings()
        .all()
    )
    return [_season_row(row) for row in rows]


def list_teams_for_season(
    connection: Connection,
    *,
    season_id: int,
) -> list[TeamOptionRow]:
    """Return teams that have batting history in the given season."""
    rows = (
        connection.execute(
            text(
                """
                SELECT tm.team_id, tm.name
                FROM curated.team tm
                WHERE EXISTS (
                    SELECT 1
                    FROM analytics.player_performance_trends t
                    WHERE t.team_id = tm.team_id
                      AND t.season_id = :season_id
                )
                ORDER BY tm.name, tm.team_id
                """
            ),
            {"season_id": season_id},
        )
        .mappings()
        .all()
    )
    return [_team_row(row) for row in rows]


def list_players_for_season(
    connection: Connection,
    *,
    season_id: int,
    team_id: int | None,
) -> list[PlayerOptionRow]:
    """Return distinct batters for a season, optionally limited to one team."""
    rows = (
        connection.execute(
            text(
                """
                SELECT p.player_id, p.full_name
                FROM curated.player p
                WHERE EXISTS (
                    SELECT 1
                    FROM analytics.player_performance_trends t
                    WHERE t.player_id = p.player_id
                      AND t.season_id = :season_id
                      AND (
                          CAST(:team_id AS BIGINT) IS NULL
                          OR t.team_id = CAST(:team_id AS BIGINT)
                      )
                )
                ORDER BY p.full_name, p.player_id
                """
            ),
            {"season_id": season_id, "team_id": team_id},
        )
        .mappings()
        .all()
    )
    return [_player_row(row) for row in rows]


def _season_row(row: RowMapping) -> SeasonOptionRow:
    return SeasonOptionRow(
        season_id=int(row["season_id"]),
        season_year=int(row["season_year"]),
    )


def _team_row(row: RowMapping) -> TeamOptionRow:
    return TeamOptionRow(
        team_id=int(row["team_id"]),
        name=str(row["name"]),
    )


def _player_row(row: RowMapping) -> PlayerOptionRow:
    return PlayerOptionRow(
        player_id=int(row["player_id"]),
        full_name=str(row["full_name"]),
    )
