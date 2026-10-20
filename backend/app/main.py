"""FastAPI application for the Baseball Intelligence Platform."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.players import router as players_router

_LOCAL_VITE_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)

app = FastAPI(
    title="Baseball Intelligence Platform",
    description=(
        "REST API for baseball analytics, including player performance "
        "trends derived from the PostgreSQL analytics layer."
    ),
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_LOCAL_VITE_ORIGINS),
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(players_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
