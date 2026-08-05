"""PositionSizer — Professional-mode position sizing with conviction-based Kelly.

Calculates single-position size using a modified Kelly Criterion adjusted
by trader conviction level, with hard caps for position and sector exposure.

Formula (per CONTEXT.md):
    conviction_multiplier = {"high": 1.0, "medium": 0.67, "low": 0.33}
    risk_per_share = abs(entry - stop_loss)
    kelly_base = account_equity × risk_per_trade_pct × conviction_multiplier / risk_per_share
    position_size = min(kelly_base, max_position_cap, max_sector_cap)
"""

from __future__ import annotations

import math

from backend.app.core.logging import get_logger
from backend.app.infrastructure.professional.models import (
    PositionSizeRequest,
    PositionSizeResponse,
)

log = get_logger("conflu.professional.position_sizer")

# Conviction → multiplier mapping (from CONTEXT.md)
_CONVICTION_MULTIPLIERS: dict[str, float] = {
    "high": 1.0,
    "medium": 0.67,
    "low": 0.33,
}


class PositionSizer:
    """Single-position size calculator using conviction-adjusted Kelly.

    Designed for Professional Mode — takes a single PositionSizeRequest
    and returns a complete PositionSizeResponse with capped size, shares,
    risk metrics, and the limiting constraint.
    """

    def calculate(self, request: PositionSizeRequest) -> PositionSizeResponse:
        """Compute optimal position size with conviction and capping.

        Args:
            request: Position sizing inputs including entry, stop, conviction,
                     equity, and exposure limits.

        Returns:
            PositionSizeResponse with final dollar size, integer shares,
            risk dollar amount, risk percentage, conviction multiplier,
            and the name of the constraint that capped the position.

        Raises:
            ValueError:
                - If `entry <= stop_loss` (stop must be below entry for long).
                - If `account_equity <= 0`.
        """
        # ── Validate inputs ──────────────────────────────────────────────
        if request.entry == request.stop_loss:
            raise ValueError(
                f"Entry ({request.entry}) and stop_loss ({request.stop_loss}) "
                f"must be different to compute risk per share."
            )

        if request.account_equity <= 0:
            raise ValueError(
                f"Account equity must be positive, got {request.account_equity}."
            )

        # ── Conviction multiplier ────────────────────────────────────────
        conviction_mult = _CONVICTION_MULTIPLIERS.get(
            request.conviction, _CONVICTION_MULTIPLIERS["medium"]
        )

        # ── Position sizing (per CONTEXT.md formula) ─────────────────────
        risk_per_share = abs(request.entry - request.stop_loss)

        # Risk dollars = equity × risk_pct × conviction_mult
        risk_dollars = (
            request.account_equity
            * request.risk_per_trade_pct
            * conviction_mult
        )

        # Kelly shares = risk_dollars / risk_per_share
        kelly_shares = risk_dollars / risk_per_share

        # Kelly dollar amount = kelly_shares × entry
        kelly_dollars = kelly_shares * request.entry

        position_cap = request.max_position_pct * request.account_equity
        sector_cap = request.max_sector_pct * request.account_equity

        # ── Determine final size and limiting constraint ─────────────────
        position_size = min(kelly_dollars, position_cap, sector_cap)

        if position_cap <= kelly_dollars and position_cap <= sector_cap:
            capped_by = "position"
        elif sector_cap <= kelly_dollars and sector_cap <= position_cap:
            capped_by = "sector"
        else:
            capped_by = "kelly"

        # ── Compute derived values ───────────────────────────────────────
        shares = math.floor(position_size / request.entry)
        actual_size = shares * request.entry
        risk_amount = shares * risk_per_share
        risk_pct = risk_amount / request.account_equity

        return PositionSizeResponse(
            position_size=actual_size,
            shares=shares,
            risk_amount=risk_amount,
            risk_pct=risk_pct,
            conviction_multiplier=conviction_mult,
            capped_by=capped_by,
        )
