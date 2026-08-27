"""Education Service â€” plain-English explanations of financial metrics.

Single source of truth is ``frontend/src/content/education.json`` (loaded at
startup; Docker mounts it read-only at /app/education/education.json).
This service renders value-aware explanations via the shared bands DSL
(``education_bands.py`` â€” parity-tested with the frontend evaluator).

Legacy behavior preserved: metric-name normalization, EducationResponse
schema, and LLM-enhancement hook point are unchanged.
"""

from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.app.core.logging import get_logger
from backend.app.infrastructure.professional.education_bands import evaluate_bands
from backend.app.infrastructure.professional.models import EducationResponse

logger = get_logger(__name__)

# In-process daily call budget for LLM education enhancement (Phase 5).
_LLM_CALL_STATE: dict[str, Any] = {"day": None, "count": 0}


def _get_professional_settings():
    """Fetch ProfessionalSettings lazily; None if config unavailable."""
    try:
        from backend.app.core.config import settings as app_settings

        return app_settings.professional
    except Exception as exc:  # noqa: BLE001
        logger.info("ProfessionalSettings unavailable for LLM education", error=str(exc)[:120])
        return None

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Content loading â€” education.json single source of truth
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_CANDIDATE_PATHS = [
    os.environ.get("EDUCATION_CONTENT_PATH", ""),
    "/app/education/education.json",  # docker mount
    str(Path(__file__).resolve().parents[4] / "frontend" / "src" / "content" / "education.json"),
]


@lru_cache(maxsize=1)
def _load_content() -> dict[str, Any]:
    """Load and cache education.json. Raises RuntimeError if not found."""
    for candidate in _CANDIDATE_PATHS:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            logger.info(
                "education content loaded",
                path=str(path),
                metrics=len(data.get("metrics", {})),
                version=data.get("meta", {}).get("version"),
            )
            return data
    raise RuntimeError(
        "education.json not found in any candidate path; set EDUCATION_CONTENT_PATH"
    )


def _lesson_for(canonical: str) -> dict[str, Any] | None:
    """Resolve a canonical metric key to its lesson across all sections."""
    data = _load_content()
    sections = ("metrics", "backtestMetrics")
    for section in sections:
        lesson = data.get(section, {}).get(canonical)
        if lesson:
            return lesson
    # tradePlan/concepts are also explainable
    for section in ("tradePlan", "concepts"):
        lesson = data.get(section, {}).get(canonical)
        if lesson:
            return {**lesson, "category": section}
    return None


# Legacy alias map retained for API compatibility (callers may pass display
# names like "P/E Ratio"); content keys live in education.json.
_METRIC_ALIASES: dict[str, str] = {
    "pe_ratio": "pe_ratio", "pe": "pe_ratio", "p/e": "pe_ratio",
    "p/e ratio": "pe_ratio", "price to earnings": "pe_ratio",
    "price-to-earnings": "pe_ratio", "price to earnings ratio": "pe_ratio",
    "price-to-earnings ratio": "pe_ratio",
    "rsi": "rsi", "relative strength index": "rsi",
    "atr_pct": "atr_pct", "atr": "atr_pct", "average true range": "atr_pct",
    "average true range %": "atr_pct", "atr%": "atr_pct",
    "beta": "beta", "Î²": "beta",
    "adx": "adx", "average directional index": "adx",
    "macd": "macd_status", "macd_status": "macd_status",
    "moving average convergence divergence": "macd_status",
    "volume_ratio": "volume_ratio", "volume": "volume_ratio",
    "volume ratio": "volume_ratio", "relative volume": "volume_ratio",
    "rel volume": "volume_ratio",
    "ma_alignment": "ma_alignment", "ma": "ma_alignment",
    "moving average alignment": "ma_alignment", "moving average": "ma_alignment",
    "bb_position": "bb_position", "bollinger bands": "bb_position",
    "bb": "bb_position", "bollinger": "bb_position",
    "bollinger band position": "bb_position",
    "market_cap": "market_cap", "market cap": "market_cap",
    "market capitalization": "market_cap",
    "eps": "eps", "earnings per share": "eps",
    "profit_margin": "profit_margin", "profit margin": "profit_margin",
    "net margin": "profit_margin", "net profit margin": "profit_margin",
    "debt_to_equity": "debt_to_equity", "debt to equity": "debt_to_equity",
    "d/e": "debt_to_equity", "debt/equity": "debt_to_equity",
    "debt equity ratio": "debt_to_equity",
    "revenue_growth": "revenue_growth_yoy", "revenue growth": "revenue_growth_yoy",
    "revenue": "revenue_growth_yoy", "revenue growth yoy": "revenue_growth_yoy",
    "fcf_yield": "fcf_yield", "fcf": "fcf_yield",
    "free cash flow yield": "fcf_yield", "free cash flow": "fcf_yield",
    "analyst_consensus": "analyst_consensus", "analyst consensus": "analyst_consensus",
    "consensus": "analyst_consensus", "analyst rating": "analyst_consensus",
    "insider_activity": "insider_status", "insider_activity": "insider_status",
    "insider activity": "insider_status", "insider trading": "insider_status",
    "insider": "insider_status", "insider_status": "insider_status",
    "short_interest": "short_interest_pct", "short interest": "short_interest_pct",
    "short": "short_interest_pct", "short float": "short_interest_pct",
    "% short": "short_interest_pct", "short_interest_pct": "short_interest_pct",
    "institutional_ownership": "institutional_ownership",
    "institutional ownership": "institutional_ownership",
    "inst own": "institutional_ownership", "inst ownership": "institutional_ownership",
    "dividend_yield": "dividend_yield", "dividend yield": "dividend_yield",
    "dividend": "dividend_yield",
    "short_ratio": "short_ratio", "short ratio": "short_ratio",
    "days to cover": "short_ratio", "days_to_cover": "short_ratio",
    "days-to-cover": "short_ratio",
    "earnings_growth_yoy": "earnings_growth_yoy",
    "earnings growth": "earnings_growth_yoy", "earnings growth yoy": "earnings_growth_yoy",
    "peg_ratio": "peg_ratio", "peg": "peg_ratio", "peg ratio": "peg_ratio",
    "price earnings growth": "peg_ratio",
    "price_to_sales": "price_to_sales", "price to sales": "price_to_sales",
    "p/s": "price_to_sales", "p/s ratio": "price_to_sales",
    "price sales ratio": "price_to_sales",
    "current_ratio": "current_ratio", "current ratio": "current_ratio",
    "avg_volume_20d": "avg_volume_20d", "average volume 20d": "avg_volume_20d",
    "avg volume 20 day": "avg_volume_20d", "avg volume": "avg_volume_20d",
    "sma_50_200": "sma_50_200", "sma 50 200": "sma_50_200",
    "50 200 sma": "sma_50_200", "golden cross": "sma_50_200",
    "death cross": "sma_50_200",
    "consecutive_gains": "consecutive_gains", "consecutive gains": "consecutive_gains",
    "up days": "consecutive_gains", "consecutive up days": "consecutive_gains",
    "institutional_flow": "institutional_flow", "institutional flow": "institutional_flow",
    "inst flow": "institutional_flow", "institutional buying": "institutional_flow",
    "vix": "vix", "market_regime": "market_regime", "regime": "market_regime",
    "sector_rotation": "sector_rotation",
    "advance_decline_ratio": "advance_decline_ratio", "a/d": "advance_decline_ratio",
    "dollar_index": "dollar_index", "dxy": "dollar_index",
    "sp500_futures": "sp500_futures", "s&p 500": "sp500_futures",
    "nasdaq_futures": "nasdaq_futures", "change_1w": "change_1w",
}

_METRIC_ALIASES: dict[str, str] = {
    # P/E ratio
    "pe_ratio": "pe_ratio",
    "pe": "pe_ratio",
    "p/e": "pe_ratio",
    "p/e ratio": "pe_ratio",
    "price to earnings": "pe_ratio",
    "price-to-earnings": "pe_ratio",
    "price to earnings ratio": "pe_ratio",
    "price-to-earnings ratio": "pe_ratio",
    # RSI
    "rsi": "rsi",
    "relative strength index": "rsi",
    # ATR
    "atr_pct": "atr_pct",
    "atr": "atr_pct",
    "average true range": "atr_pct",
    "average true range %": "atr_pct",
    "atr%": "atr_pct",
    # Beta
    "beta": "beta",
    "Î²": "beta",
    # ADX
    "adx": "adx",
    "average directional index": "adx",
    # MACD
    "macd": "macd",
    "moving average convergence divergence": "macd",
    # Volume
    "volume_ratio": "volume_ratio",
    "volume": "volume_ratio",
    "volume ratio": "volume_ratio",
    "relative volume": "volume_ratio",
    "rel volume": "volume_ratio",
    # Moving average alignment
    "ma_alignment": "ma_alignment",
    "ma": "ma_alignment",
    "moving average alignment": "ma_alignment",
    "moving average": "ma_alignment",
    # Bollinger Bands
    "bb_position": "bb_position",
    "bollinger bands": "bb_position",
    "bb": "bb_position",
    "bollinger": "bb_position",
    "bollinger band position": "bb_position",
    # Market cap
    "market_cap": "market_cap",
    "market cap": "market_cap",
    "market capitalization": "market_cap",
    # EPS
    "eps": "eps",
    "earnings per share": "eps",
    # Profit margin
    "profit_margin": "profit_margin",
    "profit margin": "profit_margin",
    "net margin": "profit_margin",
    "net profit margin": "profit_margin",
    # Debt to equity
    "debt_to_equity": "debt_to_equity",
    "debt to equity": "debt_to_equity",
    "d/e": "debt_to_equity",
    "debt/equity": "debt_to_equity",
    "debt equity ratio": "debt_to_equity",
    # Revenue growth
    "revenue_growth": "revenue_growth",
    "revenue growth": "revenue_growth",
    "revenue": "revenue_growth",
    "revenue growth yoy": "revenue_growth",
    # Free cash flow yield
    "fcf_yield": "fcf_yield",
    "fcf": "fcf_yield",
    "free cash flow yield": "fcf_yield",
    "free cash flow": "fcf_yield",
    # Analyst consensus
    "analyst_consensus": "analyst_consensus",
    "analyst consensus": "analyst_consensus",
    "consensus": "analyst_consensus",
    "analyst rating": "analyst_consensus",
    # Insider activity
    "insider_activity": "insider_activity",
    "insider activity": "insider_activity",
    "insider trading": "insider_activity",
    "insider": "insider_activity",
    # Short interest
    "short_interest": "short_interest",
    "short interest": "short_interest",
    "short": "short_interest",
    "short float": "short_interest",
    "% short": "short_interest",
    # Institutional ownership
    "institutional_ownership": "institutional_ownership",
    "institutional ownership": "institutional_ownership",
    "inst own": "institutional_ownership",
    "inst ownership": "institutional_ownership",
    # Dividend yield
    "dividend_yield": "dividend_yield",
    "dividend yield": "dividend_yield",
    "dividend": "dividend_yield",
    # Short ratio (days to cover)
    "short_ratio": "short_ratio",
    "short ratio": "short_ratio",
    "days to cover": "short_ratio",
    "days_to_cover": "short_ratio",
    # Earnings growth
    "earnings_growth_yoy": "earnings_growth_yoy",
    "earnings growth": "earnings_growth_yoy",
    "earnings growth yoy": "earnings_growth_yoy",
    # PEG ratio
    "peg_ratio": "peg_ratio",
    "peg": "peg_ratio",
    "peg ratio": "peg_ratio",
    "price earnings growth": "peg_ratio",
    # Price to sales
    "price_to_sales": "price_to_sales",
    "price to sales": "price_to_sales",
    "p/s": "price_to_sales",
    "p/s ratio": "price_to_sales",
    "price sales ratio": "price_to_sales",
    # Current ratio
    "current_ratio": "current_ratio",
    "current ratio": "current_ratio",
    # Avg volume 20d
    "avg_volume_20d": "avg_volume_20d",
    "average volume 20d": "avg_volume_20d",
    "avg volume 20 day": "avg_volume_20d",
    "avg volume": "avg_volume_20d",
    # Relative volume
    "relative_volume": "relative_volume",
    "relative volume": "relative_volume",
    "rel volume": "relative_volume",
    # SMA 50/200
    "sma_50_200": "sma_50_200",
    "sma 50 200": "sma_50_200",
    "50 200 sma": "sma_50_200",
    "golden cross": "sma_50_200",
    "death cross": "sma_50_200",
    # Consecutive gains
    "consecutive_gains": "consecutive_gains",
    "consecutive gains": "consecutive_gains",
    "up days": "consecutive_gains",
    "consecutive up days": "consecutive_gains",
    # Institutional flow
    "institutional_flow": "institutional_flow",
    "institutional flow": "institutional_flow",
    "inst flow": "institutional_flow",
    "institutional buying": "institutional_flow",
}



# ──────────────────────────────────────────────
# EducationService — json-driven (single source of truth)
# ──────────────────────────────────────────────


class EducationService:
    """Plain-English explanations rendered from education.json.

    Content lives in ``frontend/src/content/education.json`` and is
    evaluated through the shared bands DSL (parity-tested with the
    frontend evaluator in ``education_bands``). Metric-name aliases are
    preserved for API compatibility.

    Typical usage::

        svc = EducationService()
        resp = svc.explain("pe_ratio", "35", symbol="AAPL")
        print(resp.plain_english)
    """

    def explain(
        self,
        metric: str,
        value: str,
        symbol: str | None = None,
        sector: str | None = None,
        price: float | None = None,
    ) -> EducationResponse:
        """Generate a plain-English explanation for a metric value.

        Args:
            metric: Metric name — any alias in ``_METRIC_ALIASES`` or a
                canonical key from education.json.
            value: The metric value as a string (e.g. ``"25.5"``,
                ``"bullish"``).
            symbol: Optional ticker symbol for context (LLM hook).
            sector: Optional sector context (LLM hook).
            price: Optional current price (reserved).

        Returns:
            An :class:`EducationResponse`. Unknown metrics return a
            graceful fallback with ``source="template"``.
        """
        canonical = self._normalize_metric(metric)

        lesson = _lesson_for(canonical) if canonical else None
        if canonical is None or lesson is None:
            logger.info(
                "Unknown metric requested: %r (normalised to %r)", metric, canonical
            )
            return EducationResponse(
                metric=metric,
                symbol=symbol,
                plain_english=(
                    f"Metric '{metric}' is not in our education library yet."
                ),
                value_context=None,
                actionable=None,
                source="template",
                cached=False,
            )

        # Render the value-aware band text (dynamic wording per value).
        parts: list[str] = []
        one_liner = lesson.get("oneLiner")
        if one_liner:
            parts.append(one_liner)

        interp = lesson.get("valueInterpretation")
        read_line = evaluate_bands(interp, value) if interp else ""
        if not read_line:
            # Fall back to the unconditional band so unknown/odd values
            # still get sensible guidance.
            fallback_band = next(
                (
                    b
                    for b in reversed((interp or {}).get("bands", []))
                    if not b.get("if", "").strip()
                ),
                None,
            )
            if fallback_band:
                read_line = fallback_band["text"].replace("${value}", value)
        if read_line:
            parts.append(read_line)

        why = lesson.get("whyMatters")
        if why:
            parts.append(why)

        resp = EducationResponse(
            metric=canonical,
            symbol=symbol,
            plain_english=" ".join(parts),
            value_context=None,
            actionable=None,
            source="template",
            cached=False,
        )

        if symbol:
            self._maybe_enhance_with_llm(
                resp=resp,
                canonical=canonical,
                value=value,
                symbol=symbol,
                sector=sector,
                llm_prompt=self._build_llm_prompt(canonical, value, symbol, sector),
                price=price,
            )

        return resp

    def deep_dive(self, metric: str) -> dict[str, Any] | None:
        """Return the full lesson dict (deep-dive view) for a metric key."""
        canonical = self._normalize_metric(metric) or metric
        return _lesson_for(canonical)

    @staticmethod
    def _build_llm_prompt(
        canonical: str, value: str, symbol: str, sector: str | None
    ) -> str:
        sector_ctx = sector or "its sector"
        return (
            f"Explain {canonical} of {value} for {symbol} in the context of "
            f"{sector_ctx}. Two sentences maximum, beginner-friendly, no "
            f"financial advice."
        )

    # ── Internal helpers ──────────────────────────────────────────

    @staticmethod
    def _normalize_metric(metric: str) -> str | None:
        """Normalise a user-supplied metric name to its canonical key.

        Strips whitespace, lowercases, then checks the alias map and —
        as a second chance — direct key membership in education.json.
        """
        key = metric.strip().lower()
        aliased = _METRIC_ALIASES.get(key)
        if aliased:
            return aliased
        # Direct canonical keys work even without an alias entry.
        data = _load_content()
        for section in ("metrics", "backtestMetrics", "tradePlan", "concepts"):
            if key in data.get(section, {}):
                return key
        return None

    @staticmethod
    def _maybe_enhance_with_llm(
        resp: EducationResponse,
        canonical: str,
        value: str,
        symbol: str,
        sector: str | None,
        llm_prompt: str,
        price: float | None = None,
    ) -> None:
        """Optionally enrich the response with a Gemini-generated note.

        Phase 5, flag-gated (``CONFLU_PROFESSIONAL_LLM_EDUCATION_ENABLED`` +
        ``llm_api_key``). Design guarantees:

        - Curated content is ALWAYS present; the LLM only fills
          ``value_context`` / ``actionable`` as clearly-secondary context.
        - Any failure (no key, flag off, timeout, HTTP error, rate limit,
          bad payload) leaves the curated response untouched.
        - Output is constrained: system prompt forbids advice language and
          caps length; result is truncated defensively.
        - Daily call budget respected via in-process counter.
        """
        settings = _get_professional_settings()
        if not settings or not settings.llm_education_enabled:
            return
        api_key = settings.llm_api_key
        if not api_key:
            return

        # Daily budget (in-process; resets on restart — acceptable for a garnish)
        today = date.today().isoformat()
        if _LLM_CALL_STATE["day"] != today:
            _LLM_CALL_STATE["day"] = today
            _LLM_CALL_STATE["count"] = 0
        if _LLM_CALL_STATE["count"] >= settings.max_daily_education_calls:
            logger.info("LLM education daily budget exhausted; skipping enhancement")
            return

        try:
            import httpx

            prompt = (
                f"Context: metric '{canonical}' has value {value} for {symbol}"
                + (f" in the {sector} sector." if sector else ".")
                + " Give ONE short observation (max 25 words) that is specific to"
                + " this symbol/value combination. No financial advice, no"
                + " recommendations, no disclaimers."
            )

            with httpx.Client(timeout=6.0) as client:
                r = client.post(
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    "gemini-2.0-flash:generateContent",
                    params={"key": api_key},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "systemInstruction": {
                            "parts": [
                                {
                                    "text": (
                                        "You are an educational footnote writer inside a"
                                        " stock-analytics app. State neutral, factual,"
                                        " symbol-specific observations. NEVER give advice"
                                        " (no buy/sell/should/consider/target words). Max"
                                        " 2 sentences. If unsure, say nothing useful and"
                                        " keep it generic."
                                    )
                                }
                            ]
                        },
                        "generationConfig": {
                            "temperature": 0.4,
                            "maxOutputTokens": 120,
                        },
                    },
                )
                r.raise_for_status()
                data = r.json()
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                    .strip()
                )

            if not text:
                logger.info("LLM education returned empty text; keeping template response")
                return

            resp.value_context = text[:280]  # defensive truncation
            resp.actionable = None  # never surface advice-shaped fields from the model
            resp.source = "llm"
            _LLM_CALL_STATE["count"] += 1
            logger.info(
                "LLM education enhanced", metric=canonical, symbol=symbol, chars=len(text)
            )
        except Exception as exc:  # noqa: BLE001 — garnish must never break the meal
            logger.info("LLM education enhancement skipped", error=str(exc)[:200])
