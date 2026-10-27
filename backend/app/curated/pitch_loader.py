"""Orchestrate loading curated pitches from raw Statcast data."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Connection

from app.curated.pitch_data import load_pitches, transform_pitches
from app.curated.statcast_pitch_data import (
    PITCH_EXTRACT_CHUNK_SIZE,
    iter_statcast_pitch_chunks,
)


@dataclass(frozen=True)
class PitchLoadOrchestrationResult:
    pitches_found: int
    pitches_loaded: int


def load_pitches_from_statcast(
    connection: Connection,
    *,
    chunk_size: int = PITCH_EXTRACT_CHUNK_SIZE,
) -> PitchLoadOrchestrationResult:
    """Extract, transform, and insert curated pitches in bounded chunks.

    Each chunk is transformed and persisted before the next chunk is
    fetched. The caller owns the transaction. Exceptions from
    extraction, transformation, or loading are not caught here.
    """
    pitches_found = 0
    pitches_loaded = 0
    for chunk in iter_statcast_pitch_chunks(
        connection,
        chunk_size=chunk_size,
    ):
        pitches_found += len(chunk)
        curated_pitches = transform_pitches(connection, chunk)
        pitches_loaded += load_pitches(connection, curated_pitches)
    return PitchLoadOrchestrationResult(
        pitches_found=pitches_found,
        pitches_loaded=pitches_loaded,
    )
