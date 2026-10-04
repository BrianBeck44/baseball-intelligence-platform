"""Orchestrate loading analytics pitch-type effectiveness from curated data."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Connection

from app.analytics.player_pitch_type_effectiveness_data import (
    get_player_pitch_type_effectiveness_pitches,
    load_player_pitch_type_effectiveness,
    transform_player_pitch_type_effectiveness,
)


@dataclass(frozen=True)
class PlayerPitchTypeEffectivenessLoadResult:
    extracted_count: int
    transformed_count: int
    loaded_count: int


def load_player_pitch_type_effectiveness_from_curated(
    connection: Connection,
) -> PlayerPitchTypeEffectivenessLoadResult:
    """Extract, transform, and persist pitch-type effectiveness.

    The caller owns the transaction. Exceptions from extraction,
    transformation, or loading are not caught here.
    """
    pitches = get_player_pitch_type_effectiveness_pitches(connection)
    rows = transform_player_pitch_type_effectiveness(connection, pitches)
    loaded_count = load_player_pitch_type_effectiveness(connection, rows)
    return PlayerPitchTypeEffectivenessLoadResult(
        extracted_count=len(pitches),
        transformed_count=len(rows),
        loaded_count=loaded_count,
    )
