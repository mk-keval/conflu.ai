# Paper Trading Workflow — conflu.ai Elite Trader System

This is your **operating manual** for paper trading with conflu.ai. Follow it every morning for 2-3 weeks. The system is only as good as your discipline in using it.

---

## The Daily Ritual (1 click after the close — morning brief optional)

**Default rhythm:** once the market has closed, open **Workflow → Daily
Routine** and press **"Run After-Close (one go)"**. That single call runs the
7-step gate on today's candidates (new entries), records every rejection, and
syncs + applies exits for the open book (D-68). Then glance at **Workflow →
Journal** — trades table, runs strip, rejections, Export CSV.

The journal of record is **SQLite** (`data/paper_trades.db`) — there is no
spreadsheet to maintain. Steps 1–2 below are the optional morning preview;
Steps 3–4 explain exactly what the one-go run does under the hood; Step 5 is
the weekly review.

### Step 1 (optional): Preview today's candidate list (1 minute)

```bash
python backend/scripts/paper_trade_from_brief.py --min-conviction 5
```

*(preview only — nothing lands in the journal until you run `--run-close`
/`--apply` or press the one-go button.)*

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

### Step 3: Enforce the gate + record entries (1 click, after the close)

Press **"Run After-Close (one go)"** in **Workflow → Daily Routine**. It calls
`POST /api/v1/workflow/paper-trades/run-close`, which:

1. Fetches the Morning Brief + each candidate's verdict, runs the 7-step gate,
   sizes the survivors (CONDITIONAL → 0.5×), and **upserts each accepted trade
   into the journal of record** (`data/paper_trades.db`; key
   `(date_entered, symbol)` — same-day re-runs keep the row).
2. Appends every rejected candidate to the **rejections** table with its
   `gate_failed_step` + reason — nothing is silently dropped.

Entries land at end-of-day (`entry_timing='eod'`). Missed days stay **honest
gaps** — no backfill, no invented rows.

### Step 4: The exits close the loop themselves (0 minutes)

The same one-go call runs the exit sync (Touchpoint B): it walks daily OHLCV
from the entry date forward and fills the exit columns when a stop / target /
time-stop triggers — conservative priority (a gap through the stop fills at
the open, T2 before T1, etc.):

`date_closed`, `exit_price`, `exit_reason`, `realized_r`, `pnl_usd`, `mfe_r`,
`mae_r`, `plan_adherence`.

Two rules you should know:

- **Same-day guard:** a position entered today is skipped — exits start the
  next session. This is not day-trading; entries fill at the close.
- **The entry bar can't stop you out:** because entries fill at the close
  (`entry_timing='eod'`), the entry day's own intraday range is excluded from
  exit checks.

`plan_adherence` is a **process** metric (did the system execute the plan?),
not a success metric — profitability is measured by `realized_r` and
expectancy.

Errors are honest, not silent: every run writes a row to the `workflow_runs`
log (`ok` / `partial` / `error`) and the runs strip in the Journal tab shows
missed (gray) and failed (red) days at a glance. You can still run the
individual touchpoints (gate only / exits dry-run / exits apply) from the
"Manual steps" sections in Daily Routine.

### Step 5: Weekly review (Sunday, 15 minutes)

Only **closed** rows count (those with a `date_closed`). Open rows are not
evidence yet.

1. Count: how many trades won, lost, still open?
2. Compute win rate: wins / (wins + losses)
3. Compute **expectancy**: `mean(realized_r)` across closed trades - THE north-star number
4. Compute **profit factor**: `sum(winning realized_r) / abs(sum(losing realized_r))`
5. Look at the **losing trades**: was the catalyst signal wrong, or was the execution wrong? Check `mae_r` - did it go green first and then stop you out?
6. Look at the **winning trades**: check `mfe_r` - did you leave R on the table?
7. Review the **rejections log** (Journal tab): were the rejected candidates actually the losers? If the gate rejects winners, the gate is wrong.
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
data/
└── paper_trades.db            # THE journal of record (SQLite, D-68): trades + rejections + runs

docs/
├── PAPER_TRADING/             # this workflow doc + future updates
├── paper_trades/              # LEGACY CSVs - import source + archive (byte-identical, D-68)
│   ├── TEMPLATE.csv           # canonical header (D-51 schema)
│   ├── REJECTIONS.csv         # legacy rejections (imported once; new rejects live in the DB)
│   └── archive/               # voided cohorts (see archive/README.md)
├── SESSIONS/
│   └── morning_brief/         # daily JSON output from the morning brief
├── DECISIONS/                 # ADR-style decision records
└── ...
```

---

## First day checklist (today)

- [ ] (Optional morning) Preview the candidates: `python backend/scripts/paper_trade_from_brief.py --min-conviction 5` - then pick what you'd actually trade
- [ ] After the close: press **"Run After-Close (one go)"** in Workflow → Daily Routine - the gate enforces (entries + rejections) and exits sync
- [ ] Check **Workflow → Journal**: trades table, rejections, runs strip (green = ran, red = error)
- [ ] Set alerts in your broker at the entry/stop/target prices (paper account)

That's it. The rest is discipline.

---

## The script (CLI twin of the one-go button)

`backend/scripts/paper_trade_from_brief.py` — fetches the same data as the UI's Morning Brief page, runs the 7-step gate, and writes to the journal of record.

```bash
# One-go after-close run: gate enforcement + exits applied (same as the UI button)
python backend/scripts/paper_trade_from_brief.py --run-close

# Gate enforcement only (entries + rejections), no exit sync
python backend/scripts/paper_trade_from_brief.py --apply

# Exit sync only - dry-run preview by default; add --apply to write
python backend/scripts/paper_trade_from_brief.py --sync-exits

# Higher conviction bar (only the strongest setups)
python backend/scripts/paper_trade_from_brief.py --run-close --min-conviction 7
```

Output: rows upserted into `data/paper_trades.db` (key `(date_entered, symbol)`); rejected candidates are logged with their failed gate step. Without `--apply`/`--run-close` the script is a **preview** - nothing is written.

> **Historical gap (2026-09-16), now closed.** The script used to write *every* candidate above the conviction floor without running the gate. Enforcement + rejection logging now run in this path, and each run is logged to `workflow_runs`. Source: [evidence audit](../SESSIONS/2026-09-16_paper-trade-evidence-audit.md).

The old `daily_morning_ritual.py` script is **deprecated** as of 2026-09-03 — it called `/api/v1/screen/tv` directly with filter names that no longer exist in the schema. The new script uses the same `/api/v1/professional/morning-brief` endpoint as the UI, so what you see in the app and what lands in the journal are guaranteed to match.
