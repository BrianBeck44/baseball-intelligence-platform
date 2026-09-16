"""V1 Statcast chunk validation and scope filtering.

Validation does not query or write to PostgreSQL. Existing database
source keys are handled later by ON CONFLICT DO NOTHING.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import Any, Iterable

import numpy as np
import pandas as pd


REQUIRED_FIELDS: tuple[str, ...] = (
    "game_pk",
    "at_bat_number",
    "pitch_number",
    "game_type",
)
SOURCE_KEY_FIELDS: tuple[str, ...] = (
    "game_pk",
    "at_bat_number",
    "pitch_number",
)
V1_GAME_TYPE = "R"

MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
INVALID_SOURCE_KEY = "INVALID_SOURCE_KEY"
DUPLICATE_SOURCE_KEY = "DUPLICATE_SOURCE_KEY"

SourceKey = tuple[int, int, int]


@dataclass(frozen=True)
class RejectionRecord:
    """One rejected source row for raw.ingestion_rejection."""

    source_row_number: int
    rejection_reason: str
    source_key: dict[str, Any] | None
    details: dict[str, Any] | None
    raw_row: dict[str, Any]


@dataclass(frozen=True)
class ChunkValidationResult:
    """Validation outcome for one processing chunk."""

    valid_rows: pd.DataFrame
    rejections: list[RejectionRecord]
    records_received: int
    records_filtered: int
    records_rejected: int


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def to_json_safe(value: Any) -> Any:
    """Convert a Pandas/NumPy cell value into a JSON-serializable form."""
    if is_missing(value):
        return None

    if isinstance(value, np.generic):
        if isinstance(value, np.datetime64):
            if np.isnat(value):
                return None
            return pd.Timestamp(value).isoformat()
        value = value.item()
        if is_missing(value):
            return None

    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if isfinite(value) else None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def row_to_raw_json(record: dict[str, Any]) -> dict[str, Any]:
    return {field: to_json_safe(value) for field, value in record.items()}


def build_source_key(record: dict[str, Any]) -> dict[str, Any] | None:
    source_key = {
        field: to_json_safe(record.get(field)) for field in SOURCE_KEY_FIELDS
    }
    if all(value is None for value in source_key.values()):
        return None
    return source_key


def parse_integer_compatible(value: Any) -> int | None:
    """Return an integer if the value is integer-compatible; otherwise None."""
    if is_missing(value) or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(as_float) or not as_float.is_integer():
        return None
    return int(as_float)


def find_missing_required_fields(record: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for field in REQUIRED_FIELDS:
        if field not in record or is_missing(record.get(field)):
            errors.append({"field": field, "issue": "missing"})
    return errors


def find_invalid_source_key_fields(record: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for field in SOURCE_KEY_FIELDS:
        if field not in record or is_missing(record.get(field)):
            continue
        value = record.get(field)
        parsed = parse_integer_compatible(value)
        if parsed is None:
            errors.append(
                {
                    "field": field,
                    "issue": "not_integer_compatible",
                    "value": to_json_safe(value),
                }
            )
            continue
        if parsed <= 0:
            errors.append(
                {
                    "field": field,
                    "issue": "not_positive",
                    "value": parsed,
                }
            )
    return errors


def choose_rejection_reason(errors: Iterable[dict[str, Any]]) -> str:
    issues = {error.get("issue") for error in errors}
    if "missing" in issues:
        return MISSING_REQUIRED_FIELD
    if issues & {"not_integer_compatible", "not_positive"}:
        return INVALID_SOURCE_KEY
    return DUPLICATE_SOURCE_KEY


def is_regular_season(game_type: Any) -> bool:
    """True only for the exact V1 regular-season code 'R'."""
    return isinstance(game_type, str) and game_type == V1_GAME_TYPE


def _parsed_source_key(record: dict[str, Any]) -> SourceKey | None:
    parsed_values: list[int] = []
    for field in SOURCE_KEY_FIELDS:
        parsed = parse_integer_compatible(record.get(field))
        if parsed is None or parsed <= 0:
            return None
        parsed_values.append(parsed)
    return parsed_values[0], parsed_values[1], parsed_values[2]


def validate_statcast_chunk(
    chunk: pd.DataFrame,
    starting_source_row_number: int,
) -> ChunkValidationResult:
    """Validate one Statcast DataFrame chunk.

    ``starting_source_row_number`` is the 1-based CSV data-row number of
    the first row in this chunk. The CSV header is not counted.
    """
    records_received = len(chunk)
    records = chunk.to_dict(orient="records")

    valid_positions: list[int] = []
    rejections: list[RejectionRecord] = []
    records_filtered = 0
    seen_source_keys: dict[SourceKey, int] = {}

    for offset, record in enumerate(records):
        source_row_number = starting_source_row_number + offset
        game_type = record.get("game_type")

        if not is_missing(game_type) and not is_regular_season(game_type):
            records_filtered += 1
            continue

        missing_errors = find_missing_required_fields(record)
        invalid_key_errors = find_invalid_source_key_fields(record)
        field_errors = missing_errors + invalid_key_errors

        if field_errors:
            rejections.append(
                RejectionRecord(
                    source_row_number=source_row_number,
                    rejection_reason=choose_rejection_reason(field_errors),
                    source_key=build_source_key(record),
                    details={"errors": field_errors},
                    raw_row=row_to_raw_json(record),
                )
            )
            continue

        source_key = _parsed_source_key(record)
        if source_key is None:
            raise RuntimeError(
                "Source key passed field validation but could not be parsed."
            )

        first_row_number = seen_source_keys.get(source_key)
        if first_row_number is not None:
            duplicate_error = {
                "issue": "duplicate_source_key",
                "source_key": {
                    "game_pk": source_key[0],
                    "at_bat_number": source_key[1],
                    "pitch_number": source_key[2],
                },
                "first_source_row_number": first_row_number,
            }
            rejections.append(
                RejectionRecord(
                    source_row_number=source_row_number,
                    rejection_reason=DUPLICATE_SOURCE_KEY,
                    source_key=build_source_key(record),
                    details={"errors": [duplicate_error]},
                    raw_row=row_to_raw_json(record),
                )
            )
            continue

        seen_source_keys[source_key] = source_row_number
        valid_positions.append(offset)

    valid_rows = chunk.iloc[valid_positions].copy()
    return ChunkValidationResult(
        valid_rows=valid_rows,
        rejections=rejections,
        records_received=records_received,
        records_filtered=records_filtered,
        records_rejected=len(rejections),
    )
