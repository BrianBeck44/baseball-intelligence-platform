"""Unit tests for curated pitch-loading orchestration."""

from dataclasses import fields
from unittest.mock import MagicMock, patch

import pytest

from app.curated.pitch_data import CuratedPitch
from app.curated.pitch_loader import (
    PitchLoadOrchestrationResult,
    load_pitches_from_statcast,
)
from app.curated.statcast_pitch_data import (
    PITCH_EXTRACT_CHUNK_SIZE,
    StatcastPitch,
)


def _statcast_pitch(
    mlb_game_pk: int,
    at_bat_number: int,
    pitch_number: int,
    *,
    pitch_type_code: str | None = None,
    pitch_outcome_code: str | None = None,
) -> StatcastPitch:
    values: dict[str, object] = {
        field.name: None
        for field in fields(StatcastPitch)
        if field.name not in {"mlb_game_pk", "at_bat_number", "pitch_number"}
    }
    values["pitch_type_code"] = pitch_type_code
    values["pitch_outcome_code"] = pitch_outcome_code
    return StatcastPitch(
        mlb_game_pk=mlb_game_pk,
        at_bat_number=at_bat_number,
        pitch_number=pitch_number,
        **values,  # type: ignore[arg-type]
    )


def _curated_pitch(
    plate_appearance_id: int,
    pitch_number: int,
) -> CuratedPitch:
    values: dict[str, object] = {
        field.name: None
        for field in fields(CuratedPitch)
        if field.name not in {"plate_appearance_id", "pitch_number"}
    }
    return CuratedPitch(
        plate_appearance_id=plate_appearance_id,
        pitch_number=pitch_number,
        **values,  # type: ignore[arg-type]
    )


def test_default_extract_chunk_size_reduces_round_trips():
    assert PITCH_EXTRACT_CHUNK_SIZE >= 5000


def test_empty_statcast_result_loads_nothing():
    connection = MagicMock()

    def fake_iter(connection, *, chunk_size=PITCH_EXTRACT_CHUNK_SIZE):
        return
        yield

    with (
        patch(
            "app.curated.pitch_loader.iter_statcast_pitch_chunks",
            side_effect=fake_iter,
        ) as mock_get,
        patch(
            "app.curated.pitch_loader.transform_pitches",
        ) as mock_transform,
        patch(
            "app.curated.pitch_loader.load_pitches",
        ) as mock_load,
    ):
        result = load_pitches_from_statcast(connection)

    mock_get.assert_called_once_with(
        connection,
        chunk_size=PITCH_EXTRACT_CHUNK_SIZE,
    )
    mock_transform.assert_not_called()
    mock_load.assert_not_called()
    assert result == PitchLoadOrchestrationResult(
        pitches_found=0,
        pitches_loaded=0,
    )
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_extracted_pitches_are_loaded():
    connection = MagicMock()
    pitches = [
        _statcast_pitch(900007001, 1, 1),
        _statcast_pitch(900007002, 2, 1),
    ]
    curated_pitches = [
        _curated_pitch(101, 1),
        _curated_pitch(102, 1),
    ]

    def fake_iter(connection, *, chunk_size=PITCH_EXTRACT_CHUNK_SIZE):
        yield pitches

    with (
        patch(
            "app.curated.pitch_loader.iter_statcast_pitch_chunks",
            side_effect=fake_iter,
        ) as mock_get,
        patch(
            "app.curated.pitch_loader.transform_pitches",
            return_value=curated_pitches,
        ) as mock_transform,
        patch(
            "app.curated.pitch_loader.load_pitches",
            return_value=2,
        ) as mock_load,
    ):
        result = load_pitches_from_statcast(connection)

    mock_get.assert_called_once_with(
        connection,
        chunk_size=PITCH_EXTRACT_CHUNK_SIZE,
    )
    mock_transform.assert_called_once_with(connection, pitches)
    mock_load.assert_called_once_with(connection, curated_pitches)
    assert result == PitchLoadOrchestrationResult(
        pitches_found=2,
        pitches_loaded=2,
    )
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_persistence_result_is_propagated():
    connection = MagicMock()
    pitches = [
        _statcast_pitch(900007003, 1, 1),
        _statcast_pitch(900007004, 1, 2),
    ]
    curated_pitches = [
        _curated_pitch(201, 1),
        _curated_pitch(201, 2),
    ]

    def fake_iter(connection, *, chunk_size=PITCH_EXTRACT_CHUNK_SIZE):
        yield pitches

    with (
        patch(
            "app.curated.pitch_loader.iter_statcast_pitch_chunks",
            side_effect=fake_iter,
        ),
        patch(
            "app.curated.pitch_loader.transform_pitches",
            return_value=curated_pitches,
        ),
        patch(
            "app.curated.pitch_loader.load_pitches",
            return_value=42,
        ),
    ):
        result = load_pitches_from_statcast(connection)

    assert result == PitchLoadOrchestrationResult(
        pitches_found=2,
        pitches_loaded=42,
    )


def test_transforms_and_loads_one_chunk_at_a_time():
    connection = MagicMock()
    events: list[str] = []
    first_chunk = [
        _statcast_pitch(index, 1, 1) for index in range(1, 1001)
    ]
    second_chunk = [_statcast_pitch(1001, 1, 1)]

    def fake_iter(connection, *, chunk_size=PITCH_EXTRACT_CHUNK_SIZE):
        events.append("fetch-1")
        yield first_chunk
        events.append("fetch-2")
        yield second_chunk

    def fake_transform(connection, chunk):
        events.append(f"transform-{len(chunk)}")
        return [_curated_pitch(len(chunk), pitch.pitch_number) for pitch in chunk]

    def fake_load(connection, curated):
        events.append(f"load-{len(curated)}")
        return len(curated)

    with (
        patch(
            "app.curated.pitch_loader.iter_statcast_pitch_chunks",
            side_effect=fake_iter,
        ),
        patch(
            "app.curated.pitch_loader.transform_pitches",
            side_effect=fake_transform,
        ),
        patch(
            "app.curated.pitch_loader.load_pitches",
            side_effect=fake_load,
        ),
    ):
        result = load_pitches_from_statcast(connection)

    assert events == [
        "fetch-1",
        "transform-1000",
        "load-1000",
        "fetch-2",
        "transform-1",
        "load-1",
    ]
    assert result == PitchLoadOrchestrationResult(
        pitches_found=1001,
        pitches_loaded=1001,
    )
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_extraction_errors_propagate():
    connection = MagicMock()

    with (
        patch(
            "app.curated.pitch_loader.iter_statcast_pitch_chunks",
            side_effect=ValueError("conflicting pitch"),
        ),
        patch("app.curated.pitch_loader.transform_pitches") as mock_transform,
        patch("app.curated.pitch_loader.load_pitches") as mock_load,
    ):
        with pytest.raises(ValueError, match="conflicting pitch"):
            load_pitches_from_statcast(connection)

    mock_transform.assert_not_called()
    mock_load.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_transformation_errors_propagate():
    connection = MagicMock()
    pitches = [_statcast_pitch(900007005, 1, 1)]

    def fake_iter(connection, *, chunk_size=PITCH_EXTRACT_CHUNK_SIZE):
        yield pitches

    with (
        patch(
            "app.curated.pitch_loader.iter_statcast_pitch_chunks",
            side_effect=fake_iter,
        ),
        patch(
            "app.curated.pitch_loader.transform_pitches",
            side_effect=ValueError("missing game"),
        ),
        patch("app.curated.pitch_loader.load_pitches") as mock_load,
    ):
        with pytest.raises(ValueError, match="missing game"):
            load_pitches_from_statcast(connection)

    mock_load.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_unknown_pitch_type_in_later_chunk_still_raises():
    connection = MagicMock()
    first_chunk = [_statcast_pitch(900007008, 1, 1, pitch_type_code="FF")]
    second_chunk = [
        _statcast_pitch(900007009, 1, 1, pitch_type_code="ZZZ_MISSING")
    ]

    def fake_iter(connection, *, chunk_size=PITCH_EXTRACT_CHUNK_SIZE):
        yield first_chunk
        yield second_chunk

    def fake_transform(connection, chunk):
        if chunk[0].pitch_type_code == "ZZZ_MISSING":
            raise ValueError(
                "No curated pitch type found for pitch type code ZZZ_MISSING"
            )
        return [_curated_pitch(1, 1)]

    with (
        patch(
            "app.curated.pitch_loader.iter_statcast_pitch_chunks",
            side_effect=fake_iter,
        ),
        patch(
            "app.curated.pitch_loader.transform_pitches",
            side_effect=fake_transform,
        ),
        patch(
            "app.curated.pitch_loader.load_pitches",
            return_value=1,
        ) as mock_load,
    ):
        with pytest.raises(
            ValueError,
            match="No curated pitch type found for pitch type code ZZZ_MISSING",
        ):
            load_pitches_from_statcast(connection)

    mock_load.assert_called_once()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_unknown_pitch_outcome_still_raises():
    connection = MagicMock()
    pitches = [
        _statcast_pitch(
            900007010,
            1,
            1,
            pitch_outcome_code="zzz_missing_pitch_outcome",
        )
    ]

    def fake_iter(connection, *, chunk_size=PITCH_EXTRACT_CHUNK_SIZE):
        yield pitches

    with (
        patch(
            "app.curated.pitch_loader.iter_statcast_pitch_chunks",
            side_effect=fake_iter,
        ),
        patch(
            "app.curated.pitch_loader.transform_pitches",
            side_effect=ValueError(
                "No curated pitch outcome type found for pitch outcome "
                "code zzz_missing_pitch_outcome"
            ),
        ),
        patch("app.curated.pitch_loader.load_pitches") as mock_load,
    ):
        with pytest.raises(
            ValueError,
            match=(
                "No curated pitch outcome type found for pitch outcome "
                "code zzz_missing_pitch_outcome"
            ),
        ):
            load_pitches_from_statcast(connection)

    mock_load.assert_not_called()


def test_persistence_errors_propagate():
    connection = MagicMock()
    pitches = [_statcast_pitch(900007006, 1, 1)]
    curated_pitches = [_curated_pitch(301, 1)]

    def fake_iter(connection, *, chunk_size=PITCH_EXTRACT_CHUNK_SIZE):
        yield pitches

    with (
        patch(
            "app.curated.pitch_loader.iter_statcast_pitch_chunks",
            side_effect=fake_iter,
        ),
        patch(
            "app.curated.pitch_loader.transform_pitches",
            return_value=curated_pitches,
        ),
        patch(
            "app.curated.pitch_loader.load_pitches",
            side_effect=ValueError("insert failed"),
        ),
    ):
        with pytest.raises(ValueError, match="insert failed"):
            load_pitches_from_statcast(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()


def test_orchestration_does_not_manage_transactions():
    connection = MagicMock()

    def fake_iter(connection, *, chunk_size=PITCH_EXTRACT_CHUNK_SIZE):
        return
        yield

    with (
        patch(
            "app.curated.pitch_loader.iter_statcast_pitch_chunks",
            side_effect=fake_iter,
        ),
        patch(
            "app.curated.pitch_loader.transform_pitches",
            return_value=[],
        ),
        patch(
            "app.curated.pitch_loader.load_pitches",
            return_value=0,
        ),
    ):
        load_pitches_from_statcast(connection)

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.begin.assert_not_called()
