"""Screener-specific Pydantic models for filter results and screen runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FilterRunResult(BaseModel):
    """Result of evaluating a single filter expression."""

    model_config = ConfigDict(frozen=True)

    filter_name: str
    category: str
    params: dict[str, Any] = Field(default_factory=dict)
    timeframe: str = "1D"
    matched: int = 0
    total: int = 0
    pass_rate: float = 0.0


class ScreenRunResult(BaseModel):
    """Complete result of a single screen evaluation."""

    model_config = ConfigDict(frozen=True)

    screen_name: str
    timestamp: datetime
    duration_ms: float
    total_symbols: int
    symbols_matched: int
    filter_results: list[FilterRunResult] = Field(default_factory=list)
    symbols: list[dict[str, Any]] = Field(default_factory=list)


class ScreenStreamMessage(BaseModel):
    """WebSocket message sent during screener streaming."""

    model_config = ConfigDict(frozen=True)

    type: Literal["screen_update", "delta_update", "error", "pong"] = "screen_update"
    screen_id: str
    sequence: int = 0
    timestamp: datetime
    interval_ms: float = 5000.0
    results: list[dict[str, Any]] = Field(default_factory=list)
    total_matched: int = 0
    total_symbols: int = 0
    added: list[dict[str, Any]] | None = None
    removed: list[str] | None = None
    updated: list[dict[str, Any]] | None = None
