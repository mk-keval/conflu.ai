# VISION — conflu.ai

> Single source of truth for *what we are building*, *what "working" means*, and *when to stop*.
> If a decision conflicts with this file, either the decision wins and this file gets updated on
> purpose — or the decision gets reversed. Created 2026-10-19, after the validation-reset audit.

Related documents:
- [`ELITE_SWING_TRADING_BLUEPRINT.md`](ELITE_SWING_TRADING_BLUEPRINT.md) — the institutional blueprint this system implements (process, risk, apprenticeship).
- [`docs/PAPER_TRADING/README.md`](docs/PAPER_TRADING/README.md) — the operating manual + scorecard rules.
- `docs/DECISIONS/` — ADR-style records of every consequential choice.

---

## Who it's for

A **working professional** (30–60 min/day, beginner to intermediate) who wants to swing trade
(multi-day to multi-week holds) without staring at charts. The system does the analysis; the user
makes the final call, learns while doing it, and never has to maintain a spreadsheet.

## The promise

conflu.ai is the user's **analyst, risk manager, and journal** — not their broker, and not a profit
guarantee.

1. **Find candidates** — Morning Brief picks screens per market regime from validated templates.
2. **Analyze deep** — per-ticker multi-timeframe technicals, structure, volume profile, SMC, macro
   overlay, earnings, fundamentals, sentiment → a verdict **plus a trade plan** (entry zone, stop,
   targets) whose geometry satisfies hard invariants (R:R floor, structural targets — never manufactured).
3. **Gate entry** — a 7-step validation gate rejects plans that fail risk, liquidity, or geometry
   checks. Every rejection is recorded — rejections are data, not noise.
4. **Track honestly** — one-click after-close run logs entries, applies exits, records rejections;
   `data/paper_trades.db` is the journal of record. Missed days stay honest gaps.
5. **Teach** — plain-English narration, Learn content, and a Journal that shows what actually happened.

## What "working" means (pre-registered — do not move these goalposts)

Primary metric: **expectancy in R** over closed journal trades.

| Rule | Value |
|---|---|
| Minimum sample before any pattern-level conclusion | **30+ closed trades per pattern** |
| Passing bar | hit rate **> 50%** AND average **R > 0.5** (after ≥ 20 closed trades) |
| Kill rule | **expectancy ≤ 0 after 30+ closed trades** → change it or stop. "Give it more time" requires a written reason. |
| Gate quality check | rejected candidates must **not** outperform accepted ones (review weekly) |
| Coverage | journal shows a run for every trading day in the observation window (missed days recorded as gaps) |

Weekly scorecard lives in the Journal tab (runs strip + trades + rejections) with a CSV export.

## What we will not promise

- **Profit.** No system can promise profit. The system's job is disciplined process, honest
  measurement, and fast iteration — the edge, if any, shows up in the journal and nowhere else.
- **Analysis depth = edge.** More modules ≠ more money. Depth is a hypothesis; the journal is the test.
- Intraday trading, options, leverage — out of scope for now. Paper, swings, long and short bias allowed.

## Non-goals — until the evidence loop has run

- No new analysis modules, templates, UI sections, or asset classes **until the journal has run
  ≥ 6 weeks and the scorecard exists**.
- No live-brokerage auto-execution.
- No template promotions/demotions without ≥ 30 closed trades behind the decision.

## How we keep the engine honest (validation rules)

1. **Live-verified only.** Every TradingView column name, interval behavior, and API claim is
   probe-verified against the live API before it lands (D-65 / D-67 / 2026-10-19 lessons).
2. **No silent skips.** A backtest filter that can't be evaluated (unknown indicator, missing data,
   unavailable timeframe) is *recorded as a deviation* — never silently counted as a pass.
3. **Backtest == live semantics.** Same filters, same timeframes, same exit model (stop / target /
   time cap) as the live plan — or the difference is listed in the report.
4. **Pre-declared windows & universes.** No mega-cap-only, survivorship-only, or hand-picked date
   ranges called "validation". Report the window, universe, and survivorship bias in the header.
5. **No look-ahead.** Signals at bar *t* use data only up to *t*; executions happen at the **next**
   bar's price. Exit logic may never read future signals.
6. **Red means red.** The test suite must be green on `main`-tracked branches; a known-failing test is
   fixed or explicitly quarantined with a linked issue — never tolerated.

## Current phase (as of 2026-10-19)

**Phase: Evidence.** The tooling to measure was completed (D-68 journal + one-click EOD run);
the validation harness was reset (look-ahead exits, dropped filters, and broken units fixed).
Next: run the loop daily, build the scorecard, prune or promote templates on data.
