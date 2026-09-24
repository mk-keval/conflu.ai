# 2026-09-16 - Paper-Trade Evidence Audit (Read-Only)

## Why

User: *"I believe I have enough data now to investigate."* Before designing the
enforcement spine (7-step gate + review engine), we audited what the paper-trade
record actually contains. Question: **can the system currently be validated?**

Answer: **No.** The record has no exits.

## Method

Read-only aggregation over `docs/paper_trades/*.csv` (7 files, 31 data rows;
`TEMPLATE.csv` excluded). No source files changed. Repro script:
`%TEMP%\opencode\audit_paper_trades.py`.

Files: `2026-09-03, 09-05, 09-06, 09-09, 09-10, 09-12, 09-15` (31 rows total).

---

## Finding 1 - The loop has no exit (BLOCKER)

CSV columns: `date_entered, symbol, sector, action, entry_price, stop_loss,
target_1, target_2, position_size_pct, confluence_count, signal_at_entry, notes`.

Outcome columns present: **NONE**.

- Exits recorded: **0 / 31**
- Closed trades: **0**
- R-multiples computable: **0**

`docs/PAPER_TRADING/README.md` Step 4 instructs the operator to "update the CSV
with current price / status" - **not one row was ever updated.**

**Consequence:** win rate, expectancy, profit factor, average R, and hit rate are
all **not computable**. Any review engine or adherence dashboard we build reads an
empty record. A review loop cannot exist without an exit.

---

## Finding 2 - Geometry fails the system's own gate

n = 30 rows with valid `entry > stop` and a `target_1` (VZ has no stop).

| Metric | Value |
|---|---|
| min R:R | 0.43 (TARS) |
| median R:R | 1.53 |
| mean R:R | 1.61 |
| max R:R | 3.99 (BULL) |

| Threshold | Pass | % |
|---|---|---|
| R:R >= 2.5 (**blueprint floor**) | **2 / 30** | **7%** |
| R:R >= 2.0 (README upper) | 8 / 30 | 27% |
| R:R >= 1.5 (README lower) | 15 / 30 | 50% |
| R:R <= 1.0 (reward <= risk) | 6 / 30 | 20% |
| R:R exactly 1.00 | 4 / 30 | - |

Worst geometry: **TARS 0.43:1, T 0.51:1, SLDE 0.54:1**.

Stop distance as % of entry got as wide as **30.6% (GWRE), 22.8% (BULL),
20.9% (TARS), 17.9% (SLDE), 17.4% (INTC)** - far beyond any swing-trade stop.

Missing stop: **1 (VZ)** - a merger arb with capped upside.

**Doc drift discovered:** the operating manual contradicts the elite standard and
the code:

| Source | R:R threshold |
|---|---|
| `ELITE_SWING_TRADING_BLUEPRINT.md` | 2.5:1 |
| `frontend/src/workflow/gate.ts` (`RISK_REWARD_PASS`) | 2.5 |
| `docs/PAPER_TRADING/README.md` Step 2 | **"at least 1.5-2x"** |

The README silently relaxed the bar by ~40%. Even at 1.5x, **15/30 fail**.

> The gate we planned would reject **~93%** of the trades the system actually
> shipped.

---

## Finding 3 - Sizing is decoupled from conviction, and inverted

31 rows; sizes range **3.3% to 16.5%**, median 9.4%.

- Violations of the 5% single-name cap: **29 / 31 (94%)**
- Distinct sizes within conviction = 3: **7** `{3.3, 6.8, 8.0, 8.8, 9.4, 11.2, 16.5}`
- Distinct sizes within conviction = 5: **5** `{5.0, 8.0, 9.4, 15.0, 16.5}`

Same day (2026-09-03), same conviction (3):

| Symbol | Conviction | Size |
|---|---|---|
| BULL | 3 | **3.3%** |
| PAGP | 3 | **16.5%** |
| SLDE | 3 | **16.5%** |
| GNW | 3 | **16.5%** |
| LNG | 3 | **16.5%** |
| ZETA | 3 | 8.8% |
| DOCU | 3 | 8.8% |

**5x spread at identical conviction.** Worse - the allocation is *inverted*:
- **BULL** had the best R:R in the book (**3.99**) and received the **smallest**
  allocation (3.3%).
- **GWRE** had R:R 1.31 with a **30.6%** stop distance and received 8.8%.

Size is not a function of quality. There is no sizing rule.

---

## Finding 4 - Concentration; gate step 6 has no data to run on

| Sector | Rows |
|---|---|
| Technology | 13 |
| Energy | 12 |
| Financial Services | 2 |
| Healthcare | 2 |
| Communication Services | 2 |

**25 / 31 (81%) in two sectors.** 31 rows across only **20 distinct symbols**.

Repeated symbols: `DOCU x3, CVX x3, PSX x3, VLO x3, MU x3, INTC x2`.

Pyramiding into the same stop:

| Symbol | Entries | Same stop? |
|---|---|---|
| MU | 944.36 -> 971.31 -> 971.60 | **yes (883.17)** |
| PSX | 243.66 -> 245.53 -> 243.90 | **yes (232.38)** |
| VLO | 354.53 -> 356.82 -> 354.51 | **yes (333.32)** |
| INTC | 99.72 -> 102.56 | **yes (84.71)** |
| DOCU | 61.30 -> 60.67 -> 63.35 | no (56.70 / 58.44) |
| CVX | 211.32 -> 201.73 -> 208.60 | no (203.46 / 190.96 / 200.82) |

MU was added **higher, three times, against an unchanged stop** - the cluster's
downside compounds while per-trade R:R decays (2.21 -> 1.45 -> 1.27).

**Consequence:** Portfolio Fit (gate step 6) requires current position state.
No position state exists anywhere, so this step cannot be enforced today.

---

## Finding 5 - The system never says NO

| Action | Rows |
|---|---|
| STRONG BUY | 17 |
| ACCUMULATE | 11 |
| BUY | 3 |
| HOLD / WATCH / AVOID | **0** |

31/31 rows are bullish. **Rejections recorded: 0.**

A filter that never rejects is not a filter. These are a *candidate dump*, not
trades - selection (the source of alpha) is entirely absent.

**Contributing cause found in the docs.** The committed
`docs/PAPER_TRADING/README.md` "First day checklist" used to require a human
selection step:

```
- [ ] Pick 1-2 that match your conviction
```

An **uncommitted** working-tree edit replaced it with:

```
- [ ] Look at the candidates, drop the ones you don't want
```

so the checklist no longer asks the operator to *choose* - and the preferred
"script path" section added in the same uncommitted edit writes **all** candidates
above the conviction floor. The selection step was not merely skipped in practice;
it was being removed from the documented process at the same time. Also note the
README's own R:R guidance (line 41, committed) says *"At least **1.5-2x** the stop
distance"* versus the 2.5:1 in the blueprint and `gate.ts` (see Finding 2).

---

## Finding 6 - Dangerous flags shipped as BUY in the same string

| Contradiction | Rows | Examples |
|---|---|---|
| RSI overbought (71.2 - 78.9) | **11** | SLDE 72.8, GNW 71.2, VLO 75.3, TARS 78.9 |
| Extreme valuation | **4** | GWRE P/E 110, INTC P/E 50.3, DOCU P/E 41.7 |
| "yfinance D/E appears incorrect" | **10** | PAGP 56.39, LNG 243.42, CVX 18.96, MU 6.33 |
| `+nan% today` sector confirmation | 5 | "leading sector XLE (+nan% today) confirms risk-on" |
| Merger arb as swing trade | 1 | VZ: "deal spread provides near-risk-free return", **no stop** |

The system surfaces the danger in the *same* `notes` field as the buy call, then
ships the buy anyway. BULL was flagged *"Extreme volatility regime - widen stops
significantly"*. The "risk-on confirmed" line was backed by a **NaN**.

---

## Finding 7 - Cadence

`13, 5, 4, 3, 2, 2, 2` entries per run.

Day 1 dumped the entire watchlist (13 names), then it decayed. Weekday gaps
(09-04, 09-08, 09-11) - not even a daily process. No steady-state cadence.

---

## Consequence - measurement before enforcement

We were about to design disciplined execution of an unproven signal, graded by a
metric that cannot detect failure, over a record with no outcomes. The order must
invert:

**close the loop (capture exits) -> measure edge -> then enforce the gate.**

The gate should be designed from *what actually went wrong* (Findings 2-6), not
from the blueprint's wishlist.

---

## Proposed exit-capture schema (v0 - PENDING APPROVAL)

Extend the paper-trade row (additive; existing columns unchanged) so outcomes are
recorded and R is computable:

| Column | Type | Purpose |
|---|---|---|
| `date_closed` | `YYYY-MM-DD` | when the position ended |
| `exit_price` | float | realized exit |
| `exit_reason` | enum: `stop / target_1 / target_2 / trail / time_stop / thesis_break / manual` | why it ended |
| `shares` | int | actual size taken (replaces `position_size_pct` guesswork) |
| `realized_r` | float | (exit - entry) / (entry - stop), signed |
| `pnl_usd` | float | optional, for account-level curve |
| `max_favorable_excursion_r` | float | optional - how far it ran (did we exit too early?) |
| `max_adverse_excursion_r` | float | optional - how close to stop (was the stop too wide?) |
| `plan_adherence` | enum: `followed / partial / broke` | process metric, NOT the success metric |

Also required: a **rejection log** (every candidate the gate said NO to, with the
failing step) - otherwise Finding 5 can never improve and the gate's true
rejection rate is unmeasurable.

North-star metric is **expectancy / profit factor**, not adherence.
Adherence is a *process* metric; a perfectly adhered-to bad plan still loses.

---

## Decisions recorded this session

1. **Measure before enforce.** Run the evidence audit first; design the gate from
   its findings. (Was about to build the gate on an unmeasurable record.)
2. **Assume 1-2 touchpoints/day, not 4.** A working professional cannot work the
   blueprint's 6:00 / 9:30 / 12:00 / 4:15 clock. Design for a pre-market decision
   (bracket orders placed, executing unattended) + an after-close journal. This
   collapses the planned 4-stage mission.

## Next

1. Approve/amend the exit-capture schema above.
2. Retro-fill the outcome columns for the 31 open rows (where now known).
3. Then design the 7-step gate against Findings 2-6, with the rejection log.
4. Fix `docs/PAPER_TRADING/README.md` drift (1.5x -> 2.5x) - or consciously lower
   `RISK_REWARD_PASS` and say so. Do not leave the two disagreeing.

## Verification

- All figures reproducible via `audit_paper_trades.py` against the 7 CSVs.
- No application source modified; no tests run (analysis + docs/process only).

---

## Executed (same session)

All three approved actions carried out. Decision record:
[D-50](../DECISIONS/D-50-paper-trade-exit-capture-schema.md).

### 1. Exit-capture schema implemented (approved as-is)

- `docs/paper_trades/TEMPLATE.csv` -> **21 columns** (12 entry columns unchanged
  + 9 outcome columns: `date_closed, exit_price, exit_reason, shares,
  realized_r, pnl_usd, mfe_r, mae_r, plan_adherence`).
- `docs/paper_trades/REJECTIONS.csv` -> new rejection log (`date_seen, symbol,
  sector, action, conviction, failed_step, gate_verdict, reason, notes`).

### 2. The 31-row bypass cohort voided

- All 7 CSVs moved to `docs/paper_trades/archive/2026-09-bypass-path-voided/`,
  retained byte-for-byte.
- `archive/2026-09-bypass-path-voided/README.md` documents why they are excluded
  from every win-rate / expectancy / adherence calculation.
- `docs/paper_trades/` now holds only `TEMPLATE.csv` + `REJECTIONS.csv` - the
  loop restarts clean at the first run against the new schema.
- Verified inert: grep for `paper_trades` across `*.py` returned no matches, so
  no code reads that directory.

### 3. README drift fixed (7 corrections)

- **Line 41:** `1.5-2x` -> **2.5:1**, matching `gate.ts` and the blueprint.
- **Step 1:** deprecated `daily_morning_ritual.py` (its filter names no longer
  exist in the schema) -> `paper_trade_from_brief.py`.
- **Step 4:** "Monitor and update" -> **"Close the loop - record the exit"**,
  documenting the 9 outcome columns and stating that an open position must stay
  open and never be duplicated into a new day's file (the root cause of this
  audit).
- **Step 5:** weekly review now asks for **expectancy** and **profit factor**,
  adds a review of `REJECTIONS.csv`, an explicit **kill criterion**
  (expectancy <= 0 after 30+ closed trades), and a **minimum-sample rule**
  (~30 closed trades per pattern).
- **Checklist:** restored **"Pick 1-2 that match your conviction"**; added the
  exit-capture reminder.
- **Script section:** added a **KNOWN GAP** warning that the script writes every
  candidate and bypasses the gate.
- **File layout:** corrected - it listed `SESSIONS/paper_trades/`; the real path
  is `docs/paper_trades/`.

## Still open (deliberately not addressed here)

- The gate is **not enforced** in `paper_trade_from_brief.py`; the script can
  still emit unvalidated candidate dumps.
- **No position state exists**, so gate step 6 (Portfolio Fit) stays
  unenforceable. Position tracking is a prerequisite, not a Phase-2 extra.
- The **4-stage clock mission** still needs collapsing to 1-2 touchpoints
  (decided in D-50; design not done).
- **`D-49`** (cp1252 + `+nan%` fixes) still has no formal decision record; the
  number is reserved in `docs/DECISIONS/index.md`.
