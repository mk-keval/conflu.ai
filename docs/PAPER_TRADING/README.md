# Paper Trading Workflow — conflu.ai Elite Trader System

This is your **operating manual** for paper trading with conflu.ai. Follow it every trading day for the life of the current sample (30 closed scored trades or 6 weeks after the first scored fill, whichever first). The system is only as good as your discipline in using it.

---

## The Daily Ritual (1 click after the close — morning brief optional)

**Default rhythm:** once the market has closed, open **Workflow → Daily
Routine** and press **"Run After-Close (one go)"**. That single call fills or
expires pending orders from earlier signals, runs the 7-step gate on today's
candidates (new pending orders), records every rejection, and syncs + applies
exits for the open book (D-68/D-73). Then glance at **Workflow → Journal** —
trades table, pending panel, runs strip, rejections, Export CSV.

**Scored sample: FWD-v0.2 — live 2026-10-29; first fill TBD.** FWD-v0.1 was
closed for verdict purposes on 2026-10-28: 3 valid fills (SF, IOSP, CRS), 1
closed (CRS −1.00R), 2 open, 1 pending (DUK). Those rows are reference only. New
rows are stamped `v0.2` from the go-live commit; no `interim` row was created.
The v0.2 clock starts at its first fill; from there the sample runs to **30
closed scored trades or 6 weeks after the first scored fill**, whichever first.
The four 2026-10-19/20 phantom fills are voided and visible; the three legacy
rows (NTNX/WBD/NVDA) are excluded from stats. Rules and trigger:
[PRE_REGISTRATION-v0.2.md](PRE_REGISTRATION-v0.2.md). Canonical numbers:
[SCORECARD.md](SCORECARD.md).

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

### Step 3: Enforce the gate + queue entries (1 click, after the close)

Press **"Run After-Close (one go)"** in **Workflow → Daily Routine**. It calls
`POST /api/v1/workflow/paper-trades/run-close`, which:

1. **Processes pending orders from earlier signals first (D-73).** A limit fills
   only from an actual bar strictly after the signal date — at the open when the
   open is at/below the limit, or at the limit when the low touches it. An order
   that gaps through the stop is cancelled; an unfilled order expires after 3
   sessions. If the fill bar's low touches the stop, the trade closes at −1R the
   same day (fill-bar targets are ignored).
2. Fetches the Morning Brief + each candidate's verdict, runs the 7-step gate,
   sizes the survivors (CONDITIONAL → 0.5×), and **queues each accepted trade as
   a pending limit at `entry_low`** in `pending_orders` — never a same-day journal
   entry.
3. Appends every rejected candidate to the **rejections** table with its
   `gate_failed_step` + reason — nothing is silently dropped.
4. Logs the run to `workflow_runs`.

A signal is **not** a fill. The journal has no entry until a later session
actually trades your limit. Missed days stay **honest gaps** — no backfill, no
invented rows. Rejections carry the `template` and market `regime`; entries carry
screen/confluence/sector plus the plan's `max_hold_days`. **The first actual fill
was 2026-10-22 (SF @ 65.40); that started the forward clock.**

### Step 4: The exits close the loop themselves (0 minutes)

The same one-go call processes fills, then runs the exit sync (Touchpoint B): it
walks daily OHLCV from the entry date forward and fills the exit columns when a
stop / target / time-stop triggers — conservative priority (a gap through the stop
fills at the open, T2 before T1, etc.):

`date_closed`, `exit_price`, `exit_reason`, `realized_r`, `pnl_usd`,
`pnl_gross_usd`, `costs_usd`, `mfe_r`, `mae_r`, `plan_adherence`.

Rules you should know:

- **Same-session stop:** if the fill bar's low touches the stop, the trade closes
  at the stop that day at −1R. Targets on the fill bar are ignored — the intrabar
  order is unknowable, so the conservative outcome wins.
- **Same-day guard after a fill:** exits start the next session. This is not
  day-trading.
- **Dollar P&L is net of costs:** `pnl_usd = shares × (exit − entry) − (entry +
  exit) × shares × 15 bps` (10 bps fee + 5 bps slippage per side). `realized_r`
  stays a gross price multiple, matching the backtests (D-71/D-74). The gross
  dollar figure and the cost are stored separately so the two are never mixed.

> **Time stop (audit 2026-10-19, fixed in execution v0.1):** the trade plan's
> 20–60-*calendar-day* limit is now stored in the journal and applied by the exit sync
> (converted to the first session on/after the cutoff). **Still open (review item A):**
> T1 can sit far above entry because targets are the highest structural levels, not the
> nearest resistance; the gate's R/R is measured to the last target. In the first valid
> closed trade (CRS) T1 was **11.2R** from the entry-zone midpoint (**27.7R** from
> the fill); the trade reached **+3.72R MFE**, then stopped for **−1.00R**.
> Targets/R:R are deliberately unchanged during this sample.
> See `docs/PAPER_TRADING/PIPELINE_AUDIT.md` F3/F5 and `SCORECARD.md`.
>
> The 3 pre-instrumentation rows (NTNX/WBD/NVDA) are flagged `exclude_from_stats=1`:
> they remain visible/open but do not count toward the 30-trade scorecard or expectancy.
> The four 2026-10-19/20 phantom fills are `voided=1` and also never count.

`plan_adherence` is a **process** metric (did the system execute the plan?),
not a success metric — profitability is measured by `realized_r` and
expectancy.

Errors are honest, not silent: every run writes a row to the `workflow_runs`
log (`ok` / `partial` / `error`) and the runs strip in the Journal tab shows
missed (gray) and failed (red) days at a glance. You can still run the
individual touchpoints (gate only / exits dry-run / exits apply) from the
"Manual steps" sections in Daily Routine.

### Optional: inspect the last 2 months as a simulation (Journal → Replay)

The forward journal only knows what happened after you started running it. To
sanity-check the deployed screens against recent history:

```bash
python run_paper_replay.py
```

That replays the deployed `config/regime_screens.yaml` screens over the current
S&P 500 for the last 60 days — regime computed as of each signal day, next-open
entries, 2 ATR stop / 3 ATR target / 15-bar cap, fees + slippage included — and
stores the result in **separate** `replay_runs` / `replay_trades` tables. The
Journal tab's **2-month replay** toggle shows every winner/loser, win rate,
expectancy and hypothetical P&L at 1% risk per trade.

This is **simulated screen/template evidence, not forward evidence**:
TradingView's screener cannot be rewound, so the replay does not reproduce the
exact live brief (ranking, confluence, catalysts, gate). Replay rows never count
toward the forward scorecard or the kill rule. Use it to inspect behavior; use
the forward journal to judge the system.

### Design review (not part of the daily ritual)

- `docs/PAPER_TRADING/PIPELINE_AUDIT.md` — read-only audit (2026-10-19) of the live
  screener → gate → exit path: root causes, evidence, and prioritized fixes mapped to
  the four dials. Read this before changing rules.
- `docs/PAPER_TRADING/FORWARD_TEST_REVIEW.md` — the pre-registered agenda for the
  review after 30 closed forward trades (exit RR ceiling + MFE, choppy/ranging
  menu gap, per-screen confirmation, gate effectiveness). No rule changes before
  the trigger.
- `docs/PAPER_TRADING/PRE_REGISTRATION.md` — the frozen rules, endpoints, trigger
  and kill rule for the active forward sample (FWD-v0.1), plus the template for
  the next experiment.
- `docs/PAPER_TRADING/SCORECARD.md` — the one-page forward scorecard: canonical
  definitions, current snapshot, exclusions and integrity gate.
- `docs/backtests/HYPOTHESIS_LOG.md` — every experiment, labelled confirmatory /
  exploratory / measurement / invalid. Check this before citing a backtest.
- `docs/PAPER_TRADING/V2_RISK_GOVERNOR_BLUEPRINT.md` — design proposal for the
  missing regime→risk layer (the "four dials": permission, playbook, size,
  exits). Not implemented; input for that review.
- `run_replay_experiments.py` — runs counterfactual what-if variants on the same
  replay window (e.g. choppy menu swap, wider targets). **Design learning only**
  — hypotheses to size, never forward evidence, never a P&L promise.

### Step 5: Weekly review (Sunday, 15 minutes)

The canonical numbers come from:

```bash
python scripts/verify_journal.py   # PASS/FAIL measurement gate — run first
python scripts/scorecard.py        # expectancy, WR, PF, dollars, MFE gap
```

`verify_journal.py` must print `PASS` before you quote a number. If it fails, fix
the journal (or restore the backup) before reviewing; a scorecard built on a
phantom fill or a wrong dollar figure is worse than no scorecard.

Only **closed forward** rows count: `voided=0`, `exclude_from_stats=0`, and a
`date_closed`. The 3 legacy rows (NTNX/WBD/NVDA), the 4 phantom fills
(PM/AMGN/CCK/MMM), open positions and pending orders are excluded. Open rows are
not evidence yet.

1. Count: how many trades won, lost, still open, still pending?
2. Win rate: wins / (wins + losses)
3. **Expectancy**: `mean(realized_r)` across closed trades — THE north-star number
4. **Profit factor**: `sum(winning realized_r) / abs(sum(losing realized_r))`
5. **MFE gap**: `mean(mfe_r − realized_r)` — did winners (and stopped trades) give back R?
6. Look at the **losing trades**: was the catalyst signal wrong, or was the execution wrong? Check `mae_r` — did it go green first and then stop you out?
7. Look at the **winning trades**: check `mfe_r` — did you leave R on the table?
8. Review the **rejections log** (Journal tab): were the rejected candidates actually the losers? If the gate rejects winners, the gate is wrong.
9. **Kill rule** — if after 30+ closed scored trades expectancy ≤ 0, the system is not working. Change it or stop. Do not "give it more time" without a written reason. The calendar review (6 weeks after the first scored fill) is a progress review, not a kill-rule verdict.

**Minimum sample:** do not draw pattern-level conclusions below ~30 closed
trades per pattern. Below that you are reading noise, not edge. One closed trade
(CRS −1.00R) is a data point, not a trend.

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

Track these metrics weekly — `python scripts/scorecard.py` computes the first five
from the journal, with one fixed filter and one R definition:

- **Expectancy in R**: `mean(realized_r)` over closed forward trades — the primary metric
- **Win rate**: winners / closed trades
- **Profit factor**: `sum(winning R) / abs(sum(losing R))`
- **MFE gap**: `mean(mfe_r − realized_r)` — positive means profit was left on the table
- **Net dollars**: after 10 bps fee + 5 bps slippage per side
- **Catalyst precision**: which catalyst signal predicted the best trades? (descriptive; needs a sample)
- **System precision vs manual**: how often does conflu.ai's verdict match your manual read?

**The binding rules are pre-registered in `VISION.md` (D-75):** at **30+ closed
trades**, the sample passes when expectancy > 0 after costs, profit factor ≥ 1.3
and average loss ≤ 1.0R. Win rate is reported, not gated. The kill rule is
expectancy ≤ 0 after 30+ closed trades; a peak-to-trough drawdown of 8R stops new
entries for review, and 12R kills. A written reason is required to extend.

**Which rows count (D-76):** only the **scored sample version** (`v0.2`). FWD-v0.1
was closed for verdict purposes on 2026-10-28 and is reference only; rows
created on/after go-live (2026-10-29) are `v0.2`. `sample_version`
is set once on insert, and a filled order inherits its order's version. The
scorecard prints other versions as reference; it never folds them into the
headline.

**The system needs work if:** your manual reads are systematically better than
conflu.ai's verdicts, or the gate rejects winners more often than losers.

---

## File layout

```
data/
├── paper_trades.db            # THE journal of record (SQLite, D-68): trades + rejections + runs + pending
└── backups/                   # timestamped DB copies before measurement writes (D-74)

docs/
├── PAPER_TRADING/             # operating manual + scorecard + pre-registration + audit
│   ├── README.md              # this file
│   ├── SCORECARD.md           # canonical forward metrics snapshot
│   ├── PRE_REGISTRATION.md    # frozen FWD-v0.1 rules, trigger, kill rule
│   ├── FORWARD_TEST_REVIEW.md # review agenda (items A–D)
│   ├── PIPELINE_AUDIT.md      # read-only pipeline audit (F1–F10)
│   └── V2_RISK_GOVERNOR_BLUEPRINT.md
├── backtests/                 # validation report, replay artifacts, hypothesis log
│   └── HYPOTHESIS_LOG.md      # every experiment and its evidence label
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
- [ ] After the close: press **"Run After-Close (one go)"** in Workflow → Daily Routine - it fills/expires earlier pending orders, queues today's accepted trades as pending limits, records rejections, and syncs exits
- [ ] Check **Workflow → Journal**: trades table, pending panel, rejections, runs strip (green = ran, red = error)
- [ ] Set alerts in your broker at the entry/stop/target prices (paper account)

That's it. The rest is discipline.

---

## The script (CLI twin of the one-go button)

`backend/scripts/paper_trade_from_brief.py` — fetches the same data as the UI's Morning Brief page, runs the 7-step gate, and writes to the journal of record.

```bash
# One-go after-close run: fill pending, enforce (queue orders + rejections), sync exits
python backend/scripts/paper_trade_from_brief.py --run-close

# Gate enforcement only (queue pending orders + rejections), no exit sync
python backend/scripts/paper_trade_from_brief.py --apply

# Process eligible pending orders only (fills / expiry / same-session stops)
python backend/scripts/paper_trade_from_brief.py --fill-pending

# Exit sync only - dry-run preview by default; add --apply to write
python backend/scripts/paper_trade_from_brief.py --sync-exits

# Order type / expiry overrides (default: limit at entry_low, 3 sessions)
python backend/scripts/paper_trade_from_brief.py --run-close --order-type moo --expiry-sessions 3

# Higher conviction bar (only the strongest setups)
python backend/scripts/paper_trade_from_brief.py --run-close --min-conviction 7
```

Output: accepted signals become rows in `pending_orders`; a later fill creates the `paper_trades` row (key `(date_entered, symbol)`); rejected candidates are logged with their failed gate step. Without `--apply`/`--run-close` the script is a **preview** - nothing is written.

> **Historical gap (2026-09-16), now closed.** The script used to write *every* candidate above the conviction floor without running the gate. Enforcement + rejection logging now run in this path, and each run is logged to `workflow_runs`. Source: [evidence audit](../SESSIONS/2026-09-16_paper-trade-evidence-audit.md).

The old `daily_morning_ritual.py` script is **deprecated** as of 2026-09-03 — it called `/api/v1/screen/tv` directly with filter names that no longer exist in the schema. The new script uses the same `/api/v1/professional/morning-brief` endpoint as the UI, so the candidates you see and the signals that get queued match. Whether a queued signal becomes a journal entry depends on a later fill (D-73).
