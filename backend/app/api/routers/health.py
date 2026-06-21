"""Health check endpoints — liveness and readiness probes.

- GET /health       → Liveness check (always returns 200)
- GET /health/ready → Readiness check (verifies DuckDB connectivity)
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from starlette.responses import JSONResponse

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
    """Readiness check — verifies DuckDB connectivity and indicator cache.

    Returns:
        - 200 with {"status": "healthy", "checks": {...}} if all pass
        - 503 with {"status": "degraded", "checks": {...}} if any fail
    """
    db_ok = False
    cache_ok = False

    try:
        with get_db(read_only=True, timeout_s=5.0) as con:
            con.sql("SELECT 1").fetchone()
            db_ok = True

            # Check if indicator_values table exists
            result = con.sql(
                "SELECT COUNT(*) as cnt FROM information_schema.tables "
                "WHERE table_name = 'indicator_values'"
            ).fetchone()
            cache_ok = (result and result[0] > 0) if result else False
    except Exception:
        log.exception("health_readiness_db_check_failed")

    all_ok = db_ok and cache_ok
    status = "healthy" if all_ok else "degraded"
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "service": "conflu-api",
            "version": VERSION,
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": {
                "database": db_ok,
                "indicator_cache": cache_ok,
            },
        },
    )
