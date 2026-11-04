# Gap Log — conflu.ai vs Elite Trader's Manual Read

> Use this file to log **system misses** — situations where the conflu.ai verdict was wrong or incomplete, and a manual elite trader's read would have done better.

---

## Why this exists

The system has 5 catalyst signals (sector RS, post-earnings drift, analyst revisions, insider cluster, options flow) and 700+ tests, but the elite trader uses more than that. Paper trading is how we find the gap.

## How to log a gap

For each paper trade, fill in the **last 3 columns** of the CSV:
- `system_says` — what conflu.ai's verdict said (e.g., "BUY c:7 — bullish setup")
- `manual_elite_read` — what you would have done as the elite trader (e.g., "HOLD — RSI 75, wait for pullback")
- `divergence_y_n` — Y if they differ, N if you agree
- `what_i_missed` — for divergences, what signal did the system fail to capture?

## What to look for

Common gaps the system might miss:
- **Multi-timeframe divergence** — daily looks great but weekly is rolling over
- **Sector-relative breakdown** — stock is in a leading sector BUT individually breaking down
- **Unusual options flow the system missed** (e.g., unusual OI, dark pool prints)
- **Macro events** — Fed day, CPI day, geopolitical (the system has macro context but doesn't gate trades on it)
- **Insider timing** — 3 insiders buying 30 days apart vs same week
- **Time-of-day** — the system is EOD; intraday setups are missed
- **News flow** — the system reads yfinance headlines but not the WSJ/Fed statements/Twitter

## How to use this log

1. **Daily:** After paper trades, fill in the last 3 columns
2. **Weekly:** Review the gaps. Group by category (e.g., "3 misses were about multi-timeframe divergence")
3. **After 2 weeks:** Bring the log to the AI. The categories of misses = the next features to build

## What I (the AI) commit to do

When you come back with this log, I will:
- NOT defend the system
- NOT say "well, the data was there if you looked"
- ONLY identify the most common gap categories and propose 1-2 surgical PRs to fix the top 1-2 categories

## Example entries

| date | symbol | system_says | manual_read | div | what_i_missed |
|------|--------|------------|-------------|-----|---------------|
| 2026-09-01 | XOM | STRONG BUY c:8 | HOLD — RSI 73, wait for pullback | Y | System didn't apply "overbought in confirmed uptrend" rule |
| 2026-09-01 | META | WATCH c:3 | BUY — AI news catalyst is real | Y | System's post-earnings detector missed the qualitative news flow |
| 2026-09-02 | TSLA | HOLD c:3 | HOLD — same | N | — |

The "what_i_missed" column is the most important. It tells us what to build.
