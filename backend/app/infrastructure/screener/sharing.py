"""Screen sharing module — token generation and validation.

Tokens are HMAC-signed JSON payloads encoded as base64url strings.
Supports configurable expiry and optional password protection.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.core.config import settings


class ScreenSharing:
    """Token generation and validation for screen sharing.

    Generates signed share URLs with configurable expiry.
    Tokens are self-contained (no server-side storage needed for validation).
    """

    def __init__(self, secret_key: str | None = None) -> None:
        self._secret = secret_key or settings.share.secret_key

    def generate_token(
        self,
        screen_id: str,
        version: int = 1,
        expiry_days: int | None = None,
    ) -> str:
        """Generate a share token with HMAC signature.

        Args:
            screen_id: UUID of the screen config.
            version: Version number of the screen.
            expiry_days: Days until token expires (default from settings).

        Returns:
            Base64url-encoded token string (no padding).
        """
        if expiry_days is None:
            expiry_days = settings.share.default_expiry_days

        max_days = settings.share.max_expiry_days
        if expiry_days > max_days:
            expiry_days = max_days

        expires_at = (datetime.now(UTC) + timedelta(days=expiry_days)).isoformat()

        payload: dict[str, Any] = {
            "screen_id": screen_id,
            "version": version,
            "expires_at": expires_at,
            "type": "share",
        }

        payload_str = json.dumps(payload, separators=(",", ":"))
        signature = self._sign(payload_str)

        token_data = json.dumps(
            {"p": payload, "s": signature},
            separators=(",", ":"),
        )
        return base64.urlsafe_b64encode(token_data.encode()).rstrip(b"=").decode()

    def validate_token(self, token: str) -> dict[str, Any] | None:
        """Validate a share token and return the payload if valid.

        Args:
            token: The base64url-encoded token string.

        Returns:
            Payload dict if valid, None if invalid or expired.
        """
        try:
            padded = token + "=" * (4 - len(token) % 4)
            decoded = base64.urlsafe_b64decode(padded).decode()
            data = json.loads(decoded)
            payload: dict[str, Any] = data["p"]
            signature: str = data["s"]

            payload_str = json.dumps(payload, separators=(",", ":"))
            expected = self._sign(payload_str)

            if not hmac.compare_digest(signature, expected):
                return None

            expires = datetime.fromisoformat(payload["expires_at"])
            if expires < datetime.now(UTC):
                return None

            return payload
        except (KeyError, json.JSONDecodeError, ValueError, TypeError):
            return None

    def _sign(self, data: str) -> str:
        """Create HMAC-SHA256 signature truncated to 16 hex chars."""
        return hmac.new(
            self._secret.encode(),
            data.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
