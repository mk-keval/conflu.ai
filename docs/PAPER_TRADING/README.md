# Paper Trading Workflow — conflu.ai Elite Trader System

This is your **operating manual** for paper trading with conflu.ai. Follow it every morning for 2-3 weeks. The system is only as good as your discipline in using it.

---

## The Daily Ritual (15-20 minutes, market open + 1 hour)

### Step 1: Run the morning ritual script (1 minute)

```bash
python backend/scripts/daily_morning_ritual.py --min-confluence 2 --limit 50
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
4. **Is the TARGET realistic?** (At least 1.5-2x the stop distance.)

If yes to all 4, it's a candidate. If no to any, skip.

### Step 3: Record each paper trade in a CSV (5 minutes per trade)

Create a file at `docs/paper_trades/YYYY-MM-DD.csv` with one row per trade:

```csv
date_entered,symbol,sector,action,entry_price,stop_loss,target_1,target_2,position_size_pct,confluence_count,signal_at_entry,notes
2026-09-01,OKTA,Technology,BUY,170,160,200,215,5,3,"sector_RS+15.6%_+insider_cluster+post_earnings","Post-earnings drift on OKTA, market-leading sector RS, 3/5 catalysts. Stop below 50d SMA."
2026-09-01,FTNT,Technology,BUY,168,160,185,200,6,3,"post_earnings+insider_ownership_17%+sector_RS_tracking","Held back, watching for confirmation."
```

### Step 4: Monitor and update (5 minutes at close)

End of day:
- For each open position, check the price vs entry/stop/target
- Update the CSV with a comment column or new "status" column
- If hit target: close the trade, record P&L
- If hit stop: close the trade, record loss
- If still open: add a row to tomorrow's CSV with current price

### Step 5: Weekly review (Sunday, 15 minutes)

At the end of each week:
1. Count: how many trades won, lost, still open?
2. Compute win rate: wins / (wins + losses)
3. Compute average R-multiple: sum(R-multiples) / closed trades
4. Look at the **losing trades**: what was wrong? Was the catalyst signal wrong, or was your execution?
5. Look at the **winning trades**: which catalyst signal was the strongest predictor?
6. Adjust the system: if insider cluster predicts but sector RS doesn't, you can tighten the screener filter to `min_confluence=3`.

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
├── SESSIONS/
│   ├── morning_brief/         # daily JSON output from the morning ritual
│   └── paper_trades/          # per-day CSV files (one per trading day)
├── DECISIONS/                 # ADR-style decision records
└── ...
```

---

## First day checklist (today)

- [ ] Run the morning ritual script
- [ ] Look at the top 5 candidates
- [ ] Pick 1-2 that match your conviction
- [ ] Create `docs/paper_trades/2026-09-01.csv` with the trades
- [ ] Set alerts in your broker at the entry/stop/target prices (paper account)
- [ ] End of day: update the CSV with current price

That's it. The rest is discipline.
