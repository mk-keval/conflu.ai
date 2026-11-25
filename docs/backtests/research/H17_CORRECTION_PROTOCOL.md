# H-17 Correction Protocol (F7)

**Date:** 2026-11-24  
**Branch:** `research/baseline-backtesting`  
**Scope:** Correction protocol for H-17 ETF momentum + trend filter study. Written and committed BEFORE any code changes. No strategy parameter, universe, window, cost, snapshot, or pass rule changes.

## a) Defects

Two real defects were found in the H-17 ETF study (commits `5057888..06929ac`):

1. **Execution timing in `simulate()`** — `backend/app/research/etf_trend.py`, `simulate()` (line 272). Frozen spec: execute at the close of `s+1`; new weights earn returns from the close of `s+1` to the close of `s+2` onward. The code lets the new weights earn the close-`s` to close-`(s+1)` return. The unit test cannot detect it (the price is flat on `s+1`).

2. **Bootstrap CAGR uses shuffled sample elapsed time** — `backend/app/research/etf_trend.py`, `paired_month_bootstrap()` (line 476). `paired_month_bootstrap` computes CAGR for each resample from the first and last date of a shuffled sample, so the CAGR-difference CI is meaningless (`[-49.5, 0.0]`). Sharpe-diff and MaxDD-ratio CIs are not affected.

## b) Frozen corrected behaviour

- On the execution day `s+1` the PREVIOUS weights earn that day's close-to-close return. Weights are drifted to the close of `s+1` using the gross portfolio return of that day: `w_i <- w_i*(1+r_i)/(1+r_gross)`.
- Then, at the close of `s+1`, the portfolio trades to the target. Cost = `(cost_bps/10000) * sum` over all assets incl. SHY of `|w_target_i - w_drifted_i|`, and it is subtracted from the `s+1` portfolio return (reported return on `s+1` = gross return of the previous weights minus cost).
- The new weights (target) earn returns from the close of `s+1` to the close of `s+2` onward and are drifted on later days with each day's gross return.
- Turnover on `s+1` = `0.5 * sum|w_target_i - w_drifted_i|`.
- CAGR inside `paired_month_bootstrap`: every resample uses the same elapsed-years value as the original aligned window, `years = (last date - first date).days / 365.25` of the original aligned series, passed to `metrics()` through a new optional argument `years` (default `None` keeps all existing behaviour). Sharpe and max drawdown inside the bootstrap are unchanged. Seed `17000` and `2000` resamples are unchanged.
- Tier A stays strict: `abs(MaxDD_strategy) < 0.6 * abs(MaxDD_SPY)` AND `Sharpe_strategy >= Sharpe_SPY` (this is what the frozen pre-registration file says). Tier B stays `CAGR_strategy > CAGR_SPY` (equal is not a pass).
- Nothing else changes: same universe, signals, momentum, trend filter, top 5, `cost_bps 10`, windows, comparators, snapshot and manifest.

## c) Verdict rules (frozen now, before the corrected run)

- The original F5 run is retained unchanged and labelled "as-run: implementation deviated from the frozen spec (execution timing) and CAGR CI invalid". It is superseded for the H-17 verdict.
- Exactly ONE corrected run is allowed (task F9). Its Tier A/Tier B result is the H-17 verdict, whatever it is.
- If the corrected run changes either tier flag compared with the as-run result, the record must say "verdict changed by the correction" and the result must be labelled EXPLORATORY, post-correction; the pass action stays "record as a hypothesis only; next step a forward paper test"; no live change.
- No second corrected run, no parameter change and no comparator promotion for any reason. Any new variant needs a new H-id and a new pre-registration.

## d) Known gap (docs only, no code change)

Tiingo return comparison for IWM was `0.025121` (> `0.02`), which the F1 rule treats as WARN; `ETF_DATA_QUALITY.md` does not list it. This is stated here and in the addendum appended to `ETF_DATA_QUALITY.md` (F7). The snapshot is not regenerated.
