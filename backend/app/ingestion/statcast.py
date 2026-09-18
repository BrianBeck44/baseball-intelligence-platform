"""Statcast ingestion orchestration and its public result type."""

from dataclasses import dataclass


@dataclass(frozen=True)
class IngestionResult:
    ingestion_batch_id: int
    status: str
    records_received: int
    records_filtered: int
    records_rejected: int
    records_skipped: int
    records_loaded: int
    error_message: str | None
