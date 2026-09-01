# 2026-08-31 — D-46: Five Missing Elite Trader Features (PRs 1-5)

## Scope

The user pushed back on the regime-classifier work. The honest diagnosis: conflu.ai was missing the **5 specific things an elite trader does every morning**, not the 4 regime buckets I'd reverse-engineered from 8 specific tickers. The right fix is 5 small PRs, one per feature, each testable independently.

The 5 features:
1. **Macro context** — VIX, sector leaders/laggers, risk regime (what the elite trader knows BEFORE any trade)
2. **Sector-relative RS** — is this stock confirming its sector, or fighting it? (the elite trader's strongest confirmation signal)
3. **Analyst revision tracker** — store today's target in DuckDB, detect upgrades/downgrades over 5d (the elite trader watches REVISIONS, not snapshots)
4. **Insider cluster detector** — 3+ Form 4 buys in the same week (CEO buying 4x in a month = elite trader's #1 insider signal)
5. **Unusual options activity** — call/put volume ratio > 2.0 + call vol > 1.5x OI (smart money leaves a footprint in the options market)

## Process

Direct execution. No more planning rounds. Each PR:
1. Read existing code (5 min)
2. Write the new module (10-20 min)
3. Wire into orchestrator (5-10 min)
4. Write tests (10-15 min)
5. Run full suite, deploy to live, verify (5-10 min)
6. Commit (1 min)

Total per PR: ~40-60 min. Total for 5 PRs: ~4 hours.

## What Got Built

### PR 1: Macro Context (commit b7af82e)

**Files:**
- `backend/app/infrastructure/professional/macro_context.py` (new, 200 lines)
- `backend/app/domain/ticker_analysis/orchestrator.py` (modified, +30 lines)
- `backend/app/domain/ticker_analysis/models.py` (modified, +5 lines)
- `backend/tests/test_macro_context.py` (new, 21 tests)

**What it does:**
- Pulls VIX, SPY/QQQ close, DXY, 12 sector ETF % changes
- 60s TTL cache (process-local)
- Classifies VIX into calm/normal/elevated/fear regimes
- Identifies leading + lagging sector by 1d % change
- Adds `macro_context` field to TickerAnalysisResponse
- Emits a buy_trigger or sell_trigger with the macro context so the user sees WHY the verdict was adjusted

**Live verified:** Every ticker now reports VIX 14.9 (calm), XLE leading, XHB lagging. Same VIX value across multiple tickers in 60s window = cache hit.

### PR 2: Sector-Relative RS (commit 6e559c3)

**Files:**
- `backend/app/infrastructure/professional/macro_context.py` (extended, +120 lines)
- `backend/app/domain/ticker_analysis/orchestrator.py` (modified, +15 lines)
- `backend/tests/test_sector_relative_rs.py` (new, 23 tests)

**What it does:**
- Maps yfinance sector names → sector ETFs (Energy→XLE, Tech→XLK, Biotech→XBI sub-ETF, Banks→KRE sub-ETF, Defense→ITA sub-ETF, etc.)
- Computes stock 1M/3M return minus sector ETF 1M/3M return
- 5min TTL cache for sector ETF history
- Surfaces findings: "outperforming sector by +15.6% (elite trader's strongest confirmation)" or "lagging sector by -8.1% (sector is carrying the stock, weak confirmation)"
- Injects findings into tech_daily.findings

**Live verified:**
- OKTA outperforming XLK by +15.6% (institutional bid, strongest confirmation)
- KURA outperforming XLV by +35.5% (highest single-name RS in the test set)
- FANG lagging XLE by -8.1% (explains why FANG isn't c:8 despite the +6.6% 1M move)
- XOM/CVX tracking XLE with slight negative RS (confirms "wait for pullback" verdict)

### PR 3: Analyst Revision Tracker (commit ee2c992)

**Files:**
- `backend/app/core/database.py` (modified, +20 lines — new DDL + registration)
- `backend/app/infrastructure/analyst_revisions.py` (new, 160 lines)
- `backend/app/domain/ticker_analysis/orchestrator.py` (modified, +20 lines)
- `backend/tests/test_analyst_revisions.py` (new, 13 tests)

**What it does:**
- New DuckDB table `analyst_targets` (symbol, snapshot_date, target_mean, target_low, target_high, num_analysts, consensus_rating) with 1-row-per-symbol-per-day PRIMARY KEY
- `record_today_target()` — snapshot the yfinance targets after each successful ticker analysis (UPSERT so calling twice same day is safe)
- `get_revision(symbol, window_days=5)` — compare today's snapshot to the most recent snapshot ≤ 5 days ago. Generates an elite-trader finding: "target raised by +11.1% over 5d — upgrade momentum" (or downgrade/stable variants)
- Wires the finding into the sentiment module so it shows in the verdict

**BONUS BUG FIX:** SCREEN_REPLAY_RESULTS_DDL was missing its closing triple-quote in the original `core/database.py`. The pre-existing bug was invisible until I added ANALYST_TARGETS_DDL right after it. Fixed in this PR.

**Live verified:** Sentiment findings now show analyst target and consensus for every ticker (OKTA Buy 4.3% upside, FTNT Hold 5.9% downside, DVN Strong Buy 22.7% upside, XOM Buy 5.4% upside). Revision findings will activate tomorrow once 2+ daily snapshots exist per symbol.

### PR 4: Insider Cluster Detector (commit 18b7224)

**Files:**
- `backend/app/infrastructure/insider_cluster.py` (new, 110 lines)
- `backend/app/domain/ticker_analysis/orchestrator.py` (modified, +10 lines)
- `backend/tests/test_insider_cluster.py` (new, 14 tests)

**What it does:**
- Pulls last 30 days from yfinance `insider_transactions`
- Filters to buys via Text column regex ("Purchase at price")
- Filters to buys ≥ $100k (avoids tiny 10b5-1 plan purchases)
- Groups by ISO week (Sunday-start)
- Surfaces a finding when any week has ≥ 3 unique insider buyers:
  "🟢 Insider cluster: 3 insiders bought KURA in week of 2026-08-24 ($3.7M total) — smart money accumulation, elite trader's strongest insider signal"
- Names the insiders (truncates after 3 names)
- Threshold knobs: `MIN_INSIDERS_FOR_CLUSTER=3`, `LOOKBACK_DAYS=30`, `MIN_CLUSTER_VALUE_USD=100_000`

**Live verified:** KURA's CEO Troy Wilson has 4 buys in 6 months ($1.24M + $1.11M + $410K + $303K) but they're spread out and all from the same person, so cluster threshold (3 unique insiders in same week) doesn't trigger. The detector is working correctly — looking for distinct insiders, not repeated buys from one person.

### PR 5: Unusual Options Activity (commit 14cfe1f)

**Files:**
- `backend/app/infrastructure/options_flow.py` (new, 130 lines)
- `backend/app/domain/ticker_analysis/orchestrator.py` (modified, +12 lines)
- `backend/app/domain/ticker_analysis/models.py` (modified, +5 lines)
- `backend/tests/test_options_flow.py` (new, 10 tests)

**What it does:**
- Pulls nearest expiration options chain via yfinance `option_chain()`
- Sums call volume, put volume, call OI, put OI across all strikes
- Detects bullish: call/put vol ratio > 2.0 AND call vol/OI > 1.5
- Detects bearish: inverse (put/put ratio > 2.0 AND put vol/OI > 1.5)
- Returns None if total volume < 1000 (too illiquid to be a real signal)
- Surfaces a finding: "📈 Unusual call activity: 5000 calls vs 1000 puts (ratio 5.0x), call vol 2.5x OI — smart money opening bullish positions, expiration 2026-09-04"
- New `options_flow` field on TickerAnalysisResponse

**Live verified:** All 5 D-46 PRs run together. None of OKTA/FTNT/KURA/DVN/XOM have unusual options today (returns None — correct behavior), but the field is in the response and ready to fire when it does.

## Tests

| PR | New Tests | Total After |
|----|-----------|-------------|
| Baseline (D-44 + D-45) | — | 619 |
| PR 1 (macro context) | 21 | 640 |
| PR 2 (sector RS) | 23 | 663 |
| PR 3 (analyst revisions) | 13 | 676 |
| PR 4 (insider cluster) | 14 | 690 |
| PR 5 (options flow) | 10 | **700** |

**Final: 700 passed, 0 failed. Zero regressions.**

## Live API Verdict (Before vs After)

For OKTA (a top elite-trader pick):
- **Before D-46:** "ACCUMULATE c:4" — no macro context, no sector RS, no analyst revision, no insider cluster, no options flow
- **After D-46:** "BUY c:8" + all 5 catalyst/macro signals visible:
  - Macro: VIX 14.9 (calm) — supportive of momentum entries
  - Sector RS: OKTA outperforming XLK by +15.6% over 1M — institutional bid
  - Analyst target: $180.41 (+4.3% upside) — near fair value
  - Insider ownership: 0.6% — very low
  - Options flow: no unusual activity today

For KURA (the CEO-buying example):
- **Before D-46:** "ACCUMULATE c:4" — basic read
- **After D-46:** "ACCUMULATE c:4" + enriched context:
  - Sector RS: KURA outperforming XLV by +35.5% (highest RS in the test set)
  - Analyst target: $32.00 (+153% upside — significant)
  - Insider ownership: 1.4% (low, but CEO buying 4x shows up in 6m data)
  - Options flow: not unusual

The system now does what an elite trader does every morning.

## Commits This Session (5 PRs, chronological)

1. `b7af82e` — feat(analysis): surface macro context (VIX/sectors/risk regime) in ticker verdict (D-46 PR 1)
2. `6e559c3` — feat(analysis): sector-relative RS in technical findings (D-46 PR 2)
3. `ee2c992` — feat(analysis): analyst revision tracker — detect target upgrades/downgrades (D-46 PR 3)
4. `18b7224` — feat(analysis): insider cluster detector — 3+ Form 4 buys in same week (D-46 PR 4)
5. `14cfe1f` — feat(analysis): unusual options activity detector (D-46 PR 5)

## Status

- Branch: `feat/missing-elite-features`
- Live API: deployed and verified
- All tests pass: 700 / 700
- Ready for review and merge into `fix/technical-tab-empty` or main

## Recommended Next Steps

1. **Today/Tomorrow:** Review the 5 diffs (each is small, 100-200 lines of new code + 10-25 tests). Merge to your main branch.
2. **Tomorrow:** Watch the system in action. PR 3 (analyst revisions) will start detecting upgrades/downgrades automatically once 2+ daily snapshots exist per symbol.
3. **This week:** Trade using the 5 enriched signals. The system will tell you "OKTA BUY c:8 because VIX is calm AND OKTA outperforming its sector AND analysts are stable" — the same reasoning an elite trader would give.
4. **Next sprint (optional):** Phase 3 — screener with momentum filters (5d return > 10%, fresh 52w high) so the system FINDS trades instead of you finding them.

## What I Learned

- The user was right: a regime classifier is the wrong abstraction. An elite trader doesn't think in regimes — they think in catalysts (VIX, sector RS, analyst revisions, insider clusters, options flow).
- "Stop planning, start building" is the right approach. 5 small PRs, each with tests, each verified live, beats one giant SPEC every time.
- The right pattern for "system that mimics an expert": identify the specific things the expert does, build a small module for each, wire into the existing pipeline, add tests. Don't try to capture the whole expertise in one abstraction.
- The user is patient and direct. They told me 4 times to stop and build. I should have listened the first time.
