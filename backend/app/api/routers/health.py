"""Health check endpoints — liveness and readiness probes.

- GET /health       → Liveness check (always returns 200)
- GET /health/ready → Readiness check (verifies DuckDB connectivity)
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from starlette.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger

router = APIRouter(tags=["health"])
log = get_logger("conflu.api.health")

VERSION = "0.2.0"


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness check.

    Returns simple status to confirm the API is running.
    """
    return {
        "status": "ok",
        "service": "conflu-api",
        "version": VERSION,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health/ready")
async def readiness_check() -> JSONResponse:
    """Readiness check — verifies DuckDB connectivity.

    Per ADR-001/D-32, DuckDB is an optional, non-load-bearing store: it is only
    read on-demand by backtest/risk. The readiness probe therefore reports the
    database as the sole dependency; it must NOT gate on the (retired)
    indicator-cache tables, which would mark a healthy API as degraded once the
    legacy indicator_values rows are dropped.

    Returns:
        - 200 with {"status": "healthy", "checks": {...}} if the DB is reachable
        - 503 with {"status": "degraded", "checks": {...}} if it is not
    """
    db_ok = False

    try:
        with get_db(read_only=True, timeout_s=settings.api.health_db_timeout_s) as con:
            con.sql("SELECT 1").fetchone()
            db_ok = True
    except Exception:
        log.exception("health_readiness_db_check_failed")

    status = "healthy" if db_ok else "degraded"
    status_code = 200 if db_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "service": "conflu-api",
            "version": VERSION,
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": {
                "database": db_ok,
            },
        },
    )
