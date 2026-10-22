"""Season lookup routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection

from app.api.schemas import SeasonListResponse
from app.core.db import get_connection
from app.services.lookups import get_available_seasons

router = APIRouter(prefix="/seasons", tags=["seasons"])


@router.get("", response_model=SeasonListResponse)
def read_seasons(
    connection: Annotated[Connection, Depends(get_connection)],
) -> SeasonListResponse:
    """Return seasons that have player batting history."""
    return get_available_seasons(connection)
