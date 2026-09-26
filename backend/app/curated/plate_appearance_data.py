"""Load Statcast plate appearances into curated.plate_appearance."""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass

from sqlalchemy import MetaData, Table, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from app.curated.statcast_plate_appearance_data import StatcastPlateAppearance


@dataclass(frozen=True)
class PlateAppearanceLoadResult:
    plate_appearances_supplied: int
    plate_appearances_loaded: int


def load_plate_appearances(
    connection: Connection,
    plate_appearances: Collection[StatcastPlateAppearance],
) -> PlateAppearanceLoadResult:
    """Upsert Statcast plate appearances into curated.plate_appearance.

    Conflict is resolved on ``(game_id, at_bat_number)``. Non-key fields
    are updated; ``plate_appearance_id`` is left unchanged. The caller
    owns the transaction.
    """
    plate_appearances_supplied = len(plate_appearances)
    if plate_appearances_supplied == 0:
        return PlateAppearanceLoadResult(
            plate_appearances_supplied=0,
            plate_appearances_loaded=0,
        )

    unique_plate_appearances = _unique_plate_appearances(plate_appearances)
    game_ids = _game_ids_by_mlb_game_pk(
        connection,
        {pa.mlb_game_pk for pa in unique_plate_appearances},
    )
    player_ids = _player_ids_by_mlb_player_id(
        connection,
        {pa.batter_id for pa in unique_plate_appearances}
        | {pa.pitcher_id for pa in unique_plate_appearances},
    )
    team_ids = _team_ids_by_code(
        connection,
        {pa.batter_team_code for pa in unique_plate_appearances}
        | {pa.pitcher_team_code for pa in unique_plate_appearances},
    )
    outcome_ids = _outcome_type_ids_by_code(
        connection,
        {pa.outcome_code for pa in unique_plate_appearances},
    )

    rows = [
        {
            "game_id": game_ids[pa.mlb_game_pk],
            "at_bat_number": pa.at_bat_number,
            "batter_id": player_ids[pa.batter_id],
            "pitcher_id": player_ids[pa.pitcher_id],
            "batter_team_id": team_ids[pa.batter_team_code],
            "pitcher_team_id": team_ids[pa.pitcher_team_code],
            "inning": pa.inning,
            "inning_topbot": pa.inning_topbot,
            "outcome_type_id": (
                None if pa.outcome_code is None else outcome_ids[pa.outcome_code]
            ),
        }
        for pa in unique_plate_appearances
    ]

    table = _curated_table(connection, "plate_appearance")
    statement = insert(table).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.game_id, table.c.at_bat_number],
        set_={
            "batter_id": statement.excluded.batter_id,
            "pitcher_id": statement.excluded.pitcher_id,
            "batter_team_id": statement.excluded.batter_team_id,
            "pitcher_team_id": statement.excluded.pitcher_team_id,
            "inning": statement.excluded.inning,
            "inning_topbot": statement.excluded.inning_topbot,
            "outcome_type_id": statement.excluded.outcome_type_id,
        },
    )
    connection.execute(statement)
    return PlateAppearanceLoadResult(
        plate_appearances_supplied=plate_appearances_supplied,
        plate_appearances_loaded=plate_appearances_supplied,
    )


def _unique_plate_appearances(
    plate_appearances: Collection[StatcastPlateAppearance],
) -> list[StatcastPlateAppearance]:
    by_key: dict[tuple[int, int], StatcastPlateAppearance] = {}
    for plate_appearance in plate_appearances:
        by_key[
            (plate_appearance.mlb_game_pk, plate_appearance.at_bat_number)
        ] = plate_appearance
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


def _outcome_type_ids_by_code(
    connection: Connection,
    outcome_codes: Iterable[str | None],
) -> dict[str, int]:
    codes = {code for code in outcome_codes if code is not None}
    if not codes:
        return {}

    outcome_type = _curated_table(connection, "outcome_type")
    rows = connection.execute(
        select(outcome_type.c.code, outcome_type.c.id).where(
            outcome_type.c.code.in_(codes)
        )
    ).all()
    mapping = {str(code): int(type_id) for code, type_id in rows}

    missing = sorted(codes - mapping.keys())
    if missing:
        raise ValueError(
            "No curated.outcome_type exists for code=" + ", ".join(missing)
        )
    return mapping
