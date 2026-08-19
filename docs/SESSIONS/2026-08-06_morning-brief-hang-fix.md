# Session: /pro Morning Brief Hang & Excessive API Calls — Fix

**Date**: 2026-08-06
**Branch**: fix/morning-pro-load-and-blocking
**Type**: Bug fix (performance regression — /pro page hangs, many API calls)

## Context

User reported `/pro` used to load in seconds but now the UI hangs and fires
many API calls. Investigation (GitNexus + git history) traced the fault to the
**backend** `GET /api/v1/professional/morning-brief` endpoint, not the frontend:

- The `/pro` page (MorningBriefPage) itself fires a single React Query request.
- That endpoint **regenerates the entire Morning Brief on every page load, with
  no caching**, fanning out ~50 blocking yfinance/TV calls.
- All yfinance calls are synchronous code inside async functions → they freeze
  the asyncio event loop, so the brief takes 30-60s+, the UI's 30s axios timeout
  fires, react-query retries 2×, and the header's RegimeBar/WebSocket queue
  behind it → "many API calls" + hung UI.

## Root Cause (what broke it)

- Commit `e2713bc` (Jul 28) replaced the 4th sector screen from a **parallel TV
  scan** (`screens = [*screens, sector_screen]`, ran inside `asyncio.gather`) into
  a **serial loop of up to 15 blocking `yf.Ticker().history()` calls** (`_score_holdings`).
- Combined with pre-existing un-offloaded blocking loops in regime detection,
  sector rotation, and market internals — and **no caching** — every page load
  re-ran the full heavy pipeline with a frozen event loop.
- `20bf95c` (Aug 4, "fix event-loop bug") only patched the regime *router*; the
  brief's own blocking calls were never fixed.
- Note: the user clarified the APScheduler cron is **not** required for /pro —
  the page calls the endpoint directly. No scheduler dependency in the fix.

## Changes (2 files)

- `backend/app/infrastructure/professional/morning_brief.py`:
  - Added 6h TTL cache (`_BRIEF_CACHE_TTL`) in `MorningBriefService`, guarded by
    `asyncio.Lock`; `generate_morning_brief(..., force=False)` serves cached brief.
  - Offloaded all blocking yfinance to `asyncio.to_thread` with bounded
    concurrency: `_detect_regime`, `_score_holdings` (`_HOLDING_CONCURRENCY=4`),
    `_fetch_sector_rotation` (`_SECTOR_CONCURRENCY=4`), `_fetch_market_internals`,
    `_fetch_premarket_quotes`. Extracted sync helpers: `_score_holding_sync`,
    `_sector_changes_sync`, `_index_last_close_sync`, `_sector_direction_sync`,
    `_premarket_quotes_sync`.
- `backend/tests/integration/test_professional_mode.py`:
  - Fixed pre-existing failure — `_fetch_sector_rotation` mock returned a 2-tuple
    while production returns 3 (weekly leader) since `e2713bc`; added `"XLK"`.

## Verification

- `lsp_diagnostics` clean on `morning_brief.py` and the test.
- `python -m pytest backend/tests/integration/test_professional_mode.py` → **12 passed**.
- Impact analysis: LOW risk; only 2 callers (API router + scheduler cron), 1 module.
- Pending: real browser check on branch (page should now serve cached brief in ms).

## Notes

- Decision record: `docs/DECISIONS/D-31-morning-brief-caching.md`
- Pre-existing LSP noise (unrelated files): `pandas_ta` attrs in `data.py`,
  `prometheus_client` / `screener.alerts` import in `ws/manager.py`.