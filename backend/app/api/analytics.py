"""Read-only analytics lookup routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Connection

from app.api.schemas import SeasonCaOpsAnalyticsResponse
from app.core.db import get_connection
from app.services.season_ca_ops_analytics import (
    get_season_ca_ops_analytics_response,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/season-ca-ops", response_model=SeasonCaOpsAnalyticsResponse)
def read_season_ca_ops_analytics(
    season_id: Annotated[int, Query(ge=1)],
    connection: Annotated[Connection, Depends(get_connection)],
) -> SeasonCaOpsAnalyticsResponse:
    """Return stored CA-OPS lines for every player in one season."""
    return get_season_ca_ops_analytics_response(
        connection,
        season_id=season_id,
    )
