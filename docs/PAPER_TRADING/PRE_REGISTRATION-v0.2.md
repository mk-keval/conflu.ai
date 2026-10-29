# Pre-Registration — Forward Sample v0.2

> **SPEC FROZEN 2026-10-28 (D-77). NOT YET LIVE.** No row is stamped `v0.2`
> until the go-live commit flips `CURRENT_SAMPLE_VERSION`. The clock starts at
> the first fill after that commit, not at this document's date.

**Experiment ID:** `FWD-v0.2`
**Status:** Frozen — implementation in progress; go-live pending
**Registered:** 2026-10-28
**First actual fill:** not yet (go-live pending)
**Supersedes:** FWD-v0.1 — closed for verdict purposes 2026-10-28 (D-76); the
geometry it measured was incoherent (D-77)
**Journal of record:** `data/paper_trades.db`
**Scorecard:** [SCORECARD.md](SCORECARD.md)
**Frozen design:** [BUNDLE_A_EXIT_GEOMETRY.md](BUNDLE_A_EXIT_GEOMETRY.md)
**Decision record:** [D-77](../DECISIONS/D-77-bundle-a-exit-geometry.md)

---

## Question

Does the deployed screen → gate → pending-order → **family exit** pipeline
produce positive expectancy in R on real, tradeable forward fills when the gate
measures the first exit that actually pays?

## Change from the previous experiment

Exactly one bundle: **Bundle A** — target hierarchy, gate R:R on T1 from the
planned fill, family exit policy, and the dynamic management plan (P1-6, P1-7,
P1-8, P4-15). Screens, regime permission, ranking, sizing, stops and entry rules
are unchanged. Bundle B is a separate future version.

---

## Frozen design (no changes mid-sample)

| Area | Frozen rule |
|---|---|
| Screens / menus | `config/regime_screens.yaml` as deployed; no weight or menu changes |
| Regime permission | None — unchanged from v0.1; Bundle B |
| Conviction floor | `min_conviction = 5` on the brief ticker |
| Gate | 7-step gate; step 5d uses **Plan R to T1 from `entry_low`** with family floors: trend/breakout/unknown PASS ≥ 2.5R, half size 2.0–2.5R, fail < 2.0R; mean reversion PASS ≥ 1.5R, half 1.25–1.5R, fail < 1.25R; rotation PASS ≥ 2.0R, half 1.75–2.0R, fail < 1.75R |
| Target hierarchy | Nearest structural level above the half-size floor, capped by family max; T2/T3 are the next levels. No ATR/percentage fallback. No level in band → reject (`target too close` / `target too far` / `no structural objective`) |
| R:R measurement | `(T1 − entry_low) / (entry_low − stop_loss)`; `stretch_rr` = T3 R is context only |
| Sizing | 1% risk formula, 25% notional hard cap, 0.5% floor; CONDITIONAL × 0.5 |
| Portfolio caps | 8 open positions; 30% sector exposure; duplicate-symbol block |
| Time stop | Trend 30 calendar days, breakout 20, mean reversion 10, rotation 15, unknown 20; first session on/after the cutoff |
| Entry model | After-close signal → pending limit at `entry_low`; MOO optional; 3-session expiry |
| Fill timing | Only bars strictly after `signal_date`; no same-day fills (D-73) |
| Same-session exits | Fill-bar stop closes at −1R; fill-bar targets are ignored |
| Exit model | Trend 1/3 T1 + 1/3 T2 + 1/3 trailed; breakout 1/2 T1 + 1/2 trailed; mean reversion/rotation/unknown 100% at T1. Breakeven at +1R close; trail 2.0×ATR (trend) / 2.5×ATR (breakout), fallback 2×risk. Stop wins same-bar ties |
| Accounting | `exit_price` = share-weighted leg VWAP; `realized_r` = weighted leg R; `pnl_usd` = canonical net on the weighted exit and total shares; costs 10 bps fee + 5 bps slippage per side; R gross |
| Versioning | `sample_version = v0.2` on rows created after go-live; filled orders inherit their order's version; v0.1/interim never scored |

**Deliberately not fixed:** the number of candidates per day, the number of
fills, and the mix of screens. Those are outputs of the frozen pipeline.

---

## Endpoints and metrics

### Primary

**Expectancy in R** = `mean(realized_r)` over closed **scored** trades, where
`realized_r` is the weighted average leg R and is gross of costs.

### Secondary (reported, not decisive)

- Win rate; profit factor; average win R; average loss R.
- Net dollar P&L after costs; gross dollars; total costs.
- MFE gap (`mean(mfe_r − realized_r)`) and MFE capture.
- Per-family and per-template expectancy, descriptive only below 30 closed
  trades per cell.
- Execution diagnostics: fill rate, expiry vs cancel, same-session stop rate,
  exit-reason mix, partial-fill leg count.

### Pass bar (D-75, unchanged)

At **30+ closed scored trades**, pass when all three hold:

- expectancy **> 0 after costs**;
- profit factor **≥ 1.3**;
- average loss **≤ 1.0R**.

Win rate, average win, payoff ratio and MFE capture are reported, not gated.
The legacy "WR > 50% AND avg R > 0.5" bar was never applied.

**Risk circuit breaker:** 8R peak-to-trough drawdown → stop new entries and
review; 12R → kill. The kill rule (expectancy ≤ 0 at 30+ closes) is unchanged.

---

## Trigger and decision rules

**30 closed scored trades OR 6 weeks after the first scored fill, whichever
first.**

- **30 closed trades** is the statistical trigger. The expectancy kill rule can
  fire only here; the 12R breaker can fire at any time.
- **6 weeks after the first fill** is a calendar review. It fires even if the
  sample is small. Do not kill on expectancy at n < 30; report the wide interval.
- At the calendar review, decide only: continue the frozen sample, extend the
  calendar review, or stop for a documented operational reason (including a
  fired 12R breaker). Any design change starts a **new** sample.

## Exclusions

- Rows whose `sample_version` is not `v0.2` — v0.1 is closed and interim is loop
  data, never evidence.
- Voided rows, legacy `exclude_from_stats` rows, replay/backtest rows.
- Open positions and pending orders — not closed evidence.
- Counterfactual "would have" exits — not in the primary endpoint.

## Integrity gate

```bash
python scripts/verify_journal.py
python scripts/scorecard.py
```

Hard failures: phantom fill; canonical P&L mismatch; unknown sample version;
fill/row version mismatch; **v0.2 leg/VWAP/R mismatch**; **v0.2 plan-R gap**
(`plan_rr` vs `target_1_r` beyond tolerance). Warnings must be reported, not
silently fixed. A DB backup must exist before any write that changes journal
rows.

## Freeze and go-live protocol

1. **Spec freeze (this document + D-77):** `SCORED_SAMPLE_VERSION = "v0.2"`,
   `CURRENT_SAMPLE_VERSION = "interim"`. No v0.2 row exists.
2. **Implementation:** exit policy, synthesis, gate, schema, pending, sync,
   verifier, tests. The daily loop may continue; every new row is `interim`.
3. **Go-live:** all focused tests pass and `verify_journal.py` PASS; flip
   `CURRENT_SAMPLE_VERSION = "v0.2"`; record the go-live date here and set
   "first fill TBD"; the clock starts at the first fill after the commit.
4. **H-09 replay:** after go-live, exploratory only (`rules_version='v0.2'`),
   never evidence.

## Deviations log

| Date | Item | Type | Effect |
|---|---|---|---|
| 2026-10-28 | Bundle A spec frozen (D-77) | Pre-sample design | No v0.2 row exists; v0.1 rows untouched |
| 2026-10-28 | Band minimum lowered to the half-size floor | Internal consistency | Keeps the D1 half-size tier reachable; PASS floors unchanged |

## Change log

| Date | Change |
|---|---|
| 2026-10-28 | Created as the v0.2 pre-registration; Bundle A frozen, not yet live |
