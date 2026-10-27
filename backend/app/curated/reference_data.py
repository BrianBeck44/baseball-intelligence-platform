"""Controlled reference data for the curated baseball model."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import MetaData, Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class ReferenceValue:
    code: str
    name: str


PITCH_TYPES = (
    ReferenceValue("CH", "Changeup"),
    ReferenceValue("CS", "Slow Curve"),
    ReferenceValue("CU", "Curveball"),
    ReferenceValue("EP", "Eephus"),
    ReferenceValue("FA", "Other"),
    ReferenceValue("FC", "Cutter"),
    ReferenceValue("FF", "4-Seam Fastball"),
    ReferenceValue("FO", "Forkball"),
    ReferenceValue("FS", "Splitter"),
    ReferenceValue("KC", "Knuckle Curve"),
    ReferenceValue("KN", "Knuckleball"),
    ReferenceValue("PO", "Pitchout"),
    ReferenceValue("SC", "Screwball"),
    ReferenceValue("SI", "Sinker"),
    ReferenceValue("SL", "Slider"),
    ReferenceValue("ST", "Sweeper"),
    ReferenceValue("SV", "Slurve"),
    ReferenceValue("UN", "Unknown"),
)

PITCH_OUTCOME_TYPES = (
    ReferenceValue("automatic_ball", "Automatic Ball"),
    ReferenceValue("automatic_strike", "Automatic Strike"),
    ReferenceValue("ball", "Ball"),
    ReferenceValue("blocked_ball", "Blocked Ball"),
    ReferenceValue("bunt_foul_tip", "Bunt Foul Tip"),
    ReferenceValue("called_strike", "Called Strike"),
    ReferenceValue("foul", "Foul"),
    ReferenceValue("foul_bunt", "Foul Bunt"),
    ReferenceValue("foul_tip", "Foul Tip"),
    ReferenceValue("hit_by_pitch", "Hit By Pitch"),
    ReferenceValue("hit_into_play", "Hit Into Play"),
    ReferenceValue("missed_bunt", "Missed Bunt"),
    ReferenceValue("pitchout", "Pitchout"),
    ReferenceValue("swinging_pitchout", "Swinging Pitchout"),
    ReferenceValue("swinging_strike", "Swinging Strike"),
    ReferenceValue("swinging_strike_blocked", "Swinging Strike Blocked"),
)

OUTCOME_TYPES = (
    ReferenceValue("catcher_interf", "Catcher Interference"),
    ReferenceValue("double", "Double"),
    ReferenceValue("double_play", "Double Play"),
    ReferenceValue("field_error", "Field Error"),
    ReferenceValue("fielders_choice", "Fielder's Choice"),
    ReferenceValue("fielders_choice_out", "Fielder's Choice Out"),
    ReferenceValue("field_out", "Field Out"),
    ReferenceValue("force_out", "Force Out"),
    ReferenceValue("grounded_into_double_play", "Grounded Into Double Play"),
    ReferenceValue("hit_by_pitch", "Hit By Pitch"),
    ReferenceValue("home_run", "Home Run"),
    ReferenceValue("intent_walk", "Intentional Walk"),
    ReferenceValue("sac_bunt", "Sacrifice Bunt"),
    ReferenceValue("sac_fly", "Sacrifice Fly"),
    ReferenceValue("sac_fly_double_play", "Sacrifice Fly Double Play"),
    ReferenceValue("single", "Single"),
    ReferenceValue("strikeout", "Strikeout"),
    ReferenceValue("strikeout_double_play", "Strikeout Double Play"),
    ReferenceValue("triple", "Triple"),
    ReferenceValue("triple_play", "Triple Play"),
    ReferenceValue("truncated_pa", "Truncated Plate Appearance"),
    ReferenceValue("walk", "Walk"),
)


GAME_TYPES = (
    ReferenceValue(code="R", name="Regular Season"),
)


def _table(connection: Connection, table_name: str) -> Table:
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        schema="curated",
        autoload_with=connection,
    )


def _load_reference_values(
    connection: Connection,
    table_name: str,
    values: tuple[ReferenceValue, ...],
) -> None:
    if not values:
        return

    table = _table(connection, table_name)

    rows = [
        {
            "code": value.code,
            "name": value.name,
        }
        for value in values
    ]

    statement = insert(table).values(rows)

    statement = statement.on_conflict_do_update(
        index_elements=[table.c.code],
        set_={"name": statement.excluded.name},
    )

    connection.execute(statement)


def load_reference_data(connection: Connection) -> None:
    """Load controlled reference data into the curated schema."""
    _load_reference_values(
        connection,
        "pitch_type",
        PITCH_TYPES,
    )
    _load_reference_values(
        connection,
        "pitch_outcome_type",
        PITCH_OUTCOME_TYPES,
    )
    _load_reference_values(
        connection,
        "outcome_type",
        OUTCOME_TYPES,
    )
    _load_reference_values(
        connection,
        "game_type",
        GAME_TYPES,
    )