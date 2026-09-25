"""Extract distinct MLB player IDs from raw Statcast pitch data."""

from __future__ import annotations

from sqlalchemy import MetaData, Table, select, union
from sqlalchemy.engine import Connection


def get_statcast_player_ids(connection: Connection) -> list[int]:
    """Return sorted distinct batter and pitcher IDs from raw.statcast_pitch."""
    metadata = MetaData()
    statcast_pitch = Table(
        "statcast_pitch",
        metadata,
        schema="raw",
        autoload_with=connection,
    )

    batter_ids = select(statcast_pitch.c.batter.label("mlb_player_id")).where(
        statcast_pitch.c.batter.is_not(None)
    )
    pitcher_ids = select(statcast_pitch.c.pitcher.label("mlb_player_id")).where(
        statcast_pitch.c.pitcher.is_not(None)
    )
    player_ids = union(batter_ids, pitcher_ids).subquery()
    statement = select(player_ids.c.mlb_player_id).order_by(
        player_ids.c.mlb_player_id
    )

    return [int(player_id) for player_id in connection.execute(statement).scalars()]
