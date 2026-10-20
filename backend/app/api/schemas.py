"""Pydantic response models for the FastAPI application."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class PlayerGameRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    game_id: int
    team_id: int
    game_date: date
    season_game_number: int
    plate_appearances: int
    rolling_14_ops: float | None
    season_ops: float | None
    ops_difference: float | None


class PlayerGameHistoryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: int
    player_name: str
    season_id: int
    games: list[PlayerGameRecord]
