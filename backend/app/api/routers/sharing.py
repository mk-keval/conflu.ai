"""Screen sharing API router.

Share token generation and resolution for saved screen configurations.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from backend.app.api.dependencies import ScreenSharingDep
from backend.app.api.schemas import (
    ApiResponse,
    MetaInfo,
    ScreenDetail,
    ShareTokenRequest,
    ShareTokenResponse,
)
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger

log = get_logger("conflu.api.sharing")
router = APIRouter(prefix="/screens", tags=["screener"])


@router.post(
    "/{screen_id}/share",
    summary="Generate a share token for a screen",
)
async def generate_share_token(
    screen_id: str,
    request: ShareTokenRequest,
    sharing: ScreenSharingDep,
) -> ApiResponse[ShareTokenResponse]:
    """Generate a share token for a saved screen configuration.

    The token is an HMAC-signed, self-contained URL parameter.
    No server-side token storage is required for validation.
    """
    # Verify screen exists
    with get_db(read_only=True) as con:
        row = con.sql(
            "SELECT id, version FROM screen_configs WHERE id = ?",
            params=[screen_id],
        ).fetchdf()

    if row.empty:
        raise HTTPException(status_code=404, detail="Screen not found")

    version = int(row.iloc[0]["version"])
    token = sharing.generate_token(
        screen_id=screen_id,
        version=version,
        expiry_days=request.expiry_days,
    )

    # Decode token to get expir
    import base64
    padded = token + "=" * (4 - len(token) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded).decode()
        data = json.loads(decoded)
        expires_at = data["p"]["expires_at"]
    except Exception:
        expires_at = ""

    return ApiResponse(
        data=ShareTokenResponse(
            token=token,
            url=f"/shared/screen?token={token}",
            expires_at=expires_at,
        ),
        meta=MetaInfo(),
    )



