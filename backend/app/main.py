"""FastAPI application for the Baseball Intelligence Platform."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.players import router as players_router

app = FastAPI(
    title="Baseball Intelligence Platform",
    description=(
        "REST API for baseball analytics, including player performance "
        "trends derived from the PostgreSQL analytics layer."
    ),
)


app.include_router(players_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
