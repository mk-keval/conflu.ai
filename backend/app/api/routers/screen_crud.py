"""Screen configuration CRUD API router.

CRUD operations for saved screen configurations, version management,
and screen replay.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from starlette.responses import JSONResponse

from backend.app.api.dependencies import ScreenEngineDep, ScreenReplayDep
from backend.app.api.schemas import (
    ApiResponse,
    CreateScreenRequest,
    MetaInfo,
    ReplayRequest,
    ReplayResultResponse,
    ReplayStartResponse,
    ScreenDetail,
    ScreenListItem,
    ScreenVersionSummary,
    UpdateScreenRequest,
)
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.infrastructure.screener.screen_replay import ScreenReplay

log = get_logger("conflu.api.screens")
router = APIRouter(prefix="/screens", tags=["screener"])


# ── Screen CRUD ──


@router.get(
    "",
    summary="List saved screen configurations",
    response_description="List of saved screen summaries",
)
async def list_screens() -> ApiResponse[list[ScreenListItem]]:
    """List all saved screen configurations for the current user."""
    with get_db(read_only=True) as con:
        rows = con.sql(
            """
            SELECT id, name, description, version, is_public,
                   created_at, updated_at, tags
            FROM screen_configs
            ORDER BY updated_at DESC
            """,
        ).fetchdf()

    screens = []
    for _, row in rows.iterrows():
        tags = row.get("tags", "[]")
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []
        screens.append(ScreenListItem(
            id=row["id"],
            name=row["name"],
            description=row.get("description", ""),
            version=row["version"],
            is_public=bool(row.get("is_public", False)),
            created_at=str(row.get("created_at", "")),
            updated_at=str(row.get("updated_at", "")),
            tags=tags,
        ))

    return ApiResponse(data=screens, meta=MetaInfo())


@router.get(
    "/{screen_id}",
    summary="Get screen configuration detail",
    response_description="Full screen detail",
)
async def get_screen(screen_id: str) -> ApiResponse[ScreenDetail]:
    """Get full details of a saved screen configuration."""
    with get_db(read_only=True) as con:
        row = con.sql(
            "SELECT * FROM screen_configs WHERE id = ?",
            params=[screen_id],
        ).fetchdf()

    if row.empty:
        raise HTTPException(status_code=404, detail="Screen not found")

    r = row.iloc[0]
    detail = ScreenDetail(
        id=r["id"],
        user_id=r.get("user_id", "default"),
        name=r["name"],
        description=r.get("description", ""),
        filter_json=r["filter_json"],
        asset_classes=json.loads(r.get("asset_classes", "[]")),
        timeframes=json.loads(r.get("timeframes", '["1D","4h"]')),
        tags=json.loads(r.get("tags", "[]")),
        version=r["version"],
        is_public=bool(r.get("is_public", False)),
        created_at=str(r.get("created_at", "")),
        updated_at=str(r.get("updated_at", "")),
    )

    return ApiResponse(data=detail, meta=MetaInfo())


@router.post(
    "",
    summary="Create a new screen configuration",
    status_code=201,
)
async def create_screen(
    request: CreateScreenRequest,
) -> ApiResponse[ScreenDetail]:
    """Create a new saved screen configuration."""
    screen_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    with get_db() as con:
        con.sql(
            """
            INSERT INTO screen_configs (id, user_id, name, description, filter_json,
                                        asset_classes, timeframes, tags, version, is_public,
                                        created_at, updated_at)
            VALUES (?, 'default', ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            params=[
                screen_id,
                request.name,
                request.description or "",
                request.filter_json,
                json.dumps(request.asset_classes or ["equities", "crypto"]),
                json.dumps(request.timeframes or ["1D", "4h"]),
                json.dumps(request.tags or []),
                request.is_public,
                now,
                now,
            ],
        )

    detail = ScreenDetail(
        id=screen_id,
        name=request.name,
        description=request.description or "",
        filter_json=request.filter_json,
        asset_classes=request.asset_classes or ["equities", "crypto"],
        timeframes=request.timeframes or ["1D", "4h"],
        tags=request.tags or [],
        version=1,
        is_public=request.is_public,
        created_at=now,
        updated_at=now,
    )

    return ApiResponse(data=detail, meta=MetaInfo())


@router.put(
    "/{screen_id}",
    summary="Update a screen configuration",
)
async def update_screen(
    screen_id: str,
    request: UpdateScreenRequest,
) -> ApiResponse[ScreenDetail]:
    """Update an existing saved screen configuration (creates new version)."""
    with get_db(read_only=True) as con:
        existing = con.sql(
            "SELECT * FROM screen_configs WHERE id = ?",
            params=[screen_id],
        ).fetchdf()

    if existing.empty:
        raise HTTPException(status_code=404, detail="Screen not found")

    current = existing.iloc[0]
    now = datetime.now(UTC).isoformat()
    new_version = current["version"] + 1

    # Snapshot current version before updating
    with get_db() as con:
        version_id = str(uuid.uuid4())
        con.sql(
            """
            INSERT INTO screen_versions (id, screen_config_id, version, name,
                                         filter_json, asset_classes, timeframes, tags,
                                         created_at, snapshot_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            params=[
                version_id,
                screen_id,
                current["version"],
                current["name"],
                current["filter_json"],
                current["asset_classes"],
                current["timeframes"],
                current["tags"],
                now,
                None,
            ],
        )

        con.sql(
            """
            UPDATE screen_configs
            SET name = ?, description = ?, filter_json = ?,
                asset_classes = ?, timeframes = ?, tags = ?,
                is_public = ?, version = ?, updated_at = ?
            WHERE id = ?
            """,
            params=[
                request.name or current["name"],
                request.description if request.description is not None else current.get("description", ""),
                request.filter_json or current["filter_json"],
                json.dumps(request.asset_classes) if request.asset_classes is not None else current["asset_classes"],
                json.dumps(request.timeframes) if request.timeframes is not None else current["timeframes"],
                json.dumps(request.tags) if request.tags is not None else current["tags"],
                request.is_public if request.is_public is not None else current["is_public"],
                new_version,
                now,
                screen_id,
            ],
        )

    detail = ScreenDetail(
        id=screen_id,
        name=request.name or current["name"],
        description=request.description if request.description is not None else current.get("description", ""),
        filter_json=request.filter_json or current["filter_json"],
        asset_classes=request.asset_classes or json.loads(current["asset_classes"]),
        timeframes=request.timeframes or json.loads(current["timeframes"]),
        tags=request.tags or json.loads(current["tags"]),
        version=new_version,
        is_public=request.is_public if request.is_public is not None else bool(current["is_public"]),
        created_at=str(current.get("created_at", "")),
        updated_at=now,
    )

    return ApiResponse(data=detail, meta=MetaInfo())


@router.delete(
    "/{screen_id}",
    summary="Delete a screen configuration",
)
async def delete_screen(screen_id: str) -> ApiResponse[dict[str, str]]:
    """Delete a saved screen configuration and its versions."""
    with get_db() as con:
        result = con.sql(
            "DELETE FROM screen_configs WHERE id = ?",
            params=[screen_id],
        )
        con.sql(
            "DELETE FROM screen_versions WHERE screen_config_id = ?",
            params=[screen_id],
        )

    if result.fetchone() is None:
        raise HTTPException(status_code=404, detail="Screen not found")

    return ApiResponse(data={"status": "deleted", "id": screen_id}, meta=MetaInfo())


# ── Screen Version Management ──


@router.get(
    "/{screen_id}/versions",
    summary="List versions of a screen",
)
async def list_screen_versions(
    screen_id: str,
) -> ApiResponse[list[ScreenVersionSummary]]:
    """List all versions of a saved screen configuration."""
    with get_db(read_only=True) as con:
        rows = con.sql(
            """
            SELECT version, name, created_at
            FROM screen_versions
            WHERE screen_config_id = ?
            ORDER BY version DESC
            """,
            params=[screen_id],
        ).fetchdf()

    versions = [
        ScreenVersionSummary(
            version=row["version"],
            name=row["name"],
            created_at=str(row.get("created_at", "")),
        )
        for _, row in rows.iterrows()
    ]

    return ApiResponse(data=versions, meta=MetaInfo())


@router.post(
    "/{screen_id}/versions/{version}/revert",
    summary="Revert a screen to a previous version",
)
async def revert_screen_version(
    screen_id: str,
    version: int,
) -> ApiResponse[ScreenDetail]:
    """Revert a screen configuration to a previous version."""
    with get_db(read_only=True) as con:
        version_row = con.sql(
            "SELECT * FROM screen_versions WHERE screen_config_id = ? AND version = ?",
            params=[screen_id, version],
        ).fetchdf()

    if version_row.empty:
        raise HTTPException(status_code=404, detail="Version not found")

    v = version_row.iloc[0]
    now = datetime.now(UTC).isoformat()

    with get_db() as con:
        current = con.sql(
            "SELECT version FROM screen_configs WHERE id = ?",
            params=[screen_id],
        ).fetchdf()

        if current.empty:
            raise HTTPException(status_code=404, detail="Screen not found")

        new_version = int(current.iloc[0]["version"]) + 1

        con.sql(
            """
            UPDATE screen_configs
            SET name = ?, filter_json = ?, asset_classes = ?,
                timeframes = ?, tags = ?, version = ?, updated_at = ?
            WHERE id = ?
            """,
            params=[
                v["name"],
                v["filter_json"],
                v["asset_classes"],
                v["timeframes"],
                v["tags"],
                new_version,
                now,
                screen_id,
            ],
        )

    return await get_screen(screen_id)


# ── Screen Replay ──


@router.post(
    "/replay",
    summary="Start a screen replay",
)
async def start_replay(
    request: ReplayRequest,
    engine: ScreenReplayDep,
) -> ApiResponse[ReplayStartResponse]:
    """Start a historical screen replay."""
    from backend.app.infrastructure.screener.configs import ScreenConfig

    # Load the screen config to get filter pipeline
    with get_db(read_only=True) as con:
        row = con.sql(
            "SELECT * FROM screen_configs WHERE id = ?",
            params=[request.screen_config_id],
        ).fetchdf()

    if row.empty:
        raise HTTPException(status_code=404, detail="Screen not found")

    r = row.iloc[0]
    screen_config = ScreenConfig(
        name=r["name"],
        filters=[],
        timeframes=json.loads(r.get("timeframes", '["1D","4h"]')),
        description=r.get("description", ""),
    )

    replay = ScreenReplay()
    result = await replay.replay(
        screen_config=screen_config,
        symbols=None,
    )

    if result:
        result_id = await replay.cache_results(
            screen_config_id=request.screen_config_id,
            version=request.version,
            result=result,
        )
    else:
        result_id = ""

    return ApiResponse(
        data=ReplayStartResponse(result_id=result_id, status="running"),
        meta=MetaInfo(),
    )


@router.get(
    "/{screen_config_id}/replay",
    summary="Get cached replay results",
)
async def get_replay_result(
    screen_config_id: str,
    version: int = 1,
) -> ApiResponse[ReplayResultResponse]:
    """Get cached replay results for a screen configuration."""
    replay = ScreenReplay()
    result = await replay.get_cached_results(
        screen_config_id=screen_config_id,
        version=version,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="No replay results found")

    return ApiResponse(
        data=ReplayResultResponse(
            id=result.get("id", ""),
            screen_config_id=screen_config_id,
            version=version,
            start_date=result.get("start_date", ""),
            end_date=result.get("end_date", ""),
            total_days=result.get("total_days", 0),
            avg_match_count=result.get("avg_match_count"),
            max_match_count=result.get("max_match_count"),
            min_match_count=result.get("min_match_count"),
            total_signals=result.get("total_signals"),
            win_rate=result.get("win_rate"),
            avg_return=result.get("avg_return"),
            total_return=result.get("total_return"),
            sharpe=result.get("sharpe"),
            max_drawdown=result.get("max_drawdown"),
            equity_curve=result.get("equity_curve", result.get("equity_curve_json", [])),
            match_series=result.get("match_series", result.get("match_series_json", [])),
        ),
        meta=MetaInfo(),
    )
