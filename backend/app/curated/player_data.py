"""Load MLB player identity into curated.player."""

from __future__ import annotations

from collections.abc import Collection

from sqlalchemy import MetaData, Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from app.mlb.stats_api import MlbPlayer


def load_mlb_players(
    connection: Connection,
    players: Collection[MlbPlayer],
) -> int:
    """Upsert MLB players into curated.player.

    Conflict is resolved on ``mlb_player_id``. ``full_name`` is updated;
    ``player_id`` is left unchanged. The caller owns the transaction.
    """
    supplied_count = len(players)
    if supplied_count == 0:
        return 0

    rows = [
        {
            "mlb_player_id": player.mlb_player_id,
            "full_name": player.full_name,
        }
        for player in _unique_players(players)
    ]

    table = _player_table(connection)
    statement = insert(table).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.mlb_player_id],
        set_={"full_name": statement.excluded.full_name},
    )
    connection.execute(statement)
    return supplied_count


def _unique_players(players: Collection[MlbPlayer]) -> list[MlbPlayer]:
    by_mlb_player_id: dict[int, MlbPlayer] = {}
    for player in players:
        by_mlb_player_id[player.mlb_player_id] = player
    return list(by_mlb_player_id.values())


def _player_table(connection: Connection) -> Table:
    metadata = MetaData()
    return Table(
        "player",
        metadata,
        schema="curated",
        autoload_with=connection,
    )
