# Session: Docker UI Not Loading — Fix & Verification

**Date**: 2026-08-04
**Branch**: fix/elite-trader-gaps
**Type**: Bug fix (UI would not compile/load in Docker)

## Context

User launched Docker (`conflu-frontend`, `conflu-api`, `conflu-redis`) and the UI would not load. Diagnosis found a chain of issues, all traced back to the **TickerTape** header component and a route-ordering bug it exposed.

## Root Cause Chain

1. **Frontend compile failure** — `frontend/src/components/layout/TickerTape.tsx` had a duplicated block appended at the end (lines 193–213 re-declared `TAPE_SYMBOLS`, `fetchPrices`, and `Tick` already defined at the top). esbuild failed with "duplicate top-level declarations" → Vite never served the app.
2. **Route shadowing** — once the frontend compiled, the tape's `GET /api/v1/data/prices` was shadowed by the catch-all `GET /data/{symbol}` (declared earlier in `data.py`), returning an empty candle payload instead of batch prices.
3. **Response validation mismatch** — `response_model=BatchPriceResponse` expected a top-level `{prices, meta}` shape, but the handler returns the standard `ApiResponse(data={"prices": ...}, meta)` envelope → `ResponseValidationError` (500) on every prices request.
4. **React crash** — the batch endpoint could return a tick with `price` missing/0 → `formatPrice().toFixed()` threw, crashing `<TickerTape>` (uncaught error, repeated every 5s poll).
5. **Pre-existing shutdown crash** — `ws/manager.py::close_all()` lazily imports `backend.app.infrastructure.screener.alerts` (a Phase 6 alert-engine module that was never built) → `ModuleNotFoundError` on every reload/shutdown.

## Decision: Remove the TickerTape

Consulted user (the tape is cosmetic; core features don't depend on it). **User chose: Remove entirely.**

The tape polled `/api/v1/data/prices` every 5s, each request making **24 individual Yahoo Finance calls** (one per symbol, no caching) — heavy external load for a decorative strip.

## Files Changed (6)

- `frontend/src/components/layout/TickerTape.tsx` — **deleted** (component + duplicate declarations)
- `frontend/src/components/layout/AppShell.tsx` — removed `<TickerTape />` and its import
- `frontend/tailwind.config.ts` — removed `tape-scroll` animation + keyframes
- `frontend/src/index.css` — removed unused `.tape-item` rule
- `backend/app/api/routers/data.py` — removed orphaned `GET /data/prices` batch endpoint (was only for the tape): removed `PricePoint`, `get_batch_prices`, unused `asyncio` import; verified `/{symbol}` catch-all still last and working
- `backend/app/api/ws/manager.py` — guarded `alert_engine` import with `try/except ImportError` (module doesn't exist yet; Phase 6 not built)

## Verification

- Frontend: Vite HMR applied cleanly, no esbuild errors; page loads at `/dashboard` and `/pro`, **0 console errors**
- Dashboard data: Market Regime (Neutral 60/100), VIX 16.5, Sector Rotation, Upcoming Events all load; WebSocket shows **Connected**
- API: `/health` returns ok; `GET /api/v1/data/AAPL?timeframe=1D` returns valid candle data (route ordering verified)
- Remaining console warnings: 2× React Router v7 future-flag notices (benign), 1× initial WS connect warning (reconnects; now Connected)
- Pre-existing LSP noise only: `pandas_ta` dynamic attributes (`rsi`, `macd`, …) and `prometheus_client` not installed in dev image — unrelated to these changes

## Notes

- `pytest` is not installed in the runtime Docker image (`conflu-api`), so backend tests were not run inside the container this session.
- The `GET /api/v1/data/prices` endpoint was removed — no frontend/backend consumer remains. See D-30 for the decision record.
