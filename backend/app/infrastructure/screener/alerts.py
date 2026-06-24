"""Alert Engine — evaluates active alerts and dispatches notifications.

Runs as a background asyncio task. On each evaluation cycle:
1. Load all active alerts (is_active = TRUE) from DuckDB
2. For each alert, evaluate conditions against current data
3. If triggered and not in cooldown:
   a. Update last_triggered_at, increment trigger_count
   b. Insert into alert_history
   c. Broadcast via WebSocket manager
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.infrastructure.screener.cache import IndicatorCache
from backend.app.infrastructure.screener.engine import ScreenEngine

log = get_logger("conflu.screener.alerts")


class EvaluationResult:
    """Result of evaluating a single alert condition."""

    def __init__(
        self,
        triggered: bool,
        symbol: str | None = None,
        condition_matched: str | None = None,
        value_at_trigger: float | None = None,
        threshold: float | None = None,
        timeframe: str | None = None,
    ) -> None:
        self.triggered = triggered
        self.symbol = symbol
        self.condition_matched = condition_matched
        self.value_at_trigger = value_at_trigger
        self.threshold = threshold
        self.timeframe = timeframe


class TriggeredAlert:
    """Record of a triggered alert for internal dispatch."""

    def __init__(
        self,
        alert_id: str,
        user_id: str,
        alert_name: str,
        alert_type: str,
        symbol: str | None,
        timeframe: str | None,
        condition_matched: str | None,
        value_at_trigger: float | None,
        threshold: float | None,
        triggered_at: datetime,
        severity: str = "info",
        message: str = "",
    ) -> None:
        self.alert_id = alert_id
        self.user_id = user_id
        self.alert_name = alert_name
        self.alert_type = alert_type
        self.symbol = symbol
        self.timeframe = timeframe
        self.condition_matched = condition_matched
        self.value_at_trigger = value_at_trigger
        self.threshold = threshold
        self.triggered_at = triggered_at
        self.severity = severity
        self.message = message


class AlertEngine:
    """Evaluates active alerts and dispatches notifications.

    Runs as a background asyncio task. On each cycle:
    1. Load all active alerts
    2. Evaluate conditions against current data
    3. If triggered and not in cooldown: record, dispatch, broadcast
    """

    def __init__(self) -> None:
        self._cache = IndicatorCache()
        self._engine = ScreenEngine()
        self._log = get_logger("conflu.screener.alerts")
        self._background_task: asyncio.Task[Any] | None = None
        # Dedup tracker: {(alert_id, symbol, condition_hash) -> last_trigger_at}
        self._dedup_cache: dict[tuple[str, str | None, str], datetime] = {}
        self._condition_hash_cache: dict[str, str] = {}  # alert_id -> latest condition hash

    @property
    def is_running(self) -> bool:
        return self._background_task is not None and not self._background_task.done()

    def start_background_loop(self) -> None:
        """Start the periodic alert evaluation loop."""
        if self.is_running:
            self._log.warning("alert_loop_already_running")
            return

        interval = settings.alert.evaluation_interval_s
        self._background_task = asyncio.create_task(
            self._evaluation_loop(interval),
        )
        self._log.info("alert_background_loop_started", interval_s=interval)

    async def stop_background_loop(self) -> None:
        """Stop the periodic alert evaluation loop."""
        if self._background_task and not self._background_task.done():
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
        self._background_task = None
        self._log.info("alert_background_loop_stopped")

    async def _evaluation_loop(self, interval_s: int) -> None:
        """Periodic evaluation loop."""
        while True:
            try:
                await self.evaluate_all()
            except asyncio.CancelledError:
                break
            except Exception:
                self._log.exception("alert_evaluation_cycle_error")

            await asyncio.sleep(interval_s)

    async def evaluate_all(self) -> list[TriggeredAlert]:
        """Evaluate all active alerts against latest data.

        Returns:
            List of triggered alerts from this cycle.
        """
        alerts = self._load_active_alerts()
        if not alerts:
            return []

        triggered: list[TriggeredAlert] = []
        condition_hashes: dict[str, str] = {}

        for alert in alerts:
            try:
                condition_hash = self._compute_condition_hash(alert["condition_json"])
                condition_hashes[alert["id"]] = condition_hash

                if self._in_cooldown(alert):
                    continue

                result = await self._evaluate_single(alert)
                if result and result.triggered:
                    dedup_key = (alert["id"], result.symbol, condition_hash)
                    if self._is_deduplicated(dedup_key, alert["cooldown_seconds"]):
                        continue

                    triggered_alert = TriggeredAlert(
                        alert_id=alert["id"],
                        user_id=alert.get("user_id", "default"),
                        alert_name=alert["name"],
                        alert_type=alert["alert_type"],
                        symbol=result.symbol,
                        timeframe=result.timeframe,
                        condition_matched=result.condition_matched,
                        value_at_trigger=result.value_at_trigger,
                        threshold=result.threshold,
                        triggered_at=datetime.now(UTC),
                        message=self._build_message(alert, result),
                    )
                    self._record_trigger(alert, triggered_alert, condition_hash)
                    await self._dispatch(triggered_alert)
                    triggered.append(triggered_alert)

            except Exception:
                self._log.exception(
                    "alert_evaluation_error",
                    alert_id=alert.get("id", "unknown"),
                    alert_name=alert.get("name", "unknown"),
                )

        # Clean stale dedup entries
        self._clean_dedup_cache()

        return triggered

    def _load_active_alerts(self) -> list[dict[str, Any]]:
        """Load all active alerts from DuckDB."""
        with get_db(read_only=True) as con:
            rows = con.sql(
                """
                SELECT id, user_id, name, description, alert_type,
                       condition_json, symbols, timeframes, is_active,
                       cooldown_seconds, last_triggered_at, trigger_count
                FROM alerts
                WHERE is_active = TRUE
                ORDER BY created_at DESC
                """,
            ).fetchdf()

        if rows.empty:
            return []

        result: list[dict[str, Any]] = []
        for _, row in rows.iterrows():
            alert_dict = row.to_dict()
            # Parse JSON string columns
            for col in ["symbols", "timeframes"]:
                if isinstance(alert_dict.get(col), str):
                    try:
                        alert_dict[col] = json.loads(alert_dict[col])
                    except (json.JSONDecodeError, TypeError):
                        pass
            result.append(alert_dict)

        return result

    async def _evaluate_single(self, alert: dict[str, Any]) -> EvaluationResult | None:
        """Evaluate a single alert against current data.

        Dispatches to the appropriate strategy based on alert_type.
        """
        alert_type = alert["alert_type"]
        condition = json.loads(alert["condition_json"])

        if alert_type == "price_threshold":
            return await self._eval_price_threshold(condition)
        elif alert_type == "indicator_cross":
            return await self._eval_indicator_cross(condition)
        elif alert_type == "signal_trigger":
            return await self._eval_signal_trigger(condition)
        elif alert_type == "volume_spike":
            return await self._eval_volume_spike(condition)
        elif alert_type == "trend_break":
            return await self._eval_trend_break(condition)
        elif alert_type == "compound":
            return await self._eval_compound(condition)
        else:
            self._log.warning("unknown_alert_type", alert_type=alert_type)
            return None

    async def _eval_price_threshold(self, condition: dict[str, Any]) -> EvaluationResult:
        """Evaluate a price threshold condition."""
        symbol = condition.get("symbol", "")
        field = condition.get("field", "close")
        operator = condition.get("operator", "gt")
        value = float(condition.get("value", 0))
        timeframe = condition.get("timeframe", "1D")

        with get_db(read_only=True) as con:
            df = con.sql(
                f"""
                SELECT symbol, timestamp, {field} as price
                FROM ohlcv
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC LIMIT 1
                """,
                params=[symbol, timeframe],
            ).fetchdf()

        if df.empty:
            return EvaluationResult(triggered=False)

        current_price = float(df.iloc[0]["price"])
        triggered = self._compare(current_price, operator, value)

        return EvaluationResult(
            triggered=triggered,
            symbol=symbol,
            condition_matched=f"{field} {self._operator_label(operator)} {value}",
            value_at_trigger=current_price,
            threshold=value,
            timeframe=timeframe,
        )

    async def _eval_indicator_cross(self, condition: dict[str, Any]) -> EvaluationResult:
        """Evaluate an indicator cross condition."""
        symbol = condition.get("symbol", "")
        indicator = condition.get("indicator", "")
        operator = condition.get("operator", "gt")
        value = float(condition.get("value", 0))
        timeframe = condition.get("timeframe", "1D")

        df = await self._cache.get_latest(
            indicator_name=indicator,
            timeframe=timeframe,
            symbols=[symbol],
        )

        if df is None or df.empty:
            return EvaluationResult(triggered=False)

        current_value = float(df.iloc[0]["value"])
        triggered = self._compare(current_value, operator, value)

        return EvaluationResult(
            triggered=triggered,
            symbol=symbol,
            condition_matched=f"{indicator} {self._operator_label(operator)} {value}",
            value_at_trigger=current_value,
            threshold=value,
            timeframe=timeframe,
        )

    async def _eval_signal_trigger(self, condition: dict[str, Any]) -> EvaluationResult:
        """Evaluate a signal trigger (screener match) condition."""
        screen_config_name = condition.get("screen", "")
        min_matches = int(condition.get("min_matches", 1))

        try:
            result = await self._engine.screen(config=screen_config_name)
        except Exception:
            self._log.warning("signal_trigger_screen_failed", screen=screen_config_name)
            return EvaluationResult(triggered=False)

        match_count = result.symbols_matched
        triggered = match_count >= min_matches

        return EvaluationResult(
            triggered=triggered,
            condition_matched=f"screener match >= {min_matches}",
            value_at_trigger=float(match_count),
            threshold=float(min_matches),
        )

    async def _eval_volume_spike(self, condition: dict[str, Any]) -> EvaluationResult:
        """Evaluate a volume spike condition."""
        symbol = condition.get("symbol", "")
        multiplier = float(condition.get("multiplier", 2.0))
        window = int(condition.get("window", 20))
        timeframe = condition.get("timeframe", "1D")

        with get_db(read_only=True) as con:
            df = con.sql(
                """
                SELECT symbol, timestamp, volume
                FROM ohlcv
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC LIMIT ?
                """,
                params=[symbol, timeframe, window + 1],
            ).fetchdf()

        if len(df) < 2:
            return EvaluationResult(triggered=False)

        latest_volume = float(df.iloc[0]["volume"])
        avg_volume = float(df.iloc[1:]["volume"].mean())

        if avg_volume <= 0:
            return EvaluationResult(triggered=False)

        ratio = latest_volume / avg_volume
        triggered = ratio >= multiplier

        return EvaluationResult(
            triggered=triggered,
            symbol=symbol,
            condition_matched=f"volume {ratio:.1f}x above {window}-bar avg",
            value_at_trigger=float(latest_volume),
            threshold=float(avg_volume * multiplier),
            timeframe=timeframe,
        )

    async def _eval_trend_break(self, condition: dict[str, Any]) -> EvaluationResult:
        """Evaluate a trend break condition (simplified: cross of two values).

        Instead of true trendline detection, this checks for a crossover
        event: e.g., close crossing below EMA(200).
        """
        symbol = condition.get("symbol", "")
        primary = condition.get("primary", "close")
        secondary = condition.get("secondary", "ema_200")
        direction = condition.get("direction", "cross_below")
        timeframe = condition.get("timeframe", "1D")

        with get_db(read_only=True) as con:
            df = con.sql(
                f"""
                SELECT symbol, timestamp, {primary} as primary_val
                FROM ohlcv
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC LIMIT 2
                """,
                params=[symbol, timeframe],
            ).fetchdf()

        if len(df) < 2:
            return EvaluationResult(triggered=False)

        indicator_df = await self._cache.get_latest(
            indicator_name=secondary,
            timeframe=timeframe,
            symbols=[symbol],
        )
        if indicator_df is None or indicator_df.empty:
            return EvaluationResult(triggered=False)

        secondary_val = float(indicator_df.iloc[0]["value"])
        current_primary = float(df.iloc[0]["primary_val"])
        prev_primary = float(df.iloc[1]["primary_val"])

        if direction == "cross_below":
            triggered = prev_primary >= secondary_val and current_primary < secondary_val
        elif direction == "cross_above":
            triggered = prev_primary <= secondary_val and current_primary > secondary_val
        else:
            triggered = False

        return EvaluationResult(
            triggered=triggered,
            symbol=symbol,
            condition_matched=f"{primary} {direction} {secondary} ({secondary_val:.2f})",
            value_at_trigger=current_primary,
            threshold=secondary_val,
            timeframe=timeframe,
        )

    async def _eval_compound(self, condition: dict[str, Any]) -> EvaluationResult:
        """Evaluate a compound condition (AND/OR of sub-conditions)."""
        operator = condition.get("operator", "AND")
        conditions = condition.get("conditions", [])

        if not conditions:
            return EvaluationResult(triggered=False)

        results: list[EvaluationResult] = []
        for sub_condition in conditions:
            sub_type = sub_condition.get("type", "")
            # Create a simplified alert dict for recursive evaluation
            sub_alert = {
                "alert_type": sub_type,
                "condition_json": json.dumps(sub_condition),
            }
            result = await self._evaluate_single(sub_alert)
            if result is not None:
                results.append(result)

        if not results:
            return EvaluationResult(triggered=False)

        if operator == "AND":
            triggered = all(r.triggered for r in results)
        else:  # OR
            triggered = any(r.triggered for r in results)

        # Use the first triggered result's details
        triggered_result = next((r for r in results if r.triggered), results[0])

        return EvaluationResult(
            triggered=triggered,
            symbol=triggered_result.symbol,
            condition_matched=f"compound({operator}): {triggered_result.condition_matched}",
            value_at_trigger=triggered_result.value_at_trigger,
            threshold=triggered_result.threshold,
            timeframe=triggered_result.timeframe,
        )

    def _compare(self, current: float, operator: str, threshold: float) -> bool:
        """Compare a value against a threshold using the specified operator."""
        if operator in ("gt", ">"):
            return current > threshold
        elif operator in ("gte", ">="):
            return current >= threshold
        elif operator in ("lt", "<"):
            return current < threshold
        elif operator in ("lte", "<="):
            return current <= threshold
        elif operator in ("eq", "==", "="):
            return abs(current - threshold) < 1e-10
        elif operator in ("neq", "!="):
            return abs(current - threshold) >= 1e-10
        return False

    def _operator_label(self, operator: str) -> str:
        """Get a human-readable label for an operator."""
        labels = {
            "gt": ">",
            ">": ">",
            "gte": ">=",
            ">=": ">=",
            "lt": "<",
            "<": "<",
            "lte": "<=",
            "<=": "<=",
            "eq": "==",
            "==": "==",
            "=": "==",
            "neq": "!=",
            "!=": "!=",
        }
        return labels.get(operator, operator)

    def _in_cooldown(self, alert: dict[str, Any]) -> bool:
        """Check if alert is in cooldown period since last trigger."""
        last_triggered = alert.get("last_triggered_at")
        if last_triggered is None:
            return False
        cooldown = alert.get("cooldown_seconds", 300)

        if isinstance(last_triggered, str):
            try:
                last_triggered = datetime.fromisoformat(last_triggered)
            except (ValueError, TypeError):
                return False

        elapsed = (datetime.now(UTC) - last_triggered).total_seconds()
        return elapsed < cooldown

    def _is_deduplicated(
        self,
        dedup_key: tuple[str, str | None, str],
        cooldown_seconds: int,
    ) -> bool:
        """Check if this trigger is within the dedup window."""
        last_trigger = self._dedup_cache.get(dedup_key)
        if last_trigger is None:
            return False
        elapsed = (datetime.now(UTC) - last_trigger).total_seconds()
        return elapsed < cooldown_seconds

    def _compute_condition_hash(self, condition_json: str) -> str:
        """Compute a hash of the condition for deduplication."""
        return hashlib.md5(condition_json.encode()).hexdigest()[:12]

    def _build_message(self, alert: dict[str, Any], result: EvaluationResult) -> str:
        """Build a human-readable alert message."""
        symbol_part = f" ({result.symbol})" if result.symbol else ""
        value_part = f" at {result.value_at_trigger:.2f}" if result.value_at_trigger is not None else ""
        return f"{alert['name']}: {result.condition_matched}{value_part}{symbol_part}"

    def _record_trigger(
        self,
        alert: dict[str, Any],
        triggered: TriggeredAlert,
        condition_hash: str,
    ) -> None:
        """Record a triggered alert in DuckDB and dedup cache."""
        # Update dedup cache
        dedup_key = (alert["id"], triggered.symbol, condition_hash)
        self._dedup_cache[dedup_key] = datetime.now(UTC)

        import asyncio

        loop = asyncio.get_running_loop()

        def _write() -> None:
            with get_db() as con:
                # 1. Update alert: last_triggered_at, trigger_count
                con.sql(
                    """
                    UPDATE alerts
                    SET last_triggered_at = CURRENT_TIMESTAMP,
                        trigger_count = trigger_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    params=[alert["id"]],
                )

                # 2. Insert into alert_history
                con.sql(
                    """
                    INSERT INTO alert_history (id, alert_id, symbol, triggered_at,
                                               condition_matched, value_at_trigger, threshold)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
                    """,
                    params=[
                        str(uuid.uuid4()),
                        alert["id"],
                        triggered.symbol,
                        triggered.condition_matched,
                        triggered.value_at_trigger,
                        triggered.threshold,
                    ],
                )

        loop.run_in_executor(None, _write)

    async def _dispatch(self, triggered: TriggeredAlert) -> None:
        """Push alert notification via WebSocket."""
        from backend.app.api.ws.manager import ws_manager

        message: dict[str, Any] = {
            "type": "alert_triggered",
            "channel": f"alert:user:{triggered.user_id}",
            "timestamp": triggered.triggered_at.isoformat(),
            "data": {
                "alert_id": triggered.alert_id,
                "alert_name": triggered.alert_name,
                "alert_type": triggered.alert_type,
                "symbol": triggered.symbol,
                "timeframe": triggered.timeframe,
                "triggered_at": triggered.triggered_at.isoformat(),
                "condition_matched": triggered.condition_matched,
                "value_at_trigger": triggered.value_at_trigger,
                "threshold": triggered.threshold,
                "severity": triggered.severity,
                "message": triggered.message,
                "deep_link": "/screener",
            },
        }

        channel = f"alert:user:{triggered.user_id}"
        await ws_manager.broadcast(channel, message)
        self._log.info(
            "alert_dispatched",
            alert_id=triggered.alert_id,
            alert_name=triggered.alert_name,
            channel=channel,
        )

    def _clean_dedup_cache(self, max_age_minutes: int = 30) -> None:
        """Remove stale entries from the dedup cache."""
        now = datetime.now(UTC)
        stale_keys = [key for key, ts in self._dedup_cache.items() if (now - ts).total_seconds() > max_age_minutes * 60]
        for key in stale_keys:
            del self._dedup_cache[key]


# Singleton instance for use across the application
alert_engine = AlertEngine()
