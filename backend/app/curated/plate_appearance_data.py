"""Transform extracted Statcast plate appearances and persist curated records."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import MetaData, Table, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from app.curated.statcast_plate_appearance_data import StatcastPlateAppearance

_PLATE_APPEARANCE_INSERT_BATCH_SIZE = 500


@dataclass(frozen=True)
class CuratedPlateAppearance:
    game_id: int
    at_bat_number: int
    batter_id: int
    pitcher_id: int
    batter_team_id: int
    pitcher_team_id: int
    inning: int
    inning_topbot: str
    outcome_type_id: int | None
    stand: str
    p_throws: str


@dataclass(frozen=True)
class PlateAppearanceLoadResult:
    plate_appearances_supplied: int
    plate_appearances_loaded: int


def transform_plate_appearances(
    connection: Connection,
    plate_appearances: Sequence[StatcastPlateAppearance],
) -> list[CuratedPlateAppearance]:
    """Resolve Statcast plate appearances to curated identifiers.

    Lookups only; the caller owns the transaction. Missing required
    curated rows raise ValueError. A null ``outcome_code`` becomes
    ``outcome_type_id=None``.
    """
    if not plate_appearances:
        return []

    game_ids = _game_ids_by_mlb_game_pk(
        connection,
        {pa.mlb_game_pk for pa in plate_appearances},
    )
    missing_games = sorted(
        {pa.mlb_game_pk for pa in plate_appearances} - game_ids.keys()
    )
    if missing_games:
        raise ValueError(
            "No curated game found for MLB game PK "
            + ", ".join(str(game_pk) for game_pk in missing_games)
        )

    player_ids = _player_ids_by_mlb_player_id(
        connection,
        {pa.batter_id for pa in plate_appearances}
        | {pa.pitcher_id for pa in plate_appearances},
    )
    missing_batters = sorted(
        {pa.batter_id for pa in plate_appearances} - player_ids.keys()
    )
    if missing_batters:
        raise ValueError(
            "No curated player found for MLB player ID "
            + ", ".join(str(player_id) for player_id in missing_batters)
        )
    missing_pitchers = sorted(
        {pa.pitcher_id for pa in plate_appearances} - player_ids.keys()
    )
    if missing_pitchers:
        raise ValueError(
            "No curated player found for MLB player ID "
            + ", ".join(str(player_id) for player_id in missing_pitchers)
        )

    team_ids = _team_ids_by_code(
        connection,
        {pa.batter_team_code for pa in plate_appearances}
        | {pa.pitcher_team_code for pa in plate_appearances},
    )
    missing_batter_teams = sorted(
        {pa.batter_team_code for pa in plate_appearances} - team_ids.keys()
    )
    if missing_batter_teams:
        raise ValueError(
            "No curated team found for team code "
            + ", ".join(missing_batter_teams)
        )
    missing_pitcher_teams = sorted(
        {pa.pitcher_team_code for pa in plate_appearances} - team_ids.keys()
    )
    if missing_pitcher_teams:
        raise ValueError(
            "No curated team found for team code "
            + ", ".join(missing_pitcher_teams)
        )

    outcome_ids = _outcome_type_ids_by_code(
        connection,
        {pa.outcome_code for pa in plate_appearances},
    )
    missing_outcomes = sorted(
        {
            pa.outcome_code
            for pa in plate_appearances
            if pa.outcome_code is not None
        }
        - outcome_ids.keys()
    )
    if missing_outcomes:
        raise ValueError(
            "No curated outcome type found for outcome code "
            + ", ".join(missing_outcomes)
        )

    return [
        CuratedPlateAppearance(
            game_id=game_ids[pa.mlb_game_pk],
            at_bat_number=pa.at_bat_number,
            batter_id=player_ids[pa.batter_id],
            pitcher_id=player_ids[pa.pitcher_id],
            batter_team_id=team_ids[pa.batter_team_code],
            pitcher_team_id=team_ids[pa.pitcher_team_code],
            inning=pa.inning,
            inning_topbot=pa.inning_topbot,
            outcome_type_id=(
                None if pa.outcome_code is None else outcome_ids[pa.outcome_code]
            ),
            stand=pa.stand,
            p_throws=pa.p_throws,
        )
        for pa in plate_appearances
    ]


def load_plate_appearances(
    connection: Connection,
    plate_appearances: Collection[CuratedPlateAppearance],
) -> PlateAppearanceLoadResult:
    """Upsert curated plate appearances into curated.plate_appearance.

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

    rows = [
        {
            "game_id": pa.game_id,
            "at_bat_number": pa.at_bat_number,
            "batter_id": pa.batter_id,
            "pitcher_id": pa.pitcher_id,
            "batter_team_id": pa.batter_team_id,
            "pitcher_team_id": pa.pitcher_team_id,
            "inning": pa.inning,
            "inning_topbot": pa.inning_topbot,
            "outcome_type_id": pa.outcome_type_id,
            "stand": pa.stand,
            "p_throws": pa.p_throws,
        }
        for pa in plate_appearances
    ]

    table = _curated_table(connection, "plate_appearance")
    for start in range(0, len(rows), _PLATE_APPEARANCE_INSERT_BATCH_SIZE):
        batch = rows[start : start + _PLATE_APPEARANCE_INSERT_BATCH_SIZE]
        statement = insert(table).values(batch)
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
                "stand": statement.excluded.stand,
                "p_throws": statement.excluded.p_throws,
            },
        )
        connection.execute(statement)
    return PlateAppearanceLoadResult(
        plate_appearances_supplied=plate_appearances_supplied,
        plate_appearances_loaded=plate_appearances_supplied,
    )


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
    if not game_pks:
        return {}

    game = _curated_table(connection, "game")
    rows = connection.execute(
        select(game.c.mlb_game_pk, game.c.game_id).where(
            game.c.mlb_game_pk.in_(game_pks)
        )
    ).all()
    return {int(mlb_game_pk): int(game_id) for mlb_game_pk, game_id in rows}


def _player_ids_by_mlb_player_id(
    connection: Connection,
    mlb_player_ids: Iterable[int],
) -> dict[int, int]:
    player_ids = set(mlb_player_ids)
    if not player_ids:
        return {}

    player = _curated_table(connection, "player")
    rows = connection.execute(
        select(player.c.mlb_player_id, player.c.player_id).where(
            player.c.mlb_player_id.in_(player_ids)
        )
    ).all()
    return {
        int(mlb_player_id): int(player_id) for mlb_player_id, player_id in rows
    }


def _team_ids_by_code(
    connection: Connection,
    team_codes: Iterable[str],
) -> dict[str, int]:
    codes = set(team_codes)
    if not codes:
        return {}

    team = _curated_table(connection, "team")
    rows = connection.execute(
        select(team.c.code, team.c.team_id).where(team.c.code.in_(codes))
    ).all()
    return {str(code): int(team_id) for code, team_id in rows}


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
    return {str(code): int(type_id) for code, type_id in rows}
