"""Extract distinct plate appearances from raw Statcast pitch data."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import ColumnElement, MetaData, Table, func, select
from sqlalchemy.engine import Connection


_CONTEXT_FIELDS = (
    "batter",
    "home_team",
    "away_team",
    "inning",
    "inning_topbot",
    "stand",
    "p_throws",
)


@dataclass(frozen=True)
class StatcastPlateAppearance:
    mlb_game_pk: int
    at_bat_number: int
    batter_id: int
    pitcher_id: int
    batter_team_code: str
    pitcher_team_code: str
    inning: int
    inning_topbot: str
    stand: str
    p_throws: str
    outcome_code: str | None


def get_statcast_plate_appearances(
    connection: Connection,
) -> list[StatcastPlateAppearance]:
    """Return one StatcastPlateAppearance per game and at-bat.

    Rows missing required plate-appearance context are ignored. Only
    ``Top`` and ``Bot`` half-innings are accepted. Conflicting non-null
    contextual or ``events`` values for the same plate appearance raise
    ValueError. Multiple pitchers in one plate appearance are allowed;
    ``pitcher_id`` is taken from the lowest ``pitch_number``.
    """
    metadata = MetaData()
    statcast_pitch = Table(
        "statcast_pitch",
        metadata,
        schema="raw",
        autoload_with=connection,
    )

    complete_rows = (
        statcast_pitch.c.game_pk.is_not(None)
        & statcast_pitch.c.at_bat_number.is_not(None)
        & statcast_pitch.c.batter.is_not(None)
        & statcast_pitch.c.pitcher.is_not(None)
        & statcast_pitch.c.home_team.is_not(None)
        & statcast_pitch.c.away_team.is_not(None)
        & statcast_pitch.c.inning.is_not(None)
        & statcast_pitch.c.inning_topbot.in_(("Top", "Bot"))
        & statcast_pitch.c.stand.in_(("L", "R", "S"))
        & statcast_pitch.c.p_throws.in_(("L", "R"))
    )

    for field_name in _CONTEXT_FIELDS:
        _raise_if_conflicting(
            connection,
            statcast_pitch,
            complete_rows,
            statcast_pitch.c[field_name],
            field_name,
        )
    _raise_if_conflicting(
        connection,
        statcast_pitch,
        complete_rows,
        statcast_pitch.c.events,
        "events",
    )

    first_pitch_numbers = (
        select(
            statcast_pitch.c.game_pk,
            statcast_pitch.c.at_bat_number,
            func.min(statcast_pitch.c.pitch_number).label("pitch_number"),
        )
        .where(complete_rows)
        .group_by(
            statcast_pitch.c.game_pk,
            statcast_pitch.c.at_bat_number,
        )
        .subquery()
    )
    first_pitchers = (
        select(
            statcast_pitch.c.game_pk,
            statcast_pitch.c.at_bat_number,
            statcast_pitch.c.pitcher,
        )
        .where(complete_rows)
        .join(
            first_pitch_numbers,
            (statcast_pitch.c.game_pk == first_pitch_numbers.c.game_pk)
            & (
                statcast_pitch.c.at_bat_number
                == first_pitch_numbers.c.at_bat_number
            )
            & (
                statcast_pitch.c.pitch_number
                == first_pitch_numbers.c.pitch_number
            ),
        )
        .subquery()
    )

    rows = connection.execute(
        select(
            statcast_pitch.c.game_pk,
            statcast_pitch.c.at_bat_number,
            statcast_pitch.c.batter,
            first_pitchers.c.pitcher,
            statcast_pitch.c.home_team,
            statcast_pitch.c.away_team,
            statcast_pitch.c.inning,
            statcast_pitch.c.inning_topbot,
            statcast_pitch.c.stand,
            statcast_pitch.c.p_throws,
            func.max(statcast_pitch.c.events).label("events"),
        )
        .join(
            first_pitchers,
            (statcast_pitch.c.game_pk == first_pitchers.c.game_pk)
            & (
                statcast_pitch.c.at_bat_number
                == first_pitchers.c.at_bat_number
            ),
        )
        .where(complete_rows)
        .group_by(
            statcast_pitch.c.game_pk,
            statcast_pitch.c.at_bat_number,
            statcast_pitch.c.batter,
            first_pitchers.c.pitcher,
            statcast_pitch.c.home_team,
            statcast_pitch.c.away_team,
            statcast_pitch.c.inning,
            statcast_pitch.c.inning_topbot,
            statcast_pitch.c.stand,
            statcast_pitch.c.p_throws,
        )
        .order_by(statcast_pitch.c.game_pk, statcast_pitch.c.at_bat_number)
    ).all()

    plate_appearances: list[StatcastPlateAppearance] = []
    for row in rows:
        inning_topbot = str(row.inning_topbot)
        if inning_topbot == "Top":
            batter_team_code = str(row.away_team)
            pitcher_team_code = str(row.home_team)
        else:
            batter_team_code = str(row.home_team)
            pitcher_team_code = str(row.away_team)

        plate_appearances.append(
            StatcastPlateAppearance(
                mlb_game_pk=int(row.game_pk),
                at_bat_number=int(row.at_bat_number),
                batter_id=int(row.batter),
                pitcher_id=int(row.pitcher),
                batter_team_code=batter_team_code,
                pitcher_team_code=pitcher_team_code,
                inning=int(row.inning),
                inning_topbot=inning_topbot,
                stand=str(row.stand),
                p_throws=str(row.p_throws),
                outcome_code=None if row.events is None else str(row.events),
            )
        )
    return plate_appearances


def _raise_if_conflicting(
    connection: Connection,
    statcast_pitch: Table,
    complete_rows: ColumnElement[bool],
    column: ColumnElement,
    field_name: str,
) -> None:
    conflicting = connection.execute(
        select(
            statcast_pitch.c.game_pk,
            statcast_pitch.c.at_bat_number,
        )
        .where(complete_rows, column.is_not(None))
        .group_by(statcast_pitch.c.game_pk, statcast_pitch.c.at_bat_number)
        .having(func.count(func.distinct(column)) > 1)
        .order_by(statcast_pitch.c.game_pk, statcast_pitch.c.at_bat_number)
    ).all()
    if not conflicting:
        return

    details = ", ".join(
        f"game_pk={int(game_pk)}, at_bat_number={int(at_bat_number)}"
        for game_pk, at_bat_number in conflicting
    )
    raise ValueError(
        f"Conflicting {field_name} values in raw.statcast_pitch for {details}"
    )
