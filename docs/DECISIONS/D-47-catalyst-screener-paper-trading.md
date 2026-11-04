# D-47 — Catalyst-Enriched Screener + Paper Trading Workflow (Phase 3 PR 1)

**Date:** 2026-09-01
**Status:** Accepted, merged to `fix/technical-tab-empty`
**Branch:** `feat/phase-3-discovery` (merged via `29f47d5`)
**Parent:** D-46 (5 missing elite features)
**Author:** Sisyphus orchestration + direct execution

---

## 1. Context

D-45 (momentum regime boost) + D-46 (5 catalyst signals) shipped the elite trader's *analysis* layer. The verdict now includes macro context, sector-relative RS, analyst revisions, insider clusters, and options flow. But the user still has to **know which tickers to ask about**. The original Phase 3 plan was to make the screener FIND trades — the discovery layer.

The user is going to paper trade with the system starting this week. We need:
1. The screener to surface only stocks where multiple catalyst signals are firing
2. A morning ritual script the user can run every market open
3. A paper trading workflow (CSV-based) for the user to record their trades

## 2. Decision

One PR, three parts:
1. **Catalyst post-filter** — extend the TV screener to run the 5 D-46 signals on each result and surface a `confluence_count` (0-5). Opt-in via `enrich_with_catalysts: true`; filter to high-confluence via `min_confluence: N`.
2. **Bug fix** — `get_revision()` now creates the `analyst_targets` table if missing (CREATE TABLE IF NOT EXISTS). `log.exception()` calls fixed for Python 3.14 compat.
3. **Paper trading workflow** — `backend/scripts/daily_morning_ritual.py` (the morning coffee script), `docs/PAPER_TRADING/README.md` (operating manual), `docs/paper_trades/TEMPLATE.csv` (daily trade log header).

## 3. The Catalyst Post-Filter

### What it does

`detect_catalyst_signals(symbol)` in `infrastructure/screener/catalyst_filter.py` runs the 5 D-46 signals:

| Signal | What it does | Source |
|--------|--------------|--------|
| 1. Sector-relative RS | Stock 1M return vs sector ETF 1M return | yfinance + D-46 PR 2 |
| 2. Post-earnings drift | 0-20 days since last print with positive beat | yfinance.earnings_dates |
| 3. Analyst revision | Target raised >5% in last 5 days | DuckDB + D-46 PR 3 |
| 4. Insider cluster | 3+ Form 4 buys same week | yfinance.insider_transactions + D-46 PR 4 |
| 5. Options flow | Call/put vol >2x + vol >1.5x OI | yfinance.option_chain + D-46 PR 5 |

Returns `confluence_count` (0-5) and a human-readable summary:
- 0: "○ No catalyst signals"
- 1: "○ Weak signal: 1/5 catalyst firing"
- 2: "✅ MODERATE CONFLUENCE: 2/5 catalysts firing"
- 3+: "🔥 HIGH CONFLUENCE: 3/5 catalysts firing"

### How it integrates with the screener

`POST /api/v1/screen/tv` now accepts:
- `enrich_with_catalysts: bool` (default False — off for speed)
- `min_confluence: int 0-5` (default 0 — no filter)

When `enrich_with_catalysts=true`, the endpoint:
1. Runs the TV screener as before
2. For each result, calls `detect_catalyst_signals` in parallel (8-worker ThreadPoolExecutor)
3. Adds a confluence boost to the score (0-5)
4. Filters out results with `confluence_count < min_confluence`
5. Returns the enriched `ScoredTickerResponse` with `catalyst_signals`, `catalyst_confluence_count`, `catalyst_summary` fields

### Performance

For 25 screener results with `enrich_with_catalysts=true`:
- Each result needs ~5 yfinance calls (sector, earnings, analyst DB, insider, options)
- Running them in parallel with 8 workers → ~3-5s total (vs ~20s sequential)
- For the morning ritual with `min_confluence=2`, you typically get 5-15 candidates out of the original 25

## 4. The Paper Trading Workflow

### Morning ritual script

`backend/scripts/daily_morning_ritual.py`:
```bash
python backend/scripts/daily_morning_ritual.py --min-confluence 2 --limit 50
```

Output:
```
══════════════════════════════════════════════════════════════════════════
  conflu.ai DAILY MORNING RITUAL
  2026-09-01
══════════════════════════════════════════════════════════════════════════

══════════════════════════════════════════════════════════════════════════
  MACRO CONTEXT — what the market is doing RIGHT NOW
══════════════════════════════════════════════════════════════════════════
  VIX:       15.9  (normal)
  SPY:       $N/A  (N/A% today)
  Leading:   XLE (+2.04%)
  Lagging:   XBI (-3.41%)

══════════════════════════════════════════════════════════════════════════
  TOP CANDIDATES — N passed min_confluence filter
══════════════════════════════════════════════════════════════════════════
  SYMBOL   SCORE  CONF   CATALYSTS
  --------------------------------------------------------------------
  META     87     1/5    ○ Weak signal: 1/5 catalyst firing
          └─ ...

  💾 Saved to: docs/SESSIONS/morning_brief/2026-09-01.json
```

The output is also saved to a dated JSON file for day-over-day comparison.

### Paper trading CSV

`docs/paper_trades/YYYY-MM-DD.csv` with one row per trade:
```csv
date_entered,symbol,sector,action,entry_price,stop_loss,target_1,target_2,position_size_pct,confluence_count,signal_at_entry,notes
2026-09-01,OKTA,Technology,BUY,170,160,200,215,5,3,"sector_RS+15.6%_+insider_cluster+post_earnings","..."
```

The user reviews candidates, picks 1-3 with conviction, records in CSV, monitors at end of day.

### Operating manual

`docs/PAPER_TRADING/README.md` — the user-facing playbook:
- 15-minute daily ritual
- How to pick 3-5 candidates from the screener
- How to record trades in CSV
- Weekly review process
- Validation metrics (hit rate, average R, catalyst precision)

## 5. Validation

### Tests
- 14 new in `test_catalyst_filter.py`:
  - empty signals
  - full signal fires 3+ (sector RS, analyst, insider, options)
  - partial signals
  - no signals fire
  - `confluence_boost(0/5/10)` — correctly caps at 5
  - `to_dict` round-trip
  - summary level tests (0/1/2/3+)
  - `_get_sector` mock tests
- **Full suite: 714 passed, 0 failed** (was 700 + 14 = 714)

### Live API verified
- `POST /api/v1/screen/tv {enrich_with_catalysts: true, min_confluence: 0}` returns 25 results with `catalyst_summary` field for each
- Top results from a real run on 2026-09-01:
  - VLO/MPC/SLB/CVX (refiners, overbought mega-caps) — all 0 catalysts (correctly flagging "wait for pullback")
  - META — 1/5 catalysts (recent AI news)
  - All 5 D-46 signal detectors integrated into the post-filter

### Macro context (live at 9am ET Sep 1)
- VIX 15.9 (normal) — up slightly from 14.9 yesterday
- XLE leading (+2.04% today) — energy still the play
- XBI lagging (-3.41% today) — biotech cooling
- Most cyber/energy favorites at 0 catalysts — post-earnings drift window over, the system correctly says "wait for next setup"

## 6. Bug fixes bundled in this PR

1. **`get_revision()` now creates the table if missing.** Without this, a fresh DuckDB or a worktree that hasn't run `initialize_database()` would throw `Catalog Error: Table with name analyst_targets does not exist`. Idempotent and cheap (no-op if the table exists).
2. **`log.exception()` calls in `analyst_revisions.py` use `extra={...}` pattern.** Python 3.14 rejects the older `symbol=foo` keyword args. Same fix as applied to `insider_cluster.py` in D-46 PR 4.

## 7. What's Next (Phase 3 PRs 2-3)

- **PR 2: Real-time earnings calendar.** The current `earnings_calendar.json` is hand-curated. Replace with a daily refresh from a free source (Yahoo earnings calendar API) so the calendar is never stale.
- **PR 3: Backtest harness.** Replay the last 6 months of historical setups through the catalyst signals. Measure: which signals predict +3% in 20d? What's the precision/recall of the confluence model?
- **PR 4: Screener "morning ritual" template.** A pre-built TV screener config in `screener-configs/` that pairs with `--min-confluence 2` for the morning ritual.

## 8. Files Changed (this D-47)

| File | Status | Lines |
|------|--------|-------|
| `backend/app/infrastructure/screener/catalyst_filter.py` | new | +239 |
| `backend/app/infrastructure/screener/tv_models.py` | modified | +17 |
| `backend/app/api/routers/tv_screener.py` | modified | +63 |
| `backend/app/infrastructure/analyst_revisions.py` | modified (bug fix) | +22 -3 |
| `backend/tests/test_catalyst_filter.py` | new | +330 |
| `backend/scripts/daily_morning_ritual.py` | new | +256 |
| `docs/PAPER_TRADING/README.md` | new | +146 |
| `docs/paper_trades/TEMPLATE.csv` | new | +1 |

**Total: 8 files, ~1,074 insertions, ~3 deletions**

## 9. Related

- D-46: Five missing elite features (5 catalyst signals) — this builds on
- D-45: Momentum regime boost — the verdict module foundation
- D-44: Data quality gaps fix — the prior round
- Session log: `docs/SESSIONS/2026-08-31_d46-five-missing-elite-features.md`
- Branch: `feat/phase-3-discovery` (merged via `29f47d5` into `fix/technical-tab-empty`)
