"""Alert management API router.

CRUD operations for alert rules and alert history viewing.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.api.schemas import (
    AlertDetail,
    AlertHistoryDetail,
    ApiResponse,
    CreateAlertRequest,
    MetaInfo,
    UpdateAlertRequest,
)
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger

log = get_logger("conflu.api.alerts")
router = APIRouter(prefix="/alerts", tags=["screener"])


@router.get(
    "",
    summary="List all active alerts",
)
async def list_alerts() -> ApiResponse[list[AlertDetail]]:
    """List all alert rules for the current user."""
    with get_db(read_only=True) as con:
        rows = con.sql(
            """
            SELECT * FROM alerts
            ORDER BY updated_at DESC
            """,
        ).fetchdf()

    alerts = []
    for _, row in rows.iterrows():
        alerts.append(_row_to_alert_detail(row))

    return ApiResponse(data=alerts, meta=MetaInfo())


@router.get(
    "/{alert_id}",
    summary="Get alert details",
)
async def get_alert(alert_id: str) -> ApiResponse[AlertDetail]:
    """Get full details of an alert rule."""
    with get_db(read_only=True) as con:
        row = con.sql(
            "SELECT * FROM alerts WHERE id = ?",
            params=[alert_id],
        ).fetchdf()

    if row.empty:
        raise HTTPException(status_code=404, detail="Alert not found")

    return ApiResponse(data=_row_to_alert_detail(row.iloc[0]), meta=MetaInfo())


@router.post(
    "",
    summary="Create a new alert rule",
    status_code=201,
)
async def create_alert(
    request: CreateAlertRequest,
) -> ApiResponse[AlertDetail]:
    """Create a new alert rule."""
    alert_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    with get_db() as con:
        con.sql(
            """
            INSERT INTO alerts (id, user_id, name, description, alert_type,
                               condition_json, symbols, timeframes, is_active,
                               cooldown_seconds, trigger_count, created_at, updated_at)
            VALUES (?, 'default', ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            params=[
                alert_id,
                request.name,
                request.description or "",
                request.alert_type,
                request.condition_json,
                json.dumps(request.symbols or []),
                json.dumps(request.timeframes or ["1D"]),
                request.is_active,
                request.cooldown_seconds,
                now,
                now,
            ],
        )

    detail = AlertDetail(
        id=alert_id,
        name=request.name,
        description=request.description or "",
        alert_type=request.alert_type,
        condition_json=request.condition_json,
        symbols=request.symbols or [],
        timeframes=request.timeframes or ["1D"],
        is_active=request.is_active,
        cooldown_seconds=request.cooldown_seconds,
        trigger_count=0,
        created_at=now,
        updated_at=now,
    )

    return ApiResponse(data=detail, meta=MetaInfo())


@router.put(
    "/{alert_id}",
    summary="Update an alert rule",
)
async def update_alert(
    alert_id: str,
    request: UpdateAlertRequest,
) -> ApiResponse[AlertDetail]:
    """Update an existing alert rule."""
    with get_db(read_only=True) as con:
        existing = con.sql(
            "SELECT * FROM alerts WHERE id = ?",
            params=[alert_id],
        ).fetchdf()

    if existing.empty:
        raise HTTPException(status_code=404, detail="Alert not found")

    current = existing.iloc[0]
    now = datetime.now(UTC).isoformat()

    with get_db() as con:
        con.sql(
            """
            UPDATE alerts
            SET name = ?, description = ?, condition_json = ?,
                symbols = ?, timeframes = ?, is_active = ?,
                cooldown_seconds = ?, updated_at = ?
            WHERE id = ?
            """,
            params=[
                request.name or current["name"],
                request.description if request.description is not None else current.get("description", ""),
                request.condition_json or current["condition_json"],
                json.dumps(request.symbols) if request.symbols is not None else current["symbols"],
                json.dumps(request.timeframes) if request.timeframes is not None else current["timeframes"],
                request.is_active if request.is_active is not None else current["is_active"],
                request.cooldown_seconds if request.cooldown_seconds is not None else current["cooldown_seconds"],
                now,
                alert_id,
            ],
        )

    return await get_alert(alert_id)


@router.delete(
    "/{alert_id}",
    summary="Delete an alert rule",
)
async def delete_alert(alert_id: str) -> ApiResponse[dict[str, str]]:
    """Delete an alert rule."""
    with get_db() as con:
        con.sql("DELETE FROM alerts WHERE id = ?", params=[alert_id])
        con.sql("DELETE FROM alert_history WHERE alert_id = ?", params=[alert_id])

    return ApiResponse(data={"status": "deleted", "id": alert_id}, meta=MetaInfo())


@router.patch(
    "/{alert_id}",
    summary="Toggle alert active state",
)
async def toggle_alert(
    alert_id: str,
    body: dict[str, Any],
) -> ApiResponse[AlertDetail]:
    """Toggle an alert's active state."""
    is_active = body.get("is_active", True)
    now = datetime.now(UTC).isoformat()

    with get_db() as con:
        con.sql(
            "UPDATE alerts SET is_active = ?, updated_at = ? WHERE id = ?",
            params=[is_active, now, alert_id],
        )

    return await get_alert(alert_id)


@router.get(
    "/{alert_id}/history",
    summary="Get alert trigger history",
)
async def get_alert_history(
    alert_id: str,
    limit: int = 50,
) -> ApiResponse[list[AlertHistoryDetail]]:
    """Get trigger history for an alert rule."""
    with get_db(read_only=True) as con:
        rows = con.sql(
            """
            SELECT * FROM alert_history
            WHERE alert_id = ?
            ORDER BY triggered_at DESC
            LIMIT ?
            """,
            params=[alert_id, limit],
        ).fetchdf()

    history = [
        AlertHistoryDetail(
            id=row["id"],
            alert_id=row["alert_id"],
            symbol=row.get("symbol"),
            triggered_at=str(row.get("triggered_at", "")),
            condition_matched=row.get("condition_matched"),
            value_at_trigger=row.get("value_at_trigger"),
            threshold=row.get("threshold"),
            dismissed=bool(row.get("dismissed", False)),
        )
        for _, row in rows.iterrows()
    ]

    return ApiResponse(data=history, meta=MetaInfo())


@router.patch(
    "/history/{history_id}",
    summary="Dismiss an alert history entry",
)
async def dismiss_alert_history(
    history_id: str,
) -> ApiResponse[dict[str, str]]:
    """Mark an alert history entry as dismissed."""
    with get_db() as con:
        con.sql(
            "UPDATE alert_history SET dismissed = TRUE WHERE id = ?",
            params=[history_id],
        )

    return ApiResponse(data={"status": "dismissed", "id": history_id}, meta=MetaInfo())


def _row_to_alert_detail(row: Any) -> AlertDetail:
    """Convert a DuckDB row to AlertDetail schema."""
    symbols = row.get("symbols", "[]")
    if isinstance(symbols, str):
        try:
            symbols = json.loads(symbols)
        except (json.JSONDecodeError, TypeError):
            symbols = []

    timeframes = row.get("timeframes", '["1D"]')
    if isinstance(timeframes, str):
        try:
            timeframes = json.loads(timeframes)
        except (json.JSONDecodeError, TypeError):
            timeframes = ["1D"]

    return AlertDetail(
        id=row["id"],
        user_id=row.get("user_id", "default"),
        name=row["name"],
        description=row.get("description", ""),
        alert_type=row["alert_type"],
        condition_json=row["condition_json"],
        symbols=symbols,
        timeframes=timeframes,
        is_active=bool(row.get("is_active", True)),
        cooldown_seconds=row.get("cooldown_seconds", 300),
        last_triggered_at=str(row.get("last_triggered_at", "")) if row.get("last_triggered_at") else None,
        trigger_count=row.get("trigger_count", 0),
        created_at=str(row.get("created_at", "")),
        updated_at=str(row.get("updated_at", "")),
    )
