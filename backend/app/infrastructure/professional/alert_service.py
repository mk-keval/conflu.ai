"""AlertService — In-app and email notifications for Professional Mode.

Manages alert preferences, queues in-app alerts (stop/target hits, regime
changes, earnings), and simulates morning brief email delivery.

All "send" methods log the event rather than dispatching real email/push —
the logging infrastructure captures structured JSON for downstream consumers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.app.core.logging import get_logger
from backend.app.infrastructure.professional.models import (
    AlertPreferences,
    MorningBriefResponse,
)

# ── Alert type constants ──────────────────────────────────────────────

STOP_HIT = "stop_hit"
TARGET_HIT = "target_hit"
EARNINGS = "earnings"
REGIME_CHANGE = "regime_change"
MORNING_BRIEF = "morning_brief"

_ALERT_TYPES: frozenset[str] = frozenset({
    STOP_HIT,
    TARGET_HIT,
    EARNINGS,
    REGIME_CHANGE,
    MORNING_BRIEF,
})

# ── Module-level logger ───────────────────────────────────────────────
_log = get_logger("conflu.professional.alert_service")


def _now_iso() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _make_alert(
    alert_type: str,
    title: str,
    message: str,
) -> dict[str, Any]:
    """Build a standardised in-app alert dict.

    Args:
        alert_type: One of the `_ALERT_TYPES` constants.
        title: Short headline for the alert.
        message: Human-readable body text.

    Returns:
        A dict matching the in-app alert schema.
    """
    return {
        "id": str(uuid4()),
        "type": alert_type,
        "title": title,
        "message": message,
        "timestamp": _now_iso(),
        "read": False,
    }


class AlertService:
    """Professional-mode notification hub.

    Provides a unified interface for producing in-app alerts and simulated
    email notifications.  Alert preferences are stored in-memory per email;
    reload on application restart is expected (non-durable by design).

    Typical usage::

        service = AlertService()
        service.send_stop_hit_alert("AAPL", 175.0, 168.0)
        alerts = service.get_recent_alerts(limit=5)
    """

    def __init__(self) -> None:
        # email -> AlertPreferences  (in-memory; start fresh each restart)
        self._preferences: dict[str, AlertPreferences] = {}
        # Ordered list of in-app alert dicts, most recent appended last
        self._alerts: list[dict[str, Any]] = []
        self.log = get_logger("conflu.professional.alert_service")

    # ── Email (simulated) ──────────────────────────────────────────────

    def send_morning_brief_email(
        self, email: str, brief: MorningBriefResponse,
    ) -> bool:
        """Format and "send" a morning brief email (logging-only).

        Args:
            email: Recipient email address.
            brief: The full morning brief response to summarise.

        Returns:
            `True` — always succeeds (simulated).
        """
        try:
            header = (
                f"Morning Brief — {brief.date}\n"
                f"Regime: {brief.regime} — {brief.regime_description}\n"
                f"Sectors: {len(brief.sectors)} tracked  |  "
                f"Screen sections: {len(brief.screen_sections)}\n"
                f"Market internals: VIX={brief.market_internals.vix}, "
                f"SP500 futures={brief.market_internals.sp500_futures}\n"
            )

            # Build a quick summary per screen section
            screens_detail = ""
            for section in brief.screen_sections:
                top_tickers = ", ".join(
                    t.symbol for t in section.tickers[:3]
                )
                screens_detail += (
                    f"  \u2022 {section.screen_label} "
                    f"(regime match: {section.regime_match_score:.1%}): "
                    f"{len(section.tickers)} tickers  |  "
                    f"Top: [{top_tickers}]\n"
                )

            body = header + screens_detail
            self.log.info(
                "morning_brief_email_simulated",
                recipient=email,
                date=brief.date,
                regime=brief.regime,
                ticker_count=sum(
                    len(s.tickers) for s in brief.screen_sections
                ),
                body_preview=body[:200],
            )

            # Also create an in-app alert for the brief
            self._alerts.append(_make_alert(
                alert_type=MORNING_BRIEF,
                title=f"Morning Brief — {brief.date}",
                message=(
                    f"Regime: {brief.regime}.  "
                    f"{len(brief.sectors)} sectors, "
                    f"{sum(len(s.tickers) for s in brief.screen_sections)} tickers "
                    f"across {len(brief.screen_sections)} screens."
                ),
            ))
            return True

        except Exception:
            self.log.exception(
                "Failed to send morning brief email",
                recipient=email,
                date=brief.date if hasattr(brief, "date") else "unknown",
            )
            return False

    # ── In-app alerts ──────────────────────────────────────────────────

    def send_stop_hit_alert(self, symbol: str, entry: float, stop: float) -> bool:
        """Create an in-app alert when a stop-loss level is hit.

        Args:
            symbol: Ticker symbol (e.g. `"AAPL"`).
            entry: Entry price.
            stop: Stop-loss price that was triggered.

        Returns:
            `True` on success, `False` on unexpected error.
        """
        try:
            loss_pct = ((stop - entry) / entry) * 100 if entry != 0 else 0.0
            self._alerts.append(_make_alert(
                alert_type=STOP_HIT,
                title=f"Stop Hit — {symbol}",
                message=(
                    f"{symbol} stopped out at ${stop:.2f} "
                    f"(entry ${entry:.2f}, loss {loss_pct:+.2f}%)."
                ),
            ))
            self.log.info(
                "stop_hit_alert_created",
                symbol=symbol,
                entry=entry,
                stop=stop,
                loss_pct=round(loss_pct, 2),
            )
            return True

        except Exception:
            self.log.exception(
                "Failed to create stop-hit alert",
                symbol=symbol,
            )
            return False

    def send_target_hit_alert(self, symbol: str, target_level: int) -> bool:
        """Create an in-app alert when a price target is reached.

        Args:
            symbol: Ticker symbol (e.g. `"AAPL"`).
            target_level: The target number that was hit (1, 2, 3, \u2026).

        Returns:
            `True` on success, `False` on unexpected error.
        """
        try:
            self._alerts.append(_make_alert(
                alert_type=TARGET_HIT,
                title=f"Target {target_level} Hit — {symbol}",
                message=(
                    f"{symbol} reached target {target_level}.  "
                    f"Consider taking partial profits."
                ),
            ))
            self.log.info(
                "target_hit_alert_created",
                symbol=symbol,
                target_level=target_level,
            )
            return True

        except Exception:
            self.log.exception(
                "Failed to create target-hit alert",
                symbol=symbol,
                target_level=target_level,
            )
            return False

    def send_earnings_alert(self, symbols: list[str]) -> bool:
        """Create a batch in-app alert for upcoming earnings reports.

        Args:
            symbols: List of ticker symbols reporting earnings.

        Returns:
            `True` on success, `False` on unexpected error.
        """
        try:
            count = len(symbols)
            if count == 0:
                self.log.warning("send_earnings_alert called with empty symbol list")
                return True

            symbol_list = ", ".join(symbols)
            self._alerts.append(_make_alert(
                alert_type=EARNINGS,
                title=f"Earnings Today — {count} Ticker{'s' if count != 1 else ''}",
                message=f"Earnings reports due: {symbol_list}.",
            ))
            self.log.info(
                "earnings_alert_created",
                symbol_count=count,
                symbols=symbols,
            )
            return True

        except Exception:
            self.log.exception(
                "Failed to create earnings alert",
                symbol_count=len(symbols),
            )
            return False

    def send_regime_change_alert(
        self, old_regime: str, new_regime: str,
    ) -> bool:
        """Create an in-app alert when the detected market regime changes.

        Args:
            old_regime: The previous regime label.
            new_regime: The newly detected regime label.

        Returns:
            `True` on success, `False` on unexpected error.
        """
        try:
            self._alerts.append(_make_alert(
                alert_type=REGIME_CHANGE,
                title=f"Regime Change: {old_regime} \u2192 {new_regime}",
                message=(
                    f"Market regime has shifted from {old_regime} "
                    f"to {new_regime}.  Review your watchlist and "
                    f"adjust strategy accordingly."
                ),
            ))
            self.log.info(
                "regime_change_alert_created",
                old_regime=old_regime,
                new_regime=new_regime,
            )
            return True

        except Exception:
            self.log.exception(
                "Failed to create regime-change alert",
                old_regime=old_regime,
                new_regime=new_regime,
            )
            return False

    # ── Preferences ────────────────────────────────────────────────────

    def get_preferences(self, email: str) -> AlertPreferences:
        """Return stored alert preferences for *email*, or defaults.

        Args:
            email: The user's email address.

        Returns:
            An `AlertPreferences` instance — either the previously stored
            value or a default (all flags `True`).
        """
        return self._preferences.get(email, AlertPreferences())

    def update_preferences(
        self, email: str, prefs: AlertPreferences,
    ) -> None:
        """Store or update alert preferences for a given email.

        Args:
            email: The user's email address.
            prefs: The new preferences to persist.

        Raises:
            ValueError: If *email* is empty or `None` after stripping.
        """
        cleaned = email.strip()
        if not cleaned:
            raise ValueError("Email must be a non-empty string.")

        self._preferences[cleaned] = prefs
        self.log.info(
            "alert_preferences_updated",
            email=cleaned,
            preferences=prefs.model_dump(),
        )

    # ── Alert retrieval ────────────────────────────────────────────────

    def get_recent_alerts(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the most recent in-app alerts.

        Results are ordered newest-first.

        Args:
            limit: Maximum number of alerts to return (default 20).

        Returns:
            A list of alert dicts, most recent first.  If fewer alerts
            exist than *limit*, all available are returned.

        Raises:
            ValueError: If *limit* is negative.
        """
        if limit < 0:
            raise ValueError(f"Limit must be non-negative, got {limit}.")

        # _alerts is appended most-recent-last; reverse for newest-first
        return list(reversed(self._alerts[-limit:])) if limit > 0 else []


