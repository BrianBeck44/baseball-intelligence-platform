"""Team lookup routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Connection

from app.api.schemas import TeamListResponse
from app.core.db import get_connection
from app.services.lookups import get_teams_for_season

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=TeamListResponse)
def read_teams(
    season_id: Annotated[int, Query(ge=1)],
    connection: Annotated[Connection, Depends(get_connection)],
) -> TeamListResponse:
    """Return teams with batting history for one season."""
    return get_teams_for_season(connection, season_id=season_id)
