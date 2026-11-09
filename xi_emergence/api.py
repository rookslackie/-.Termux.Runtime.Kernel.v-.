"""Ξ.Emergence · api.py — the field's HTTP surface."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .engine import EmergenceEngine
from .field import GLYPH_OPERATORS, OPERATORS


class OperatorRequest(BaseModel):
    operator: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str
    actor_id: str = "hunter"


class ReplayRequest(BaseModel):
    operators: list[dict[str, Any]] = Field(default_factory=list)
    duration: float = 1.0


def create_router(engine: EmergenceEngine) -> APIRouter:
    router = APIRouter(prefix="/api/emergence", tags=["Emergence"])

    @router.get("")
    def capabilities() -> dict[str, Any]:
        return {
            "field": "Kuramoto phase network",
            "glyphs": GLYPH_OPERATORS,
            "operators": list(OPERATORS),
            "execution_class": "local exact integration; not physical quantum hardware",
        }

    @router.get("/state")
    def state() -> dict[str, Any]:
        return engine.snapshot()

    @router.get("/topology")
    def topology() -> dict[str, Any]:
        return engine.field.topology()

    @router.get("/history")
    def history(limit: int = 240) -> dict[str, Any]:
        samples = list(engine.field.history)
        return {"samples": samples[-max(1, min(limit, 600)):]}

    @router.post("/operators")
    def operator(request: OperatorRequest) -> dict[str, Any]:
        try:
            return engine.act(
                request.operator, request.parameters,
                actor_id=request.actor_id, idempotency_key=request.idempotency_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/replay")
    def replay(request: ReplayRequest) -> dict[str, Any]:
        try:
            return engine.replay(request.operators, duration=request.duration)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router
