# D-27: Professional Mode Backend Architecture

**Status:** Accepted
**Date:** 2026-07-26

## Context

The app has 80% of its engine complete (screener, deep analysis, backtest, risk) but no workflow layer for working professionals with zero market knowledge. Phase 8 introduces a "Professional Mode" that sits on top of existing features.

## Decision

### Service Architecture
Create 5 single-responsibility services under `backend/app/infrastructure/professional/`:

| Service | Responsibility |
|---------|---------------|
| `MorningBriefService` | Daily brief generation (regime→screens→sectors→pre-market) |
| `RegimeScreenSelector` | Heuristic scoring of 21 screens against current regime |
| `PositionSizer` | Conviction-adjusted Kelly sizing with hard caps |
| `EducationService` | 20 metric static templates + optional LLM enhancement |
| `AlertService` | In-app alert queue + simulated email dispatch |

### Design Principles
1. **Constructor injection**: All services accept dependencies optionally, with sensible defaults
2. **Typed models**: All inputs/outputs use Pydantic BaseModel with `extra="forbid"`
3. **No database dependency**: Alert preferences in memory, templates hardcoded
4. **Graceful degradation**: Screen failures skip, pre-market failures use close prices
5. **Parallel execution**: Morning brief runs 3 screens concurrently via `asyncio.gather`

### Formula: Position Sizing
Per CONTEXT.md, using conviction-adjusted Kelly Criterion:

```
risk_per_share = abs(entry - stop_loss)
risk_dollars = equity × risk_per_trade_pct × conviction_multiplier
kelly_shares = risk_dollars / risk_per_share
kelly_dollars = kelly_shares × entry
position_size = min(kelly_dollars, position_cap, sector_cap)
```

Conviction multipliers: high=1.0, medium=0.67, low=0.33. Hard caps: 5% position, 15% sector.

### Fallback Screen Selection
When no screen YAML has a `regime` field, use hardcoded map:
- `strong_trend` → [Trend Follower, Institutional Trend Follower MTF, Trend Leader]
- `ranging` → [Mean Reversion, Low-Vol Setup, Statistical Mean Reversion]
- `high_vol` → [Volatility Expansion, Volume Surge Breakout, Breakout]

### API Registration
All endpoints under `/api/v1/professional/` with optional API key auth. 8 endpoints registered.

## Consequences

### Positive
- Clean separation of concerns (each service has one job)
- All existing features remain untouched (no breaking changes)
- Morning brief loads in ~2s with 3 parallel screen runs
- Education works offline (static templates, no API calls)

### Risks
- RegimeScreenSelector heuristic weights (40/25/20/15) not validated against historical data yet
- AlertService does not implement real email/WebSocket dispatch (logging fallback only)
- MorningBriefService fetches market data via yfinance at request time (adds latency)
- Screen YAMLs don't have `regime` field yet — always hits fallback

### Next Steps
- Wave 2: Frontend components (Morning Brief dashboard, Verdict page, Watchlist builder)
- Wave 3: Education content expansion + inline tooltips
- Add `regime` field to screen YAMLs for proper heuristic scoring
