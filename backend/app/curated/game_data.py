"""Load Statcast games into curated.game."""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass

from sqlalchemy import MetaData, Table, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from app.curated.statcast_game_data import StatcastGame


@dataclass(frozen=True)
class GameLoadResult:
    games_supplied: int
    games_loaded: int


def load_games(
    connection: Connection,
    games: Collection[StatcastGame],
) -> GameLoadResult:
    """Upsert Statcast games into curated.game.

    Conflict is resolved on ``mlb_game_pk``. ``season_id``,
    ``official_game_date``, and ``game_type_id`` are updated;
    ``game_id`` is left unchanged. The caller owns the transaction.
    """
    games_supplied = len(games)
    if games_supplied == 0:
        return GameLoadResult(games_supplied=0, games_loaded=0)

    unique_games = _unique_games(games)
    season_ids = _season_ids_by_year(
        connection,
        {game.official_game_date.year for game in unique_games},
    )
    game_type_ids = _game_type_ids_by_code(
        connection,
        {game.game_type for game in unique_games},
    )

    rows = [
        {
            "mlb_game_pk": game.mlb_game_pk,
            "season_id": season_ids[game.official_game_date.year],
            "official_game_date": game.official_game_date,
            "game_type_id": game_type_ids[game.game_type],
        }
        for game in unique_games
    ]

    table = _curated_table(connection, "game")
    statement = insert(table).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.mlb_game_pk],
        set_={
            "season_id": statement.excluded.season_id,
            "official_game_date": statement.excluded.official_game_date,
            "game_type_id": statement.excluded.game_type_id,
        },
    )
    connection.execute(statement)
    return GameLoadResult(
        games_supplied=games_supplied,
        games_loaded=games_supplied,
    )


def _unique_games(games: Collection[StatcastGame]) -> list[StatcastGame]:
    by_mlb_game_pk: dict[int, StatcastGame] = {}
    for game in games:
        by_mlb_game_pk[game.mlb_game_pk] = game
    return list(by_mlb_game_pk.values())


def _curated_table(connection: Connection, table_name: str) -> Table:
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        schema="curated",
        autoload_with=connection,
    )


def _season_ids_by_year(
    connection: Connection,
    season_years: Iterable[int],
) -> dict[int, int]:
    years = set(season_years)
    season = _curated_table(connection, "season")
    rows = connection.execute(
        select(season.c.season_year, season.c.season_id).where(
            season.c.season_year.in_(years)
        )
    ).all()
    mapping = {int(year): int(season_id) for year, season_id in rows}

    missing_years = sorted(years - mapping.keys())
    if missing_years:
        raise ValueError(
            "No curated.season exists for season_year="
            + ", ".join(str(year) for year in missing_years)
        )
    return mapping


def _game_type_ids_by_code(
    connection: Connection,
    game_type_codes: Iterable[str],
) -> dict[str, int]:
    codes = set(game_type_codes)
    game_type = _curated_table(connection, "game_type")
    rows = connection.execute(
        select(game_type.c.code, game_type.c.id).where(game_type.c.code.in_(codes))
    ).all()
    mapping = {str(code): int(type_id) for code, type_id in rows}

    missing_codes = sorted(codes - mapping.keys())
    if missing_codes:
        raise ValueError(
            "No curated.game_type exists for code="
            + ", ".join(missing_codes)
        )
    return mapping
