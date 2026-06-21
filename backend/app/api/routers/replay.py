"""Screen sharing resolution API router.

Dedicated endpoint for resolving shared screen tokens.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from starlette.responses import JSONResponse

from backend.app.api.dependencies import ScreenSharingDep
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger

log = get_logger("conflu.api.shared")
router = APIRouter(prefix="/shared", tags=["screener"])


@router.get(
    "/{token}",
    summary="Resolve a shared screen configuration",
)
async def resolve_shared_screen(
    token: str,
    sharing: ScreenSharingDep,
) -> JSONResponse:
    """Resolve a shared screen configuration from a token.

    Validates the HMAC signature and expiry, then returns the
    full screen configuration if valid.
    """
    payload = sharing.validate_token(token)
    if payload is None:
        raise HTTPException(
            status_code=403,
            detail="Invalid or expired share token",
        )

    screen_id = payload["screen_id"]
    # version = payload.get("version", 1)

    with get_db(read_only=True) as con:
        row = con.sql(
            "SELECT * FROM screen_configs WHERE id = ?",
            params=[screen_id],
        ).fetchdf()

    if row.empty:
        raise HTTPException(status_code=404, detail="Screen not found")

    r = row.iloc[0]
    return JSONResponse(content={
        "id": r["id"],
        "name": r["name"],
        "description": r.get("description", ""),
        "filter_json": r["filter_json"],
        "asset_classes": json.loads(r.get("asset_classes", "[]")),
        "timeframes": json.loads(r.get("timeframes", '["1D","4h"]')),
        "version": r["version"],
    })
