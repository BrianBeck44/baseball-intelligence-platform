"""Load Statcast game-player triples into curated.game_player."""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass

from sqlalchemy import MetaData, Table, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from app.curated.statcast_game_player_data import StatcastGamePlayer


@dataclass(frozen=True)
class GamePlayerLoadResult:
    game_players_supplied: int
    game_players_loaded: int


def load_game_players(
    connection: Connection,
    game_players: Collection[StatcastGamePlayer],
) -> GamePlayerLoadResult:
    """Upsert Statcast game-player triples into curated.game_player.

    Conflict is resolved on ``(game_id, player_id, team_id)``.
    ``game_player_id`` is left unchanged. The caller owns the
    transaction.
    """
    game_players_supplied = len(game_players)
    if game_players_supplied == 0:
        return GamePlayerLoadResult(
            game_players_supplied=0,
            game_players_loaded=0,
        )

    unique_game_players = _unique_game_players(game_players)
    game_ids = _game_ids_by_mlb_game_pk(
        connection,
        {game_player.mlb_game_pk for game_player in unique_game_players},
    )
    player_ids = _player_ids_by_mlb_player_id(
        connection,
        {game_player.player_id for game_player in unique_game_players},
    )
    team_ids = _team_ids_by_code(
        connection,
        {game_player.team_code for game_player in unique_game_players},
    )

    rows = [
        {
            "game_id": game_ids[game_player.mlb_game_pk],
            "player_id": player_ids[game_player.player_id],
            "team_id": team_ids[game_player.team_code],
        }
        for game_player in unique_game_players
    ]

    table = _curated_table(connection, "game_player")
    statement = insert(table).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.game_id, table.c.player_id, table.c.team_id],
        set_={
            "game_id": statement.excluded.game_id,
            "player_id": statement.excluded.player_id,
            "team_id": statement.excluded.team_id,
        },
    )
    connection.execute(statement)
    return GamePlayerLoadResult(
        game_players_supplied=game_players_supplied,
        game_players_loaded=game_players_supplied,
    )


def _unique_game_players(
    game_players: Collection[StatcastGamePlayer],
) -> list[StatcastGamePlayer]:
    by_key: dict[tuple[int, int, str], StatcastGamePlayer] = {}
    for game_player in game_players:
        by_key[
            (game_player.mlb_game_pk, game_player.player_id, game_player.team_code)
        ] = game_player
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


def _player_ids_by_mlb_player_id(
    connection: Connection,
    mlb_player_ids: Iterable[int],
) -> dict[int, int]:
    player_ids = set(mlb_player_ids)
    player = _curated_table(connection, "player")
    rows = connection.execute(
        select(player.c.mlb_player_id, player.c.player_id).where(
            player.c.mlb_player_id.in_(player_ids)
        )
    ).all()
    mapping = {
        int(mlb_player_id): int(player_id) for mlb_player_id, player_id in rows
    }

    missing = sorted(player_ids - mapping.keys())
    if missing:
        raise ValueError(
            "No curated.player exists for mlb_player_id="
            + ", ".join(str(player_id) for player_id in missing)
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
