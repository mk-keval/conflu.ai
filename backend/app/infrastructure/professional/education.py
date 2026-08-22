"""Education Service — plain-English explanations of financial metrics.

Provides static template-based explanations for 20+ financial metrics,
with conditional logic built into every template. Supports metric name
normalization and optional LLM-enhanced versions when symbol context is
available.
"""

from __future__ import annotations

import re
from typing import Any

from backend.app.core.logging import get_logger
from backend.app.infrastructure.professional.models import EducationResponse

logger = get_logger(__name__)

# ──────────────────────────────────────────────
# Metric name normalization map
# ──────────────────────────────────────────────
# Maps user-supplied variations (including common display names and
# abbreviated forms) to the canonical metric keys used in _TEMPLATES.

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
    "β": "beta",
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
# Template rendering helpers
# ──────────────────────────────────────────────


def _compare_numbers(left: float, operator: str, right: float) -> bool:
    """Compare two float values using the supplied operator.

    Args:
        left: Left-hand operand.
        operator: One of ``>``, ``<``, ``>=``, ``<=``, ``==``, ``!=``.
        right: Right-hand operand.

    Returns:
        Result of the comparison.
    """
    if operator == ">":
        return left > right
    elif operator == "<":
        return left < right
    elif operator == ">=":
        return left >= right
    elif operator == "<=":
        return left <= right
    elif operator == "==":
        return abs(left - right) < 1e-9
    elif operator == "!=":
        return abs(left - right) >= 1e-9
    return False


def _compare_strings(left: str, operator: str, right: str) -> bool:
    """Compare two strings case-insensitively.

    Args:
        left: Left-hand operand (the user-supplied value).
        operator: ``==`` or ``!=``.
        right: Right-hand operand (from the template condition).

    Returns:
        Result of the comparison.
    """
    if operator == "==":
        return left.strip().lower() == right.strip().lower()
    elif operator == "!=":
        return left.strip().lower() != right.strip().lower()
    return False


def _evaluate_condition(condition: str, value: str) -> bool:
    """Evaluate a single comparison condition against the given value.

    Supports patterns such as::

        value > 30
        value < 15
        value == 'bullish'
        value >= 50
        value != 'selling'

    Args:
        condition: Raw condition string (e.g. ``"value > 30"``).
        value: The actual metric value to substitute.

    Returns:
        ``True`` if the condition is satisfied, ``False`` otherwise.
    """
    condition = condition.strip()

    # Match: value <op> <rhs>  where <rhs> is a quoted string or a number
    match = re.match(
        r"value\s*(>=|<=|!=|==|>|<)\s*(?:'([^']*)'|(-?\d+\.?\d*))\s*$",
        condition,
    )
    if not match:
        logger.warning("Could not parse condition expression: %s", condition)
        return False

    operator = match.group(1)
    string_rhs = match.group(2)
    numeric_rhs_str = match.group(3)

    if string_rhs is not None:
        return _compare_strings(value, operator, string_rhs)

    # Numeric comparison
    try:
        numeric_value = float(value)
    except (ValueError, TypeError):
        logger.warning(
            "Cannot convert value %r to float for condition: %s", value, condition
        )
        return False

    return _compare_numbers(numeric_value, operator, float(numeric_rhs_str))


def _evaluate_ternary_chain(expression: str, value: str) -> str:
    """Evaluate a chain of ternary expressions.

    The expected grammar is::

        condition ? 'true_branch' : condition ? 'true_branch' : 'fallback'

    Conditions are simple comparisons (see :func:_evaluate_condition).
    Text branches MUST be single-quoted. The final branch is an implicit
    else (no leading condition).

    Args:
        expression: The ternary chain (everything inside ``{...}``).
        value: The metric value to test conditions against.

    Returns:
        The text of the first matching branch, or the fallback text.
    """
    expr = expression.strip()

    # Split into condition and the rest (everything after the first ``?``)
    parts = expr.split("?", 1)
    if len(parts) < 2:
        # No ternary operator found — return as-is
        return expr

    condition_str = parts[0].strip()
    rest = parts[1]

    # Extract the true-branch (first single-quoted string)
    true_match = re.match(r"\s*'([^']*)'\s*:\s*(.*)", rest)
    if not true_match:
        # Malformed — return remainder verbatim
        return rest.strip()

    true_text = true_match.group(1)
    remainder = true_match.group(2).strip()

    # Evaluate the first condition
    if _evaluate_condition(condition_str, value):
        return true_text

    # Remainder is either a fallback string or another ternary chain
    if remainder.startswith("'"):
        fallback_match = re.match(r"'([^']*)'", remainder)
        return fallback_match.group(1) if fallback_match else remainder
    else:
        # Recursively evaluate the next ternary
        return _evaluate_ternary_chain(remainder, value)


def _render_template(template: str, value: str) -> str:
    """Render a template string with value interpolation and conditionals.

    Performs two passes:

    1. Replaces ``${value}`` with the actual value string.
    2. Evaluates ``{condition ? 'a' : condition ? 'b' : 'c'}`` blocks.

    Args:
        template: The raw template string from ``_TEMPLATES``.
        value: The metric value to substitute.

    Returns:
        Fully rendered plain-English text.
    """
    # Pass 1: simple variable interpolation
    result = template.replace("${value}", value)

    # Pass 2: evaluate conditional blocks ``{...}``
    def _replace_conditional(match: re.Match) -> str:
        block = match.group(1)
        return _evaluate_ternary_chain(block, value)

    result = re.sub(r"\{([^}]+)\}", _replace_conditional, result)

    return result


# ──────────────────────────────────────────────
# EducationService
# ──────────────────────────────────────────────


class EducationService:
    """Provides plain-English explanations for financial metrics.

    Uses a library of hand-crafted templates with built-in conditional
    logic to generate context-aware explanations without any external
    API calls. Each template includes a companion LLM prompt for future
    LLM-enhanced versions.

    The service also normalises metric name variations so that callers
    can pass ``"P/E Ratio"``, ``"pe"``, or ``"price to earnings"`` and
    still get the correct explanation.

    Typical usage::

        svc = EducationService()
        resp = svc.explain("pe_ratio", "35", symbol="AAPL", sector="Technology")
        print(resp.plain_english)
        # "You're paying $35 for $1 of earnings. ..."
    """

    # ── Metric templates ──────────────────────────────────────────

    _TEMPLATES: dict[str, dict[str, str]] = {
        "pe_ratio": {
            "template": (
                "You're paying ${value} for $1 of earnings. "
                "Market average is ~20x. "
                "{value > 30 ? 'This suggests the stock is priced for perfection "
                "— expensive.' : value < 15 ? 'This suggests the stock may be "
                "undervalued — but check why.' : 'This is in a reasonable range.'}"
                " Veteran lens: multiple only matters at the exit — institutions "
                "pay up for earnings power they can see; we care whether the "
                "next report defends it."
            ),
            "llm_prompt": (
                "Explain P/E ratio of {value} for {symbol} in the {sector} sector. "
                "Keep it to 2 sentences for a beginner investor."
            ),
        },
        "rsi": {
            "template": (
                "Momentum is at ${value}. "
                "{value > 70 ? 'This is overbought — a pullback may be coming.' "
                ": value < 30 ? 'This is oversold — a bounce could be imminent.' "
                ": 'This is in neutral territory.'}"
                " Veteran lens: overbought in a strong trend is strength, not a "
                "sell signal — institutions add there; we just demand tighter "
                "entries and honor the stop."
            ),
            "llm_prompt": "Explain RSI of {value} for {symbol} in simple terms.",
        },
        "atr_pct": {
            "template": (
                "The stock moves ${value}% per day on average. "
                "{value > 5 ? 'High volatility — use wider stop losses.' "
                ": value < 2 ? 'Low volatility — tighter stops work fine.' "
                ": 'Normal volatility range.'}"
                " Veteran lens: this volatility number sets position size — "
                "wider ATR means fewer shares for the same dollar risk, never "
                "a wider mental stop."
            ),
            "llm_prompt": "Explain ATR% of {value} for {symbol}.",
        },
        "beta": {
            "template": (
                "This stock moves ${value}x the S&P 500. "
                "{value > 1.5 ? 'Aggressive — it amplifies market moves.' "
                ": value < 0.5 ? 'Defensive — it barely moves with the market.' "
                ": 'It moves roughly in line with the market.'}"
                " Veteran lens: beta is portfolio heat — high-beta names get "
                "smaller size so a market wobble can't take out the whole week."
            ),
            "llm_prompt": "Explain beta of {value} for {symbol}.",
        },
        "adx": {
            "template": (
                "Trend strength is at ${value}. "
                "{value >= 50 ? 'Very strong trend in play.' "
                ": value >= 25 ? 'Trending market with decent strength.' "
                ": 'Weak or choppy price action — trend-following may be less effective.'}"
            ),
            "llm_prompt": "Explain ADX of {value} and what it means for trading.",
        },
        "macd": {
            "template": (
                "MACD status: ${value}. "
                "{value == 'bullish' ? 'Momentum is building to the upside.' "
                ": value == 'bearish' ? 'Momentum is shifting to the downside.' "
                ": 'Momentum is neutral — waiting for a signal.'}"
            ),
            "llm_prompt": "Explain MACD {value} signal for {symbol}.",
        },
        "volume_ratio": {
            "template": (
                "Volume is ${value}x the average. "
                "{value > 2 ? 'Unusually high volume — significant institutional activity.' "
                ": value > 1.5 ? 'Above-average volume — increased interest.' "
                ": 'Normal trading activity.'}"
            ),
            "llm_prompt": "Explain volume ratio of {value} for {symbol}.",
        },
        "ma_alignment": {
            "template": (
                "Moving averages are in a {value} alignment. "
                "{value == 'bullish' ? 'Short-term > mid-term > long-term — textbook uptrend.' "
                ": value == 'bearish' ? 'Short-term below long-term — downward pressure.' "
                ": 'Mixed — the trend is not clearly established.'}"
            ),
            "llm_prompt": "Explain {value} MA alignment for {symbol}.",
        },
        "bb_position": {
            "template": (
                "Price is ${value} the Bollinger Bands. "
                "{value == 'above_upper' ? 'Extended above the upper band — possibly overbought.' "
                ": value == 'below_lower' ? 'Below the lower band — possibly oversold.' "
                ": 'Within the bands — normal trading range.'}"
            ),
            "llm_prompt": "Explain Bollinger Band {value} position for {symbol}.",
        },
        "market_cap": {
            "template": (
                "Market cap is ${value}B. "
                "{value > 200 ? 'Mega-cap — among the largest companies globally.' "
                ": value > 10 ? 'Large-cap — established, liquid, institutionally owned.' "
                ": value > 2 ? 'Mid-cap — growing with more upside potential, more risk.' "
                ": 'Small-cap — higher growth potential but much more volatile.'}"
            ),
            "llm_prompt": "Explain what a ${value}B market cap means for {symbol}.",
        },
        "eps": {
            "template": (
                "Earnings per share (EPS) is ${value}. "
                "{value > 0 ? 'The company is generating positive earnings — profitable.' "
                ": 'The company is losing money per share — not profitable.'}"
            ),
            "llm_prompt": "Explain EPS of {value} for {symbol}.",
        },
        "profit_margin": {
            "template": (
                "Profit margin is {value}%. "
                "{value > 20 ? 'Highly profitable — strong pricing power and cost control.' "
                ": value > 10 ? 'Healthy margins — decent business efficiency.' "
                ": value > 0 ? 'Thin margins — cost-sensitive business.' "
                ": 'Negative margins — company is operating at a loss.'}"
            ),
            "llm_prompt": "Explain profit margin of {value}% for {symbol}.",
        },
        "debt_to_equity": {
            "template": (
                "Debt-to-equity is ${value}. "
                "{value > 2 ? 'High leverage — the company carries significant debt "
                "relative to equity.' : value > 1 ? 'Moderate leverage — manageable "
                "but worth watching.' : 'Low leverage — conservative capital structure "
                "with little debt.'}"
            ),
            "llm_prompt": "Explain debt-to-equity of {value} for {symbol}.",
        },
        "revenue_growth": {
            "template": (
                "Revenue growth is {value}% year-over-year. "
                "{value > 20 ? 'Strong growth — rapidly expanding business.' "
                ": value > 10 ? 'Healthy growth — above average expansion.' "
                ": value > 0 ? 'Modest growth — growing but slowly.' "
                ": 'Declining revenue — business is shrinking.'}"
            ),
            "llm_prompt": "Explain {value}% revenue growth for {symbol}.",
        },
        "fcf_yield": {
            "template": (
                "Free cash flow yield is {value}%. "
                "{value > 5 ? 'Strong cash generation relative to price — "
                "potentially undervalued.' : value > 2 ? 'Decent cash flow yield.' "
                ": 'Low cash flow yield — the price is high relative to cash generated.'}"
            ),
            "llm_prompt": "Explain FCF yield of {value}% for {symbol}.",
        },
        "analyst_consensus": {
            "template": (
                "Analyst consensus is: {value}. "
                "This reflects the average opinion of Wall Street analysts "
                "covering the stock."
            ),
            "llm_prompt": (
                "Explain 'analyst consensus' of {value} for {symbol}."
            ),
        },
        "insider_activity": {
            "template": (
                "Insider activity is: {value}. "
                "{value == 'buying' ? 'Insiders are buying shares — often a bullish signal.' "
                ": value == 'selling' ? 'Insiders are selling shares — could be routine, "
                "but worth monitoring.' : 'No significant insider activity detected.'}"
            ),
            "llm_prompt": "Explain insider activity of {value} for {symbol}.",
        },
        "short_interest": {
            "template": (
                "Short interest is {value}% of float. "
                "{value > 20 ? 'Very high — extreme bearish sentiment or potential "
                "squeeze setup.' : value > 10 ? 'Elevated — significant bearish "
                "positioning.' : value > 5 ? 'Moderate short interest.' : 'Low short "
                "interest — minimal bearish bets.'}"
            ),
            "llm_prompt": "Explain {value}% short interest for {symbol}.",
        },
        "institutional_ownership": {
            "template": (
                "Institutional ownership is {value}%. "
                "{value > 70 ? 'Very high — widely held by institutions, "
                "lots of smart money.' : value > 40 ? 'Healthy institutional interest.' "
                ": value > 10 ? 'Moderate institutional ownership.' "
                ": 'Low — mostly retail-owned.'}"
            ),
            "llm_prompt": "Explain {value}% institutional ownership for {symbol}.",
        },
        "dividend_yield": {
            "template": (
                "Dividend yield is {value}%. "
                "{value > 4 ? 'High yield — could indicate a mature/distressed "
                "company or income play.' : value > 2 ? 'Moderate yield — decent "
                "income with growth potential.' : value > 0 ? 'Low yield — company "
                "reinvests most earnings into growth.' : 'No dividend — all earnings "
                "reinvested in growth.'}"
            ),
            "llm_prompt": "Explain {value}% dividend yield for {symbol}.",
        },
        "short_ratio": {
            "template": (
                "Short ratio (days to cover) is ${value} days. "
                "${value > 10 ? 'EXTREMELY HIGH — would take over 10 days for all shorts to cover. Explosive squeeze potential.' "
                ": value > 5 ? 'HIGH — significant squeeze risk. Short sellers are crowded and vulnerable.' "
                ": value > 2 ? 'MODERATE — some squeeze potential. Shorts could cover in a few days.' "
                ": 'LOW — short positions can be closed quickly. Less squeeze risk.'}"
            ),
            "llm_prompt": "Explain short ratio of ${value} days for {symbol}. What does this mean for squeeze potential?",
        },
        "earnings_growth_yoy": {
            "template": (
                "Earnings growth (year-over-year) is ${value}%. "
                "${value > 50 ? 'EXPLOSIVE growth — earnings growing much faster than revenue. Becoming more efficient.' "
                ": value > 20 ? 'STRONG growth — rapidly improving profitability. Quality business signal.' "
                ": value > 0 ? 'POSITIVE growth — earnings heading in the right direction.' "
                ": value > -20 ? 'SLIGHT decline — earnings down a bit. Monitor but not a crisis.' "
                ": 'SIGNIFICANT decline — profits shrinking. Red flag unless one-time event.'}"
            ),
            "llm_prompt": "Explain ${value}% YoY earnings growth for {symbol}. Is this sustainable?",
        },
        "peg_ratio": {
            "template": (
                "PEG ratio is ${value}. "
                "${value < 0 ? 'NEGATIVE — earnings are shrinking. The low PEG is NOT a bargain, it is a warning.' "
                ": value < 1 ? 'UNDERVALUED relative to growth. Price is low for the growth rate. Often a good sign.' "
                ": value < 2 ? 'FAIRLY VALUED. Price is reasonable for the growth rate.' "
                ": 'OVERVALUED relative to growth. Price is high for the growth rate. Either growth must accelerate or the stock is expensive.'}"
            ),
            "llm_prompt": "Explain PEG ratio of ${value} for {symbol}. What does this tell us about value vs growth?",
        },
        "price_to_sales": {
            "template": (
                "Price-to-sales (P/S) ratio is ${value}. "
                "${value > 20 ? 'VERY HIGH — common for hyper-growth tech. Paying huge premium for future revenue. Risky if growth slows.' "
                ": value > 5 ? 'ABOVE AVERAGE — market is optimistic about future growth. Reasonable for growth companies.' "
                ": value > 1 ? 'TYPICAL range. Normal valuation for most businesses.' "
                ": value > 0 ? 'LOW — sales valued conservatively. Could be bargain or value trap.' "
                ": 'NEGATIVE (unusual) — likely a data issue.'}"
            ),
            "llm_prompt": "Explain P/S ratio of ${value} for {symbol}. When is this metric most useful?",
        },
        "current_ratio": {
            "template": (
                "Current ratio is ${value}. "
                "${value > 3 ? 'VERY HEALTHY — far more short-term assets than liabilities. Strong safety cushion.' "
                ": value > 1.5 ? 'HEALTHY — can comfortably cover short-term obligations. Standard for most businesses.' "
                ": value > 1 ? 'ADEQUATE — barely covers short-term debts. Watch for any deterioration.' "
                ": 'CONCERNING — short-term liabilities exceed liquid assets. Cash flow problems possible.'}"
            ),
            "llm_prompt": "Explain current ratio of ${value} for {symbol}. What does this say about financial health?",
        },
"avg_volume_20d": {
            "template": (
                "20-day average volume is ${value} shares/day. "
                "${value > 10000000 ? 'VERY LIQUID — over 10M shares/day. Huge volume, easy to trade large positions.' "
                ": value > 1000000 ? 'LIQUID — over 1M shares/day. Normal for mid-to-large caps.' "
                ": value > 100000 ? 'MODERATE — over 100K shares/day. Tradeable but larger orders may move price.' "
                ": 'LOW — under 100K shares/day. Be careful with position size, spreads may be wide.'}"
            ),
            "llm_prompt": "Explain what ${value} avg daily volume means for {symbol} liquidity.",
        },
        "relative_volume": {
            "template": (
                "Relative volume is ${value}x average. "
                "${value > 3 ? 'EXCEPTIONALLY HIGH — major institutional activity right now.' "
                ": value > 2 ? 'VERY HIGH — significant unusual interest.' "
                ": value > 1.5 ? 'ELEVATED — more trading than normal.' "
                ": value >= 1 ? 'NORMAL — typical trading activity.' "
                ": 'BELOW AVERAGE — light trading, moves may lack conviction.'}"
            ),
            "llm_prompt": "Explain relative volume of ${value}x for {symbol}. What does this indicate about current interest?",
        },
        "sma_50_200": {
            "template": (
                "SMA 50/200 status: ${value}. "
                "${value == 'golden_cross' ? 'GOLDEN CROSS — 50-day crossed ABOVE 200-day! Classic bullish signal. Short-term trend now stronger than long-term.' "
                ": value == 'death_cross' ? 'DEATH CROSS — 50-day crossed BELOW 200-day. Serious bearish signal. Short-term trend breaking down.' "
                ": 'NO CROSS — 50 and 200-day averages maintaining current order. No extreme trend change signal.'}"
            ),
            "llm_prompt": "Explain ${value} SMA 50/200 cross for {symbol}. Historical reliability?",
        },
        "consecutive_gains": {
            "template": (
                "${value} consecutive up days. "
                "${value >= 7 ? 'EXCEPTIONAL streak — over a week of gains. Intense buying pressure but may be due for a breather.' "
                ": value >= 5 ? 'STRONG streak — full week of gains. Bullish momentum.' "
                ": value >= 3 ? 'MODERATE streak — 3+ up days. Positive short-term momentum.' "
                ": value == 1 ? 'JUST STARTED — one up day. Does not make a trend yet.' "
                ": 'DECLINING — stock has been going down recently. Check other indicators.'}"
            ),
            "llm_prompt": "Explain ${value} consecutive up days for {symbol}. What typically happens next?",
        },
        "institutional_flow": {
            "template": (
                "Institutional flow is ${value} (net buying/selling last month). "
                "${value > 5 ? 'STRONG BUYING — major investors accumulating. One of the most bullish signals.' "
                ": value > 1 ? 'MODERATE BUYING — institutions adding to positions. Mildly bullish.' "
                ": value > -1 ? 'NEUTRAL — no significant institutional activity.' "
                ": value > -5 ? 'MODERATE SELLING — institutions reducing positions. Mildly bearish.' "
                ": 'STRONG SELLING — smart money exiting. Significant warning sign.'}"
            ),
            "llm_prompt": "Explain institutional flow of ${value} for {symbol}. What does smart money movement tell us?",
        },
    }

    # ── Public API ────────────────────────────────────────────────

    def explain(
        self,
        metric: str,
        value: str,
        symbol: str | None = None,
        sector: str | None = None,
        price: float | None = None,
    ) -> EducationResponse:
        """Generate a plain-English explanation for a metric value.

        Looks up the metric (with name normalisation), renders the static
        template with the supplied value, and optionally enriches the
        response with an LLM-generated explanation when a symbol is
        provided and the LLM feature flag is enabled.

        Args:
            metric: Metric name — accepts any variation listed in
                ``_METRIC_ALIASES`` (e.g. ``"pe_ratio"``, ``"P/E Ratio"``,
                ``"pe"``, ``"price to earnings"``).
            value: The metric value as a string (e.g. ``"25.5"``,
                ``"bullish"``, ``"3.2"``).
            symbol: Optional ticker symbol for context. When provided,
                the service checks whether LLM enhancement should be
                applied.
            sector: Optional sector name (e.g. ``"Technology"``) used
                as context for LLM prompts.
            price: Optional current price, reserved for future use in
                contextual explanations.

        Returns:
            An :class:`EducationResponse` containing the explanation.

        Raises:
            No exceptions are raised. Unknown metrics return a fallback
            response with ``source="template"``.

        Examples:
            >>> svc = EducationService()
            >>> resp = svc.explain("pe_ratio", "35", symbol="AAPL")
            >>> resp.plain_english
            "You're paying $35 for $1 of earnings. ..."
            >>> resp.metric
            'pe_ratio'
            >>> resp.source
            'template'
        """
        canonical = self._normalize_metric(metric)

        if canonical is None or canonical not in self._TEMPLATES:
            logger.info("Unknown metric requested: %r (normalised to %r)", metric, canonical)
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

        template_entry = self._TEMPLATES[canonical]
        template = template_entry["template"]
        llm_prompt = template_entry.get("llm_prompt", "")

        # Render the static template
        plain_english = _render_template(template, value)

        # Build the base response
        resp = EducationResponse(
            metric=canonical,
            symbol=symbol,
            plain_english=plain_english,
            value_context=None,
            actionable=None,
            source="template",
            cached=False,
        )

        # Optionally enhance with LLM when a symbol is present
        if symbol:
            self._maybe_enhance_with_llm(
                resp=resp,
                canonical=canonical,
                value=value,
                symbol=symbol,
                sector=sector,
                llm_prompt=llm_prompt,
                price=price,
            )

        return resp

    # ── Internal helpers ──────────────────────────────────────────

    @staticmethod
    def _normalize_metric(metric: str) -> str | None:
        """Normalise a user-supplied metric name to its canonical key.

        Strips whitespace, lowercases, and looks up the result in
        ``_METRIC_ALIASES``.

        Args:
            metric: Raw metric input from the caller.

        Returns:
            Canonical metric key (e.g. ``"pe_ratio"``), or ``None`` if
            no match is found.
        """
        key = metric.strip().lower()
        return _METRIC_ALIASES.get(key)

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
        """Check the LLM enhancement flag and enrich the response.

        **This is a placeholder for future LLM integration.** When the
        LLM enhancement feature flag is enabled, this method will:

        1. Format the ``llm_prompt`` with ``{value}``, ``{symbol}``,
           ``{sector}``, and ``{price}``.
        2. Call the LLM service to generate a richer explanation.
        3. Populate ``resp.value_context`` and ``resp.actionable``.
        4. Set ``resp.source`` to ``"llm"`` or ``"combined"``.

        Currently this is a no-op awaiting the feature flag
        implementation.
        """
        # TODO: Implement LLM enhancement when feature flag is available
        pass
