# Paper Trading Workflow — conflu.ai Elite Trader System

This is your **operating manual** for paper trading with conflu.ai. Follow it every morning for 2-3 weeks. The system is only as good as your discipline in using it.

---

## The Daily Ritual (15-20 minutes, market open + 1 hour)

### Step 1: Generate today's candidate list (1 minute)

```bash
python backend/scripts/paper_trade_from_brief.py --min-conviction 5
```

This will:
- Print the macro context (VIX, sector leaders/laggers, risk regime)
- Run the TV screener with catalyst enrichment
- Surface stocks with 2+ catalyst signals firing
- Save the full output to `docs/SESSIONS/morning_brief/YYYY-MM-DD.json`

Output example:
```
══════════════════════════════════════════════════════════════════════════
  TOP CANDIDATES — 8 passed min_confluence filter
══════════════════════════════════════════════════════════════════════════
  SYMBOL   SCORE  CONF   CATALYSTS
  --------------------------------------------------------------------
  OKTA     87     3/5    🔥 HIGH CONFLUENCE: 3/5 catalysts firing
          └─ 📈 Sector RS: outperforming XLK by +15.6% over 1M; 🟢 Insider cluster...
  FTNT     82     3/5    🔥 HIGH CONFLUENCE: 3/5 catalysts firing
          └─ 📈 Post-earnings drift: 5d since print, beat by 9.4%; ...
```

### Step 2: Pick 3-5 candidates (5 minutes)

Look at the top 5 candidates. For each, ask:

1. **Does the THESIS make sense to you?** (Read the verdict's `buy_triggers` and `key_red_flags`.)
2. **Is the ENTRY acceptable?** (Should be in the entry zone, not chasing.)
3. **Is the STOP at a structural level?** (Not an arbitrary %.)
4. **Is the TARGET realistic?** (At least **2.5x** the stop distance - a minimum **2.5:1** reward-to-risk.) This matches `RISK_REWARD_PASS` in `frontend/src/workflow/gate.ts` and the elite blueprint. Under 2.5:1 is a **SKIP**, not a candidate.

If yes to all 4, it's a candidate. If no to any, skip.

### Step 3: Record each paper trade in a CSV (5 minutes per trade)

Create a file at `docs/paper_trades/YYYY-MM-DD.csv` with one row per trade:

```csv
date_entered,symbol,sector,action,entry_price,stop_loss,target_1,target_2,position_size_pct,confluence_count,signal_at_entry,notes
2026-09-01,OKTA,Technology,BUY,170,160,200,215,5,3,"sector_RS+15.6%_+insider_cluster+post_earnings","Post-earnings drift on OKTA, market-leading sector RS, 3/5 catalysts. Stop below 50d SMA."
2026-09-01,FTNT,Technology,BUY,168,160,185,200,6,3,"post_earnings+insider_ownership_17%+sector_RS_tracking","Held back, watching for confirmation."
```

### Step 4: Close the loop - record the exit (5 minutes at close)

**This step is mandatory.** Without it the system cannot be measured: no exits
means no win rate, no expectancy, no average R. The 2026-09 bypass-path cohort
(31 rows) was voided precisely because this step was never performed.

When a position ends, fill in the outcome columns **on its existing row** - do
NOT open a row in tomorrow's file:

| Column | Value |
|---|---|
| `date_closed` | `YYYY-MM-DD` |
| `exit_price` | actual exit price |
| `exit_reason` | `stop` / `target_1` / `target_2` / `trail` / `time_stop` / `thesis_break` / `manual` |
| `shares` | shares actually taken |
| `realized_r` | `(exit_price - entry_price) / (entry_price - stop_loss)` - signed |
| `pnl_usd` | optional - dollar result |
| `mfe_r` | optional - best unrealized R reached (did we exit too early?) |
| `mae_r` | optional - worst unrealized R (was the stop too wide?) |
| `plan_adherence` | `followed` / `partial` / `broke` - did you run the plan? |

A position that is still open **stays open**. Never duplicate it into a new
day's file - that is what made the previous cohort unmeasurable.

`plan_adherence` is a **process** metric, not a success metric. You can be 100%
adherent to a bad plan and still lose. Profitability is measured by `realized_r`
and expectancy.

### Step 5: Weekly review (Sunday, 15 minutes)

Only **closed** rows count (those with a `date_closed`). Open rows are not
evidence yet.

1. Count: how many trades won, lost, still open?
2. Compute win rate: wins / (wins + losses)
3. Compute **expectancy**: `mean(realized_r)` across closed trades - THE north-star number
4. Compute **profit factor**: `sum(winning realized_r) / abs(sum(losing realized_r))`
5. Look at the **losing trades**: was the catalyst signal wrong, or was the execution wrong? Check `mae_r` - did it go green first and then stop you out?
6. Look at the **winning trades**: check `mfe_r` - did you leave R on the table?
7. Review `REJECTIONS.csv`: were the rejected candidates actually the losers? If the gate rejects winners, the gate is wrong.
8. **Kill criteria** - if after 30+ closed trades expectancy <= 0, the system is not working. Change it or stop. Do not "give it more time" without a reason.

**Minimum sample:** do not draw pattern-level conclusions below ~30 closed
trades per pattern. Below that you are reading noise, not edge.

---

## What conflu.ai gives you (the 5 D-46 catalyst signals)

1. **Macro context** — VIX, sector leaders/laggers, risk regime. "Is it a good day to take new trades?"
2. **Sector-relative RS** — Is the stock confirming its sector, or fighting it? The strongest confirmation signal.
3. **Post-earnings drift** — 0-20 days after a print, especially with a beat. The setup that caught CRWD/OKTA/FTNT on Aug 27.
4. **Analyst revision** — Target raised >5% in last 5 days. Wall Street is upgrading.
5. **Insider cluster** — 3+ Form 4 buys same week. CEO buying 4x in a month = the elite trader's #1 insider signal.
6. **Options flow** — Call/put vol ratio > 2.0 + vol > 1.5x OI. Smart money opening new positions.

The screener with `enrich_with_catalysts: true` runs all 5 on each result and gives a `confluence_count` (0-5). **3+ is "high confluence"** — that's when you should focus.

---

## What conflu.ai does NOT do (your job)

- **Set position size.** System suggests; you decide based on portfolio.
- **Pick the entry limit price.** System gives a zone; you decide your limit.
- **Adjust for portfolio correlations.** System doesn't know your other positions.
- **Read the news flow.** System reads yfinance headlines, not the WSJ.
- **Decide if it's a trade worth taking.** The system is a tool. You're the trader.

---

## How to validate conflu.ai's value

Track these metrics weekly:
- **Hit rate**: % of paper trades that hit T1 before stop
- **Average R**: avg profit in R-multiples (T1 hit = +1R, stop hit = -1R)
- **Catalyst precision**: which catalyst signal predicted the best trades?
- **System precision vs manual**: how often does conflu.ai's verdict match your manual read?

**The system is good if:** After 20+ paper trades, your hit rate is > 50% AND your average R is > 0.5R.

**The system needs work if:** Your manual reads are systematically better than conflu.ai's verdicts.

---

## File layout

```
docs/
├── PAPER_TRADING/             # this workflow doc + future updates
├── paper_trades/              # per-day candidate/outcome CSVs (one per trading day)
│   ├── TEMPLATE.csv           # the 21-column schema (12 entry + 9 exit-capture)
│   ├── REJECTIONS.csv         # every candidate the gate rejected, and which step
│   └── archive/               # voided cohorts (see archive/README.md)
├── SESSIONS/
│   └── morning_brief/         # daily JSON output from the morning brief
├── DECISIONS/                 # ADR-style decision records
└── ...
```

---

## First day checklist (today)

- [ ] Run the morning brief generator script (writes the **candidate** CSV)
- [ ] **Pick 1-2 that match your conviction** - do NOT keep everything the script wrote. Run each through the 7-step gate, drop the rest, and log the rejects in `REJECTIONS.csv`
- [ ] Set alerts in your broker at the entry/stop/target prices (paper account)
- [ ] End of day: **record the exit** on any position that closed (Step 4). An open position stays open.

That's it. The rest is discipline.

---

## The script (preferred path)

`backend/scripts/paper_trade_from_brief.py` — fetches the same data as the UI's Morning Brief page and writes the CSV automatically.

```bash
# Write all candidates (conviction >= 5) to today's CSV
python backend/scripts/paper_trade_from_brief.py

# Write only specific tickers
python backend/scripts/paper_trade_from_brief.py --only HRMY,SLDE,DOCU

# Higher conviction bar (only the strongest setups)
python backend/scripts/paper_trade_from_brief.py --min-conviction 7
```

Output: `docs/paper_trades/YYYY-MM-DD.csv` - a **candidate list**, not a trade list.

> **KNOWN GAP (2026-09-16).** The script writes *every* candidate above the conviction floor. It does **not** run the validation gate, size by conviction, or record a rejection. Do not treat its output as validated. Until the gate is enforced in this path, apply Step 2 by hand and log the rejects to `docs/paper_trades/REJECTIONS.csv`. Source: [evidence audit](../SESSIONS/2026-09-16_paper-trade-evidence-audit.md).

The old `daily_morning_ritual.py` script is **deprecated** as of 2026-09-03 — it called `/api/v1/screen/tv` directly with filter names that no longer exist in the schema. The new script uses the same `/api/v1/professional/morning-brief` endpoint as the UI, so what you see in the app and what you get in the CSV are guaranteed to match.
