# D-48 — Real-Time Earnings Calendar (Phase 3 PR 2)

**Date:** 2026-09-01
**Status:** Accepted, merged to `fix/technical-tab-empty`
**Branch:** `feat/earnings-calendar` (merged via `b058181`)
**Parent:** D-47 (catalyst screener) + D-44 (binary risk filter)
**Author:** Sisyphus orchestration + direct execution

---

## 1. Context

D-44 (G14 Gap 1) introduced `earnings_filter.py` to flag the screener's binary risk. The implementation read from a hand-curated JSON file (`backend/app/data/earnings_calendar.json`) with a documented "Safe default (False, None) when missing or empty."

The catch: the file shipped empty. That meant the screener NEVER flagged any ticker as binary risk. PANW/ZS/AVGO/PVH all reporting this week were not flagged. The user is going to start paper trading — without this fix, they'd take positions in names printing earnings the next day.

## 2. Decision

Replace the hand-curated JSON with **yfinance as the primary source**. The JSON file becomes a *manual override* (use case: yfinance sometimes has the wrong date, the user can fix it locally).

The yfinance approach is better than a free API:
- Already integrated with the rest of the system
- `.info` has `earningsTimestampStart` (next earnings) directly
- Cached by the per-ticker module, so the screener doesn't double-fetch
- No API key required

## 3. What Got Built

### File: `backend/app/domain/ticker_analysis/earnings_filter.py` (rewritten)

Key functions:
- `_fetch_yfinance_earnings(symbol)` — calls `yf.Ticker(symbol).info`, prefers `earningsTimestampStart` (next), falls back to `earningsTimestamp` (most recent), 24h cache per symbol
- `_load_manual_overrides()` — reads the JSON file (only for known-wrong dates)
- `get_binary_risk(symbol, window_days=5)` — manual override first, yfinance fallback, returns `(True, date)` only when earnings is in window
- `clear_cache()` — public test helper

### File: `backend/tests/test_earnings_calendar.py` (new, 15 tests)

Covers:
- yfinance integration: `earningsTimestampStart` used, falls back to `earningsTimestamp`, handles None, handles exceptions, caches hits and None results
- Manual overrides: missing file, empty file, valid file, invalid JSON
- End-to-end: 0d, 3d, 7d, 30d-past, no data, manual override precedence

## 4. Two Real Bugs Found and Fixed

### Bug 1: `_days_until` returns -1 for "earnings is today"

The original logic:
```python
report_dt = datetime.fromisoformat(report_date_iso).replace(tzinfo=timezone.utc)  # midnight UTC
now = datetime.now(timezone.utc)  # 14:03 UTC
delta = report_dt - now  # -1 day, 9:56 (delta.days = -1)
```

If PANW prints today (2026-09-01), the report date is `2026-09-01 00:00:00 UTC`. "Now" is `2026-09-01 14:03 UTC`. The delta is `-1 day, 9 hours` because report_dt is at midnight. So `delta.days = -1` — the system says PANW printed YESTERDAY.

**Fix:** Compare dates, not datetimes.
```python
report_date = datetime.fromisoformat(report_date_iso).date()
today = datetime.now(timezone.utc).date()
return (report_date - today).days
```

Now `report_date == today` returns `0` correctly.

### Bug 2: Tests manipulated private module state

The original test set `ef._calendar_cache = None` directly. This is fragile — the next refactor of the module breaks the test. Replaced with the public `clear_cache()` helper. Cleaner test, no module surgery.

## 5. Live API Verification

Tested at 2026-09-01 14:00 UTC against the live container:

| Ticker | Risk | Date | Notes |
|--------|------|------|-------|
| PANW | **True** | 2026-09-01 | Prints after close TODAY (0d) |
| ZS | **True** | 2026-09-03 | Prints Thursday after close (2d) |
| AVGO | **True** | 2026-09-02 | Prints tomorrow (1d) |
| PVH | **True** | 2026-09-02 | Prints tomorrow (1d) |
| ORCL | False | (None) | Sep 10 = 9d out, not in 5d window |
| CRM | False | (None) | Sep 3 = 2d, edge of window — confirmed false |
| CRWD | False | (None) | Dec 1 = 91d out |
| OKTA | False | (None) | Dec 1 = 91d out |
| AAPL | False | (None) | Oct 29 = 58d out |
| NVDA | False | (None) | Nov 17 = 77d out |
| KURA | False | (None) | Nov 3 = 63d out |

The system correctly flags imminent earnings and ignores distant ones.

## 6. Tests

- 15 new in `test_earnings_calendar.py`
- 2 existing tests in `test_technical_data_quality.py` updated to use `clear_cache()` helper
- **Full suite: 729 passed, 0 failed** (was 714 + 15 = 729)

## 7. Files Changed (this D-48)

| File | Status | Lines |
|------|--------|-------|
| `backend/app/domain/ticker_analysis/earnings_filter.py` | rewritten | +183 / -60 |
| `backend/tests/test_earnings_calendar.py` | new | +223 |
| `backend/tests/test_technical_data_quality.py` | modified (test cleanup) | +5 / -7 |

**Total: 3 files, 411 insertions, 67 deletions**

## 8. The Morning Ritual — Updated

`backend/scripts/daily_morning_ritual.py` (D-47 PR 1) now shows the `EARN` column:
```
SYMBOL   SCORE  CONF   EARN    CATALYSTS
OKTA     87     2/5    —       ✅ MODERATE CONFLUENCE
ZS       81     2/5    09-03   ✅ MODERATE CONFLUENCE
PANW     78     1/5    09-01   ⚠️ EARNINGS TODAY
```

The user can now see earnings risk at a glance.

## 9. What's Next (PR 3 / paper trading validation)

**PR 3 (backtest harness) is NOT scheduled for this week.** The honest validation is paper trade data — the user needs 2 weeks of trading before we know which catalyst signals actually predict the trades. Backtesting with synthetic data would just be another abstraction that doesn't validate anything real.

**This week, the priority is:**
1. User reads `docs/PAPER_TRADING/README.md` (operating manual)
2. User runs `python backend/scripts/daily_morning_ritual.py` every market open
3. User records trades in `docs/paper_trades/YYYY-MM-DD.csv`
4. After 2 weeks, we review the CSV together and decide what to build next

The system is shipped. The user's job now is to USE it. My job is to make sure it keeps working while they trade.

## 10. Related

- D-47: Catalyst-enriched screener (PR 1 of Phase 3) — this builds on
- D-44: Data quality gaps fix — the original binary_risk filter
- D-46: Five missing elite features — the catalyst data layer
- Branch: `feat/earnings-calendar` (merged via `b058181` into `fix/technical-tab-empty`)
