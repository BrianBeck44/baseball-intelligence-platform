"""Orchestrate loading curated pitches from raw Statcast data."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Connection

from app.curated.pitch_data import load_pitches, transform_pitches
from app.curated.statcast_pitch_data import get_statcast_pitches


@dataclass(frozen=True)
class PitchLoadOrchestrationResult:
    pitches_found: int
    pitches_loaded: int


def load_pitches_from_statcast(
    connection: Connection,
) -> PitchLoadOrchestrationResult:
    """Extract, transform, and insert curated pitches into curated.pitch.

    The caller owns the transaction. Exceptions from extraction,
    transformation, or loading are not caught here.
    """
    pitches = get_statcast_pitches(connection)
    curated_pitches = transform_pitches(connection, pitches)
    pitches_loaded = load_pitches(connection, curated_pitches)
    return PitchLoadOrchestrationResult(
        pitches_found=len(pitches),
        pitches_loaded=pitches_loaded,
    )
