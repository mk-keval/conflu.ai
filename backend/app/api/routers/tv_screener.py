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
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.infrastructure.screener.tv_engine import TVScreenEngine
from backend.app.infrastructure.screener.tv_models import (
    TVScreenRequest,
    TVScreenResponse,
    ScoredTickerResponse,
    EliteEnrichment,
    DeepAnalysisRequest,
    DeepAnalysisResponse,
    dict_to_screen_config,
)
from backend.app.infrastructure.screener.configs import (
    ScreenConfig,
    load_screen_template,
    list_screen_templates,
)
from backend.app.core.logging import get_logger

log = get_logger("conflu.api.tv_screener")

router = APIRouter(prefix="/screen/tv", tags=["tv-screener"])


# =========================================================================
# Dependency
# =========================================================================
def get_tv_engine() -> TVScreenEngine:
    return TVScreenEngine()


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


def _build_scored_response(scored: list[dict]) -> list[ScoredTickerResponse]:
    """Build typed response from scored tickers (includes elite enrichment)."""
    return [
        ScoredTickerResponse(
            symbol=r["symbol"],
            score=r["confluence"].total,
            breakdown=r["confluence"].breakdown,
            entry=r["confluence"].entry,
            stop_loss=r["confluence"].stop_loss,
            targets=r["confluence"].targets,
            risk_reward=r["confluence"].risk_reward,
            rating=r["confluence"].rating,
            rationale=r["confluence"].rationale,
            tv_data=r["tv_data"],
            elite=EliteEnrichment(**r.get("elite", {})) if r.get("elite") else None,
        )
        for r in scored
    ]


@router.post("", response_model=TVScreenResponse)
async def screen_tv(
    request: TVScreenRequest,
    engine: TVScreenEngine = Depends(lambda: TVScreenEngine()),
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

    engine = TVScreenEngine()

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
        results=_build_scored_response(result["results"]),
    )


@router.post("/multi-tf", response_model=dict[str, Any])
async def screen_tv_multi_tf(
    request: TVScreenRequest,
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

    engine = TVScreenEngine()
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
) -> dict[str, Any]:
    """
    Stage 3: On-demand deep analysis for a single ticker.
    Fetches OHLCV, computes indicators, runs backtest, risk.
    """
    start = time.monotonic()

    try:
        engine = TVScreenEngine()
        result = await engine.deep_analyze(
            request.symbol,
            request.timeframe,
            tv_data=request.tv_data,
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


