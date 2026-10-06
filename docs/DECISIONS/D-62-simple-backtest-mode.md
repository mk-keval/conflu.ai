# D-62: Simple Backtest Mode for Filter Sweep Page

**Date**: 2026-09-26
**Status**: Implemented
**Branch**: `fix/technical-tab-empty`

## Summary

Added a "Simple Backtest" mode to the Filter Sweep page that allows users to run single backtests with any template, custom date ranges, and custom ticker symbols — complementing the existing Parameter Sweep mode.

## Features Added

### 1. Simple Backtest API (`frontend/src/api/backtest.ts`)
- **`runSimpleBacktest(request)`** — Runs a single backtest using the existing `/api/v1/backtest` endpoint
- **Loads template automatically** — Fetches template via `fetchTVTemplate()` to extract `signal_params`
- **Transforms response** — Normalizes backend metrics to consistent format
- **Type-safe** — Full TypeScript support with proper `Record<string, unknown>` handling

### 2. SimpleBacktestForm Component (`frontend/src/components/backtest/SimpleBacktestForm.tsx`)
- **Template selector** — Dropdown with all 19 available templates (loaded from API)
- **Custom symbols** — Comma-separated ticker input (e.g., "AAPL,MSFT,GOOGL")
- **Date range picker** — Start/end date inputs with validation
- **Timeframe selector** — 1D, 4h, 1h, 1W
- **Advanced settings** — Initial cash, fees/slippage (bps), position sizing (Fixed/ATR/Kelly)
- **Loading states** — Template loading spinner, submit disabled during backtest
- **Error handling** — Inline error display

### 3. SimpleBacktestResults Component (`frontend/src/components/backtest/SimpleBacktestResults.tsx`)
- **Metrics dashboard** — 10 metric cards (Total Return, Annualized Return, Sharpe, Sortino, Max DD, Win Rate, Profit Factor, Expectancy, Total Trades, Avg Hold)
- **Color-coded metrics** — Green for good values, red for concerning values
- **Trade table** — Expandable/collapsible trade list with P&L, return %, hold days
- **Equity curve chart** — SVG-based area chart with zero-line reference
- **Export/Run again buttons** — Quick actions after backtest completes

### 4. FilterSweepPage Integration (`frontend/src/components/backtest/FilterSweepPage.tsx`)
- **Mode toggle** — Switch between "Parameter Sweep" and "Simple Backtest"
- **Preserves existing sweep functionality** — No breaking changes
- **Independent state** — Each mode maintains its own form/results state
- **Shared header** — Consistent UI with beta badge

## API Changes

### Frontend (`frontend/src/api/backtest.ts`)
```typescript
// New types
interface SimpleBacktestRequest {
  template: string;
  symbols: string[];
  start: string;
  end: string;
  timeframe: string;
  initial_cash?: number;
  fees_bps?: number;
  slippage_bps?: number;
  position_sizing?: 'fixed' | 'atr' | 'kelly';
  sizing_params?: Record<string, unknown>;
}

interface SimpleBacktestResponse {
  run_id: string;
  template: string;
  symbol: string;
  timeframe: string;
  metrics: { ... };
  trades: Array<...>;
  equity_curve: Array<{ date: string; equity: number }>;
  duration_ms: number;
}

// New function
export async function runSimpleBacktest(request: SimpleBacktestRequest): Promise<SimpleBacktestResponse>
export async function fetchBacktestTemplates(): Promise<TVTemplate[]>
```

### Backend
No backend changes required — uses existing `/api/v1/backtest` endpoint with `BacktestRequest` schema.

## Verification

- ✅ TypeScript typecheck passes (`npm run typecheck`)
- ✅ Frontend build passes (`npm run build`)
- ✅ Backend screener tests pass (60/60)
- ✅ All 19 templates available via API
- ✅ No breaking changes to existing Parameter Sweep mode

## Usage

1. Navigate to Filter Sweep page
2. Click "Simple Backtest" tab
3. Select template from dropdown (all 19 templates available)
4. Enter comma-separated symbols (e.g., "AAPL,MSFT,NVDA")
5. Pick date range and timeframe
6. Optionally adjust advanced settings
7. Click "Run Backtest"
8. View results: metrics cards, trade table, equity curve

## Future Enhancements

- Add Monte Carlo simulation option
- Add walk-forward optimization toggle
- Save/load backtest configurations
- Compare multiple templates side-by-side
- Add regime filter (only run during specific market regimes)