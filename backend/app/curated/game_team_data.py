"""Load Statcast game-team pairs into curated.game_team."""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass

from sqlalchemy import MetaData, Table, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from app.curated.statcast_game_team_data import StatcastGameTeam


@dataclass(frozen=True)
class GameTeamLoadResult:
    game_teams_supplied: int
    game_teams_loaded: int


def load_game_teams(
    connection: Connection,
    game_teams: Collection[StatcastGameTeam],
) -> GameTeamLoadResult:
    """Upsert Statcast game-team pairs into curated.game_team.

    Conflict is resolved on ``(game_id, team_id)``. ``home_away`` is
    updated; ``game_team_id`` is left unchanged. The caller owns the
    transaction.
    """
    game_teams_supplied = len(game_teams)
    if game_teams_supplied == 0:
        return GameTeamLoadResult(game_teams_supplied=0, game_teams_loaded=0)

    unique_game_teams = _unique_game_teams(game_teams)
    game_ids = _game_ids_by_mlb_game_pk(
        connection,
        {game_team.mlb_game_pk for game_team in unique_game_teams},
    )
    team_ids = _team_ids_by_code(
        connection,
        {game_team.team_code for game_team in unique_game_teams},
    )

    rows = [
        {
            "game_id": game_ids[game_team.mlb_game_pk],
            "team_id": team_ids[game_team.team_code],
            "home_away": game_team.home_away,
        }
        for game_team in unique_game_teams
    ]

    table = _curated_table(connection, "game_team")
    statement = insert(table).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.game_id, table.c.team_id],
        set_={"home_away": statement.excluded.home_away},
    )
    connection.execute(statement)
    return GameTeamLoadResult(
        game_teams_supplied=game_teams_supplied,
        game_teams_loaded=game_teams_supplied,
    )


def _unique_game_teams(
    game_teams: Collection[StatcastGameTeam],
) -> list[StatcastGameTeam]:
    by_key: dict[tuple[int, str], StatcastGameTeam] = {}
    for game_team in game_teams:
        by_key[(game_team.mlb_game_pk, game_team.team_code)] = game_team
    return list(by_key.values())


def _curated_table(connection: Connection, table_name: str) -> Table:
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        schema="curated",
        autoload_with=connection,
    )


def _game_ids_by_mlb_game_pk(
    connection: Connection,
    mlb_game_pks: Iterable[int],
) -> dict[int, int]:
    game_pks = set(mlb_game_pks)
    game = _curated_table(connection, "game")
    rows = connection.execute(
        select(game.c.mlb_game_pk, game.c.game_id).where(
            game.c.mlb_game_pk.in_(game_pks)
        )
    ).all()
    mapping = {int(mlb_game_pk): int(game_id) for mlb_game_pk, game_id in rows}

    missing = sorted(game_pks - mapping.keys())
    if missing:
        raise ValueError(
            "No curated.game exists for mlb_game_pk="
            + ", ".join(str(game_pk) for game_pk in missing)
        )
    return mapping


def _team_ids_by_code(
    connection: Connection,
    team_codes: Iterable[str],
) -> dict[str, int]:
    codes = set(team_codes)
    team = _curated_table(connection, "team")
    rows = connection.execute(
        select(team.c.code, team.c.team_id).where(team.c.code.in_(codes))
    ).all()
    mapping = {str(code): int(team_id) for code, team_id in rows}

    missing = sorted(codes - mapping.keys())
    if missing:
        raise ValueError(
            "No curated.team exists for code=" + ", ".join(missing)
        )
    return mapping
