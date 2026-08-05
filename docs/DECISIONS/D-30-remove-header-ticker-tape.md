# D-30: Remove Header TickerTape Component

**Status:** Accepted
**Date:** 2026-08-04

## Context

After launching Docker, the UI would not load. Root-cause chain traced entirely to the **TickerTape** header component (added in D-29 as the "signature element"):

1. `TickerTape.tsx` had a duplicated declaration block appended at the end → esbuild "duplicate top-level declarations" error → Vite never served the app.
2. Once compiling, the tape's `GET /api/v1/data/prices` was shadowed by the earlier `GET /data/{symbol}` catch-all route → returned empty candle payload.
3. The batch endpoint's `response_model` disagreed with the actual `ApiResponse` envelope → `ResponseValidationError` (500).
4. The endpoint could return a tick with missing price → `formatPrice().toFixed()` threw → React crash, repeated every 5s poll.
5. A separate pre-existing defect: `ws/manager.py::close_all()` lazily imported an alert-engine module (`screener.alerts`) that was never built (Phase 6 still planned) → `ModuleNotFoundError` on every reload/shutdown.

The tape polled `/api/v1/data/prices` every 5s, each request firing **24 individual Yahoo Finance calls** (one per symbol, uncached) — heavy external load for a purely decorative strip that core features never depended on.

## Decision

Consulted the user (the tape is cosmetic; core features are independent of it). **User chose: remove it entirely.** Concretely:

- Delete `frontend/src/components/layout/TickerTape.tsx` and all its references (`AppShell`, `tailwind.config.ts` tape-scroll animation, `index.css` `.tape-item`).
- Remove the now-orphaned `GET /api/v1/data/prices` batch endpoint from `backend/app/api/routers/data.py` (created solely for the tape; no remaining consumer). Keep the `/{symbol}` catch-all OHLCV route.
- Guard the missing `alert_engine` import in `ws/manager.py::close_all()` with `try/except ImportError` so shutdown/reload stops crashing.

## Consequences

- **Good:** Removes ~24 external Yahoo calls/min of gratuitous load; eliminates 4 bug classes (duplicate decl → compile, route shadowing, response validation, React crash); no visual loss to core product; shutdown no longer crashes on an unbuilt Phase 6 module.
- **Trade-off:** The header no longer shows a live price strip / "Live" badge — a blot on the D-29 "signature element" goal. Revisit only with a lightweight streaming source (existing `price:*` WebSocket channels are available), not per-symbol Yahoo polling.
- **Risk:** Low. Verified end-to-end: dashboard + `/pro` render with **0 console errors**, WebSocket Connected, Market Regime/VIX/Sector Rotation/Events all load, `GET /data/{symbol}` OHLCV confirmed.
- **Supersedes:** The "live ticker tape" element described in D-29 is now removed; D-29's palette/type/logo/responsive decisions stand unchanged.