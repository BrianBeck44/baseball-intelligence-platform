"""Load MLB team identity into curated.team."""

from __future__ import annotations

from collections.abc import Collection

from sqlalchemy import MetaData, Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from app.mlb.stats_api import MlbTeam


def load_mlb_teams(
    connection: Connection,
    teams: Collection[MlbTeam],
) -> int:
    """Upsert MLB teams into curated.team.

    Conflict is resolved on ``code``. ``name`` is updated;
    ``team_id`` is left unchanged. The caller owns the transaction.
    """
    supplied_count = len(teams)
    if supplied_count == 0:
        return 0

    rows = [
        {
            "code": team.code,
            "name": team.name,
        }
        for team in _unique_teams(teams)
    ]

    table = _team_table(connection)
    statement = insert(table).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.code],
        set_={"name": statement.excluded.name},
    )
    connection.execute(statement)
    return supplied_count


def _unique_teams(teams: Collection[MlbTeam]) -> list[MlbTeam]:
    by_code: dict[str, MlbTeam] = {}
    for team in teams:
        by_code[team.code] = team
    return list(by_code.values())


def _team_table(connection: Connection) -> Table:
    metadata = MetaData()
    return Table(
        "team",
        metadata,
        schema="curated",
        autoload_with=connection,
    )
