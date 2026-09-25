"""Extract distinct games from raw Statcast pitch data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import MetaData, Table, func, select
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class StatcastGame:
    mlb_game_pk: int
    official_game_date: date
    game_type: str


def get_statcast_games(connection: Connection) -> list[StatcastGame]:
    """Return one StatcastGame per distinct game_pk in raw.statcast_pitch.

    Rows missing ``game_date`` or ``game_type`` are ignored. Conflicting
    non-null game-level values for the same ``game_pk`` raise ValueError.
    """
    metadata = MetaData()
    statcast_pitch = Table(
        "statcast_pitch",
        metadata,
        schema="raw",
        autoload_with=connection,
    )

    complete_rows = (
        statcast_pitch.c.game_date.is_not(None)
        & statcast_pitch.c.game_type.is_not(None)
    )

    conflicting_game_pks = connection.execute(
        select(statcast_pitch.c.game_pk)
        .where(complete_rows)
        .group_by(statcast_pitch.c.game_pk)
        .having(
            (func.count(func.distinct(statcast_pitch.c.game_date)) > 1)
            | (func.count(func.distinct(statcast_pitch.c.game_type)) > 1)
        )
        .order_by(statcast_pitch.c.game_pk)
    ).scalars().all()

    if conflicting_game_pks:
        game_pks = ", ".join(str(int(game_pk)) for game_pk in conflicting_game_pks)
        raise ValueError(
            "Conflicting game-level values in raw.statcast_pitch for "
            f"game_pk={game_pks}"
        )

    rows = connection.execute(
        select(
            statcast_pitch.c.game_pk,
            statcast_pitch.c.game_date,
            statcast_pitch.c.game_type,
        )
        .where(complete_rows)
        .distinct()
        .order_by(statcast_pitch.c.game_pk)
    ).all()

    return [
        StatcastGame(
            mlb_game_pk=int(row.game_pk),
            official_game_date=row.game_date,
            game_type=str(row.game_type),
        )
        for row in rows
    ]
