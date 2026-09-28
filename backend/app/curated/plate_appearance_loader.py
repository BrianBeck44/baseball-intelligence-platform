"""Orchestrate loading curated plate appearances from raw Statcast identities."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Connection

from app.curated.plate_appearance_data import (
    PlateAppearanceLoadResult,
    load_plate_appearances,
    transform_plate_appearances,
)
from app.curated.statcast_plate_appearance_data import get_statcast_plate_appearances


@dataclass(frozen=True)
class PlateAppearanceLoadOrchestrationResult:
    plate_appearances_found: int
    plate_appearances_loaded: int


def load_plate_appearances_from_statcast(
    connection: Connection,
) -> PlateAppearanceLoadOrchestrationResult:
    """Extract, transform, and upsert curated plate appearances.

    The caller owns the transaction. Exceptions from extraction,
    transformation, or loading are not caught here.
    """
    plate_appearances = get_statcast_plate_appearances(connection)
    curated_plate_appearances = transform_plate_appearances(
        connection,
        plate_appearances,
    )
    load_result: PlateAppearanceLoadResult = load_plate_appearances(
        connection,
        curated_plate_appearances,
    )
    return PlateAppearanceLoadOrchestrationResult(
        plate_appearances_found=len(plate_appearances),
        plate_appearances_loaded=load_result.plate_appearances_loaded,
    )
