# TV Screener API — Instant discovery + on-demand deep analysis
"""
Endpoints:
- POST /api/v1/screen/tv           — Instant TV discovery + confluence scoring
- POST /api/v1/screen/tv/multi-tf  — Multi-timeframe intersection
- POST /api/v1/screen/tv/analyze   — Deep analysis for matched ticker
- GET  /api/v1/screen/tv/templates — List available screen templates
- GET  /api/v1/screen/tv/templates/{name} — Load a screen template
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.infrastructure.screener.tv_engine import TVScreenEngine
from backend.app.infrastructure.screener.tv_models import (
    TVScreenRequest,
    TVScreenResponse,
    ScoredTickerResponse,
    EliteEnrichment,
    VerdictResponse,
    DeepAnalysisRequest,
    DeepAnalysisResponse,
    dict_to_screen_config,
)
from backend.app.infrastructure.screener.verdict import build_verdict
from backend.app.infrastructure.screener.configs import (
    ScreenConfig,
    load_screen_template,
    list_screen_templates,
)
from backend.app.infrastructure.backtest.external_backtest import ExternalBacktestEngine, BacktestConfig
from backend.app.infrastructure.data.fetcher import OHLCVFetcher
from backend.app.core.logging import get_logger

log = get_logger("conflu.api.tv_screener")

router = APIRouter(prefix="/screen/tv", tags=["tv-screener"])


# =========================================================================
# Dependency
# =========================================================================
# Module-level singleton so the engine's TVCache (60s TTL) and TVRateLimiter
# (25 req/min) persist across requests. A per-request engine defeated both —
# every request started with a cold cache and a full token bucket.
_ENGINE = TVScreenEngine()


def get_tv_engine() -> TVScreenEngine:
    return _ENGINE


# =========================================================================
# Endpoints
# =========================================================================


def _resolve_config(config: dict[str, Any] | str) -> Any:
    """Resolve config from inline dict or template name.

    Tries exact filename first. If not found, searches all YAML screen
    files for one whose ``name`` field matches *config* (handles the
    case where the human-readable display name differs from the filename).
    """
    if isinstance(config, str):
        try:
            return load_screen_template(config)
        except FileNotFoundError:
            # Fallback: search screen files by their embedded name field
            from backend.app.infrastructure.screener.configs import _resolve_screens_dir
            import yaml

            screens_dir = _resolve_screens_dir()
            for p in sorted(screens_dir.glob("*.yaml")):
                try:
                    with open(p) as f:
                        data = yaml.safe_load(f)
                    if data and data.get("name") == config:
                        return ScreenConfig(**data)
                except Exception:
                    continue
            raise
    return dict_to_screen_config(config)


def _build_scored_response(
    scored: list[dict],
    enrich_with_catalysts: bool = False,
    min_confluence: int = 0,
) -> list[ScoredTickerResponse]:
    """Build typed response from scored tickers (includes elite enrichment).

    D-47 PR 1: when enrich_with_catalysts=True, run the 5 D-46 catalyst
    detectors on each result in parallel and attach a catalyst_signals
    dict. min_confluence filters out symbols with fewer than N firing
    signals.
    """
    # D-44 (G14): Look up earnings proximity from the hand-curated
    # calendar for each ticker in the batch. The lookup is in-process
    # (reads backend/app/data/earnings_calendar.json), so a single
    # cache load is sufficient.
    from backend.app.domain.ticker_analysis.earnings_filter import (
        get_binary_risk,
    )

    # D-47 PR 1: optionally run catalyst signals in parallel
    catalyst_results: dict[str, Any] = {}
    if enrich_with_catalysts and scored:
        from concurrent.futures import ThreadPoolExecutor
        from backend.app.infrastructure.screener.catalyst_filter import (
            detect_catalyst_signals,
        )

        def _run_catalysts(symbol: str) -> tuple[str, Any]:
            try:
                signals = detect_catalyst_signals(symbol)
                return symbol, signals
            except Exception as exc:
                log.exception("catalyst_signal_failed", symbol=symbol)
                return symbol, None

        with ThreadPoolExecutor(max_workers=8, thread_name_prefix="catalyst") as pool:
            for sym, sig in pool.map(_run_catalysts, [r["symbol"] for r in scored]):
                catalyst_results[sym] = sig

    out: list[ScoredTickerResponse] = []
    for r in scored:
        conf = r["confluence"]
        elite_raw = r.get("elite") or {}
        verdict = build_verdict(
            symbol=r["symbol"],
            score_total=conf.total,
            rating=conf.rating,
            breakdown=conf.breakdown,
            elite=elite_raw,
            tv_data=r.get("tv_data") or {},
        )
        # D-44: G14 (Gap 1) — attach binary_risk + earnings_date.
        # Batch path: manual calendar only. A per-ticker yfinance fallback here
        # costs ~0.2s per row (500 rows ≈ 100s) and rate-limits Yahoo.
        binary_risk, earnings_date = get_binary_risk(
            r["symbol"], window_days=5, allow_yfinance=False
        )

        # D-47 PR 1: attach catalyst signals if enriched
        cat_dict = None
        cat_count = 0
        cat_summary = None
        cat_boost = 0
        if enrich_with_catalysts and r["symbol"] in catalyst_results:
            sig = catalyst_results[r["symbol"]]
            if sig is not None:
                cat_dict = sig.to_dict()
                cat_count = sig.confluence_count
                cat_summary = sig.summary
                cat_boost = min(cat_count, 5)
                # Apply confluence boost to the score
                conf.total = (conf.total or 0) + cat_boost

        # Apply min_confluence filter
        if enrich_with_catalysts and cat_count < min_confluence:
            continue

        out.append(
            ScoredTickerResponse(
                symbol=r["symbol"],
                score=conf.total,
                breakdown=conf.breakdown,
                entry=conf.entry,
                stop_loss=conf.stop_loss,
                targets=conf.targets,
                risk_reward=conf.risk_reward,
                rating=conf.rating,
                rationale=conf.rationale,
                tv_data=r["tv_data"],
                elite=EliteEnrichment(**elite_raw) if elite_raw else None,
                probable_fund=r.get("probable_fund", False),
                probable_fund_reason=r.get("probable_fund_reason"),
                verdict=VerdictResponse(**verdict.to_dict()),
                binary_risk=binary_risk,
                earnings_date=earnings_date,
                catalyst_signals=cat_dict,
                catalyst_confluence_count=cat_count,
                catalyst_summary=cat_summary,
            )
        )
    return out


@router.post("", response_model=TVScreenResponse)
async def screen_tv(
    request: TVScreenRequest,
    engine: TVScreenEngine = Depends(get_tv_engine),
) -> TVScreenResponse:
    """
    Stage 1: Instant TV Screener discovery + confluence scoring.
    Runs the screen on TradingView's server (12K+ symbols, <2s).
    Returns ranked tickers with confluence scores from TV data ONLY.
    """
    start = time.monotonic()

    try:
        config = _resolve_config(request.config)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if request.multi_timeframe:
        result = await engine.screen_multi_tf(config)
    else:
        result = await engine.screen(config, limit=request.limit)

    return TVScreenResponse(
        screen_name=result["screen_name"],
        total_matches=result["total_matches"],
        execution_ms=round((time.monotonic() - start) * 1000),
        timeframe=result.get("timeframe", config.timeframes[0] if config.timeframes else "1D"),
        fetched_at=datetime.now(timezone.utc).isoformat(),
        results=_build_scored_response(
            result["results"],
            enrich_with_catalysts=request.enrich_with_catalysts,
            min_confluence=request.min_confluence,
        ),
    )


@router.post("/multi-tf", response_model=dict[str, Any])
async def screen_tv_multi_tf(
    request: TVScreenRequest,
    engine: TVScreenEngine = Depends(get_tv_engine),
) -> dict[str, Any]:
    """
    Multi-timeframe TV screen: runs per-TF, intersects tickers, scores.
    Returns tickers that match ALL timeframes.
    """
    start = time.monotonic()

    try:
        config = _resolve_config(request.config)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = await engine.screen_multi_tf(config)

    return {
        "screen_name": result["screen_name"],
        "total_matches": result["total_matches"],
        "execution_ms": round((time.monotonic() - start) * 1000),
        "timeframes": result.get("timeframes", []),
        "results": _build_scored_response(result["results"]),
    }


@router.post("/analyze", response_model=dict[str, Any])
async def deep_analyze(
    request: DeepAnalysisRequest,
    engine: TVScreenEngine = Depends(get_tv_engine),
) -> dict[str, Any]:
    """
    Stage 3: On-demand deep analysis for a single ticker.
    Fetches OHLCV, computes indicators, runs backtest, risk.
    """
    start = time.monotonic()

    try:
        result = await engine.deep_analyze(
            request.symbol,
            request.timeframe,
            tv_data=request.tv_data,
            include_backtest=request.include_backtest,
            include_risk=request.include_risk,
        )

        return {
            "symbol": result.get("symbol", request.symbol),
            "timeframe": result.get("timeframe", request.timeframe),
            "confluence_score": result.get("confluence_score", 0),
            "entry": result.get("entry", 0),
            "stop_loss": result.get("stop_loss", 0),
            "targets": result.get("targets", []),
            "backtest": result.get("backtest") if request.include_backtest else None,
            "risk": result.get("risk") if request.include_risk else None,
            "execution_ms": round((time.monotonic() - start) * 1000),
            "has_ohlcv": result.get("has_ohlcv", False),
            "tv_fallback": result.get("tv_fallback"),
        }

    except Exception as e:
        log.exception("deep_analyze_failed", symbol=request.symbol, error=str(e))
        raise HTTPException(status_code=500, detail=f"Deep analysis failed: {str(e)}")


@router.get("/templates", response_model=list[dict[str, str]])
async def list_templates() -> list[dict[str, str]]:
    """List available screen templates."""
    return list_screen_templates()


@router.get("/templates/{name}", response_model=dict[str, Any])
async def get_template(name: str) -> dict[str, Any]:
    """Load a screen template by name (supports both filename and display name)."""
    try:
        config = load_screen_template(name)
        return config.model_dump()
    except FileNotFoundError:
        pass

    # Fallback: search screen files by their embedded name field
    from backend.app.infrastructure.screener.configs import _resolve_screens_dir
    import yaml

    screens_dir = _resolve_screens_dir()
    for p in sorted(screens_dir.glob("*.yaml")):
        try:
            with open(p) as f:
                data = yaml.safe_load(f)
            if data and data.get("name") == name:
                return ScreenConfig(**data).model_dump()
        except Exception:
            continue

    raise HTTPException(status_code=404, detail=f"Screen template '{name}' not found")


# =========================================================================
# Helper
# =========================================================================
# External Backtest Endpoint (Yahoo Finance + pandas, no vectorbt)
# =========================================================================

class ExternalBacktestRequest(BaseModel):
    """Request for a single backtest using a template and Yahoo Finance data."""
    template: str
    symbols: list[str]
    start: str
    end: str
    timeframe: str = "1D"
    initial_cash: float = 100_000
    fees_bps: float = 10.0
    slippage_bps: float = 5.0
    position_sizing: Literal["fixed", "atr", "kelly"] = "fixed"
    sizing_params: dict[str, Any] = Field(default_factory=dict)
    signal_params: dict[str, Any] = Field(default_factory=dict)
    stop_atr_mult: float = 2.0
    target_atr_mult: float = 3.0
    max_hold_bars: int | None = None


class ExternalBacktestTrade(BaseModel):
    trade_id: int
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    units: float
    pnl: float
    return_pct: float
    hold_days: int


class ExternalBacktestResponse(BaseModel):
    run_id: str
    template: str
    symbol: str
    timeframe: str
    metrics: dict[str, float]
    trades: list[ExternalBacktestTrade]
    equity_curve: list[dict[str, Any]]
    duration_ms: float


@router.post("/backtest/external", response_model=ExternalBacktestResponse)
async def run_external_backtest(request: ExternalBacktestRequest) -> ExternalBacktestResponse:
    """Run a single backtest using a template and Yahoo Finance data (no vectorbt).
    
    Uses the ExternalBacktestEngine which fetches data from Yahoo Finance,
    computes indicators with pandas_ta, and runs simulation with pure pandas/numpy.
    """
    from backend.app.infrastructure.backtest.external_backtest import ExternalBacktestEngine, BacktestConfig
    from backend.app.infrastructure.data.fetcher import OHLCVFetcher
    from backend.app.infrastructure.screener.configs import load_screen_template
    
    try:
        # Load template: pass FULL filter rules so per-rule operator,
        # timeframe, and duplicate indicators survive (validation reset,
        # 2026-10-19 — the old dict collapsed them and dropped timeframes).
        template = load_screen_template(request.template)
        
        config = BacktestConfig(
            symbol=request.symbols[0],  # Primary symbol
            timeframe=request.timeframe,
            start_date=request.start,
            end_date=request.end,
            initial_cash=request.initial_cash,
            fees_bps=request.fees_bps,
            slippage_bps=request.slippage_bps,
            position_sizing=request.position_sizing,
            sizing_params=request.sizing_params,
            signal_filters=list(template.filters),
            direction=getattr(template, "direction", "long"),
            stop_atr_mult=request.stop_atr_mult,
            target_atr_mult=request.target_atr_mult,
            max_hold_bars=request.max_hold_bars,
        )
        
        fetcher = OHLCVFetcher()
        engine = ExternalBacktestEngine(fetcher=fetcher)
        
        # Run backtest for each symbol and aggregate
        all_results = []
        all_trades = []
        all_equity = []
        
        for symbol in request.symbols:
            config.symbol = symbol
            result = await engine.run_backtest(config)
            
            if result.error:
                continue
                
            all_results.append({
                "symbol": symbol,
                "total_return": result.total_return,
                "annualized_return": result.annualized_return,
                "sharpe": result.sharpe_ratio,
                "sortino": result.sortino_ratio,
                "max_dd_pct": result.max_drawdown_pct,
                "win_rate": result.win_rate,
                "profit_factor": result.profit_factor,
                "expectancy": result.expectancy,
                "total_trades": result.total_trades,
            })
            
            # Collect trades
            for trade in result.trades:
                all_trades.append(ExternalBacktestTrade(
                    trade_id=trade["trade_id"],
                    entry_date=trade["entry_date"],
                    exit_date=trade["exit_date"],
                    entry_price=trade["entry_price"],
                    exit_price=trade["exit_price"],
                    units=trade["units"],
                    pnl=trade["pnl"],
                    return_pct=trade["return_pct"],
                    hold_days=trade["hold_days"],
                ))
            
            # Collect equity curve
            for point in result.equity_curve:
                all_equity.append({"date": point["date"], "equity": point["equity"]})
        
        # Aggregate metrics across symbols
        if all_results:
            avg_return = sum(r["total_return"] for r in all_results) / len(all_results)
            avg_sharpe = sum(r["sharpe"] for r in all_results) / len(all_results)
            avg_win_rate = sum(r["win_rate"] for r in all_results) / len(all_results)
            avg_pf = sum(r["profit_factor"] for r in all_results) / len(all_results)
            avg_expectancy = sum(r["expectancy"] for r in all_results) / len(all_results)
            total_trades = sum(r["total_trades"] for r in all_results)
            avg_hold_days = sum(r.get("avg_hold_days", 0) for r in all_results) / len(all_results)
        else:
            avg_return = avg_sharpe = avg_win_rate = avg_pf = avg_expectancy = total_trades = avg_hold_days = 0
        
        return ExternalBacktestResponse(
            run_id=str(uuid.uuid4()),
            template=request.template,
            symbol=request.symbols[0],
            timeframe=request.timeframe,
            metrics={
                "total_return": avg_return * 100,
                "annualized_return": sum(r["annualized_return"] for r in all_results) / len(all_results) * 100 if all_results else 0,
                "sharpe_ratio": avg_sharpe,
                "sortino_ratio": sum(r["sortino"] for r in all_results) / len(all_results) if all_results else 0,
                "max_drawdown_pct": sum(r["max_dd_pct"] for r in all_results) / len(all_results) if all_results else 0,
                "win_rate": avg_win_rate,
                "profit_factor": avg_pf,
                "expectancy": avg_expectancy,
                "total_trades": total_trades,
                "avg_hold_days": avg_hold_days,
            },
            trades=all_trades,
            equity_curve=[{"date": p["date"], "equity": p["equity"]} for p in all_equity],
            duration_ms=0,  # TODO: track duration
        )
        
    except Exception as e:
        log.exception("external_backtest_failed", template=request.template, error=str(e))
        raise HTTPException(status_code=500, detail=f"External backtest failed: {str(e)}")


# =========================================================================
# Helper
# =========================================================================


