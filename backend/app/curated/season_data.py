"""Load curated seasons into curated.season."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import MetaData, Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class CuratedSeason:
    season_year: int
    all_star_date: date | None
    trade_deadline_date: date | None


@dataclass(frozen=True)
class SeasonLoadResult:
    seasons_loaded: int


def load_seasons(
    connection: Connection,
    seasons: Sequence[CuratedSeason],
) -> SeasonLoadResult:
    """Upsert curated seasons into curated.season.

    Conflict is resolved on ``season_year``. ``all_star_date`` and
    ``trade_deadline_date`` are updated; ``season_id`` is left
    unchanged. The caller owns the transaction.
    """
    unique_seasons = _unique_seasons(seasons)
    seasons_loaded = len(unique_seasons)
    if seasons_loaded == 0:
        return SeasonLoadResult(seasons_loaded=0)

    rows = [
        {
            "season_year": season.season_year,
            "all_star_date": season.all_star_date,
            "trade_deadline_date": season.trade_deadline_date,
        }
        for season in unique_seasons
    ]

    table = _curated_table(connection, "season")
    statement = insert(table).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.season_year],
        set_={
            "all_star_date": statement.excluded.all_star_date,
            "trade_deadline_date": statement.excluded.trade_deadline_date,
        },
    )
    connection.execute(statement)
    return SeasonLoadResult(seasons_loaded=seasons_loaded)


def _unique_seasons(seasons: Sequence[CuratedSeason]) -> list[CuratedSeason]:
    by_season_year: dict[int, CuratedSeason] = {}
    for season in seasons:
        by_season_year[season.season_year] = season
    return list(by_season_year.values())


def _curated_table(connection: Connection, table_name: str) -> Table:
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        schema="curated",
        autoload_with=connection,
    )
