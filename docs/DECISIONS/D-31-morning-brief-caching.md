# D-31: Morning Brief Caching & Non-Blocking yfinance Fetches

**Status:** Accepted
**Date:** 2026-08-06

## Context

The `/pro` page (MorningBriefPage) regressed from "loads within seconds" to
"UI hangs + many API calls". Root-cause chain traced to the backend
`GET /api/v1/professional/morning-brief` endpoint, not the frontend:

1. The endpoint regenerates the **entire Morning Brief from scratch on every page
   load** — there was no caching.
2. That single `generate_morning_brief()` fans out to **~50 blocking external
   calls**: `_detect_regime` (6 macro + 11 sector yfinance), `_fetch_sector_rotation`
   (11 sequential), `_score_holdings` (up to 15 sequential — the 4th sector screen
   added in `e2713bc`), `_fetch_market_internals` (4 indexes + 11 sectors),
   `_fetch_premarket_quotes` (9).
3. Every `yf.Ticker(...).history()` is **synchronous code inside an async
   function** → it blocks the entire asyncio event loop. While the brief
   regenerates, the UI's 30s axios timeout fires, react-query retries 2×, and
   the header's global RegimeBar + WebSocket reconnect stack behind the frozen
   loop — the "many API calls" and the hung UI.

Same disease class as D-30's TickerTape (24 uncached Yahoo calls/min), but at
larger scale and on a *core* page rather than a decorative strip.

## Decision

Fix the backend only (no frontend changes). Two coordinated changes in
`backend/app/infrastructure/professional/morning_brief.py`:

1. **TTL cache the generated brief.** `MorningBriefService` now stores the last
   generated `MorningBriefResponse` with a 6h TTL (`_BRIEF_CACHE_TTL`), guarded by
   an `asyncio.Lock`. Repeated page loads (and the header's concurrent regime/WS
   traffic) get the cached brief instead of re-running the ~50-call pipeline.
   `generate_morning_brief(regime_override=None, force=False)` — `force` bypasses
   cache; the 6AM scheduler cron (unchanged signature) continues to work and can
   force a fresh generation when needed.

2. **Offload every blocking yfinance call.** The previously-serial synchronous
   loops now run inside `asyncio.to_thread` with bounded concurrency, so they
   no longer freeze the event loop during a (now rare) cold generation:
   - `_detect_regime` → `asyncio.to_thread`
   - `_score_holdings` → per-symbol `_score_holding_sync` in threads, semaphore
     `_HOLDING_CONCURRENCY=4` (was 15 serial round-trips)
   - `_fetch_sector_rotation` → `_sector_changes_sync` in threads, `_SECTOR_CONCURRENCY=4`
   - `_fetch_market_internals` → `_index_last_close_sync` + `_sector_direction_sync` in threads
   - `_fetch_premarket_quotes` → `_premarket_quotes_sync` in one thread

## Consequences

- **Good:** Page loads after the first now return the cached brief in ms;
  the event loop stays responsive during the cold generation. Cold-cache
  generation is faster (parallel threads vs serial). No frontend change; the
  scheduler caller is untouched (its `generate_morning_brief()` call is compatible
  with the new optional `force` param).
- **Trade-off:** The brief can be up to 6h stale between forced regenerations.
  This mirrors the existing 6h regime cache and is acceptable for a daily
  swing-trading artifact; `force=True` is available if a fresh generation is
  ever required out of band.
- **Risk:** Low. Only 2 callers (API router + scheduler), 1 module. All 12
  `test_professional_mode.py` integration tests pass. `lsp_diagnostics` clean on
  the changed files.
- **Also fixed while here:** `test_professional_mode.py::test_morning_brief_generation_mock_regime`
  was a pre-existing failure — its `_fetch_sector_rotation` mock returned a
  2-tuple while production returns 3 (since `e2713bc`). Added the missing
  `weekly_leader_etf` element.