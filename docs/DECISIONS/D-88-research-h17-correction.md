# D-88: H-17 ETF trend study correction (F7-F10)

**Date:** 2026-11-24
**Status:** Recorded. Exploratory only.
**Branch:** `research/baseline-backtesting`
**Commits:**

| Task | Commit | Message |
|---|---|---|
| F7 | `8ef939b92cbec8226d7d66d2e3e24e841286f4f7` | `docs (research): H-17 correction protocol and housekeeping (F7)` |
| F7 | `fb73c3a9efc19807ad1762c5b448a35950b7e574` | `docs(log): record H-17 correction protocol hash` |
| F8 | `19176e2ebc3eacd41cd25470b84069f396cb8932` | `research: fix H-17 execution timing and bootstrap CAGR; add tests (F8)` |
| F9 | `fd32f4e027754fac56ab1aeb7b174d45b4dddad2` | `research: H-17 corrected run (F9)` |
| F10 | `<this commit>` | `docs (research): record D-88 H-17 correction (F10)` |

**Related:** [D-87](D-87-research-etf-momentum-trend-h17.md), [H17_CORRECTION_PROTOCOL.md](../backtests/research/H17_CORRECTION_PROTOCOL.md), [ETF_TREND_STUDY_H17.md](../backtests/research/ETF_TREND_STUDY_H17.md), [ETF_TREND_STUDY_H17_CORRECTED.md](../backtests/research/ETF_TREND_STUDY_H17_CORRECTED.md), [ETF_DATA_QUALITY.md](../backtests/research/ETF_DATA_QUALITY.md), [PREREGISTRATION-H-17-v1.md](../backtests/research/PREREGISTRATION-H-17-v1.md), [HYPOTHESIS_LOG.md](../backtests/HYPOTHESIS_LOG.md), [research-etf-log.md](../SESSIONS/research-etf-log.md).

---

## 1. Why the correction was made

Review of commits `5057888..06929ac` found two real defects in the H-17 ETF study (copied from [H17_CORRECTION_PROTOCOL.md](../backtests/research/H17_CORRECTION_PROTOCOL.md)):

1. **Execution timing in `simulate()`** — `backend/app/research/etf_trend.py`, `simulate()` (line 272). Frozen spec: execute at the close of `s+1`; new weights earn returns from the close of `s+1` to the close of `s+2` onward. The code lets the new weights earn the close-`s` to close-`(s+1)` return. The unit test cannot detect it (the price is flat on `s+1`).
2. **Bootstrap CAGR uses shuffled sample elapsed time** — `backend/app/research/etf_trend.py`, `paired_month_bootstrap()` (line 476). `paired_month_bootstrap` computes CAGR for each resample from the first and last date of a shuffled sample, so the CAGR-difference CI is meaningless (`[-49.5, 0.0]`). Sharpe-diff and MaxDD-ratio CIs are not affected.

## 2. Correction rules (frozen before corrected run)

Copied from [H17_CORRECTION_PROTOCOL.md](../backtests/research/H17_CORRECTION_PROTOCOL.md):

- On the execution day `s+1` the PREVIOUS weights earn that day's close-to-close return. Weights are drifted to the close of `s+1` using the gross portfolio return of that day: `w_i <- w_i*(1+r_i)/(1+r_gross)`.
- Then, at the close of `s+1`, the portfolio trades to the target. Cost = `(cost_bps/10000) * sum` over all assets incl. SHY of `|w_target_i - w_drifted_i|`, and it is subtracted from the `s+1` portfolio return (reported return on `s+1` = gross return of the previous weights minus cost).
- The new weights (target) earn returns from the close of `s+1` to the close of `s+2` onward and are drifted on later days with each day's gross return.
- Turnover on `s+1` = `0.5 * sum|w_target_i - w_drifted_i|`.
- CAGR inside `paired_month_bootstrap`: every resample uses the same elapsed-years value as the original aligned window, `years = (last date - first date).days / 365.25` of the original aligned series, passed to `metrics()` through a new optional argument `years` (default `None` keeps all existing behaviour). Sharpe and max drawdown inside the bootstrap are unchanged. Seed `17000` and `2000` resamples are unchanged.
- Tier A stays strict: `abs(MaxDD_strategy) < 0.6 * abs(MaxDD_SPY)` AND `Sharpe_strategy >= Sharpe_SPY` (this is what the frozen pre-registration file says). Tier B stays `CAGR_strategy > CAGR_SPY` (equal is not a pass).
- Nothing else changes: same universe, signals, momentum, trend filter, top 5, `cost_bps 10`, windows, comparators, snapshot and manifest.

Verdict rules (frozen before corrected run):

- The original F5 run is retained unchanged and labelled "as-run: implementation deviated from the frozen spec (execution timing) and CAGR CI invalid". It is superseded for the H-17 verdict.
- Exactly ONE corrected run is allowed (task F9). Its Tier A/Tier B result is the H-17 verdict, whatever it is.
- If the corrected run changes either tier flag compared with the as-run result, the record must say "verdict changed by the correction" and the result must be labelled EXPLORATORY, post-correction; the pass action stays "record as a hypothesis only; next step a forward paper test"; no live change.
- No second corrected run, no parameter change and no comparator promotion for any reason. Any new variant needs a new H-id and a new pre-registration.

## 3. Corrected result (F9, copied verbatim from ETF_TREND_STUDY_H17_CORRECTED.md)

**Run metadata (from report):** Run label `F9-corrected`, generated UTC `2026-11-25T01:33:46.426750+00:00`, code revision `19176e2ebc3eacd41cd25470b84069f396cb8932`, dirty `False`, prereg sha256 `3a1300d840592287f28fcc0442f84609118878e9fd53a98a1aee3f4dff1f12af`, snapshot manifest sha256 `c0bb469785aa64679f3b8f48e17f7ee42584d2d049a88b1a6b2b316f19aa9304`, correction protocol sha256 `442e721d3b17821569a631e296167453842405b0b7c7a5da6cc3534c9f94fb44`.

### Primary strategy — Tier A/B (holdout)

- Tier A: **False**
- Tier B: **False**
- Four-way label: **neither**

### Holdout point estimates and CIs (primary vs SPY)

| Metric | Point | 95% month-block CI | CI includes zero/1? |
|---|---:|---:|---:|
| Sharpe diff (strategy-SPY) | -0.1827 | [-0.5862, 0.1856] | True |
| CAGR diff (strategy-SPY) | -0.0547 | [-0.1241, 0.0086] | True |
| MaxDD magnitude ratio (strategy/SPY) | 0.6076 | [0.5270, 1.3855] | True |

### Holdout comparator table

| Strategy | CAGR | Sharpe | MaxDD | Calmar | Ann turnover | Share days SHY |
|---|---:|---:|---:|---:|---:|---:|
| primary_cost_10 | 8.66% | 0.6495 | -20.49% | 0.4225 | 3.3244 | 0.77% |
| top3 | 7.98% | 0.5487 | -21.81% | 0.3656 | 3.9408 | 0.77% |
| top8 | 8.30% | 0.6962 | -20.38% | 0.4070 | 2.7619 | 0.77% |
| trend_only | 8.82% | 0.7590 | -19.79% | 0.4459 | 2.7574 | 0.77% |
| momentum_no_trend | 10.44% | 0.7083 | -21.49% | 0.4858 | 2.8922 | 0.00% |
| primary_cost_0 | 9.38% | 0.6954 | -20.40% | 0.4599 | 3.3244 | 0.77% |
| primary_cost_25 | 7.58% | 0.5802 | -20.62% | 0.3674 | 3.3244 | 0.77% |
| spy_ief_60_40 | 9.10% | 0.8832 | -21.18% | 0.4294 | 0.1084 | 0.00% |
| equal_weight_19 | 10.59% | 0.8178 | -28.65% | 0.3696 | 0.1621 | 0.00% |
| spy_buy_hold | 14.12% | 0.8322 | -33.72% | 0.4189 | 0.0000 | 0.00% |

## 4. As-run (F5) vs corrected (F9), primary strategy

| Window | Run | CAGR | Sharpe | MaxDD | Calmar | Ann turnover | Share days SHY |
|---|---|---:|---:|---:|---:|---:|---:|
| Dev (2005-01-01..2015-12-31) | as-run (F5) | 9.84% | 0.7021 | -24.76% | 0.3974 | 3.0842 | 0.00% |
| Dev (2005-01-01..2015-12-31) | corrected (F9) | 9.38% | 0.6742 | -25.66% | 0.3656 | 3.0865 | 0.00% |
| Holdout (2016-01-01..2026-11-23) | as-run (F5) | 8.76% | 0.6582 | -23.02% | 0.3805 | 3.3166 | 0.77% |
| Holdout (2016-01-01..2026-11-23) | corrected (F9) | 8.66% | 0.6495 | -20.49% | 0.4225 | 3.3244 | 0.77% |

Tier flag comparison (holdout, primary vs SPY): Tier A same (False). Tier B same (False). Four-way label same (neither). **No tier flag changed by the correction.**

## 5. Limits

- The 19 ETFs were chosen in 2026 from survivors (ETF survivorship is mild but not zero); 2005-2015 includes 2008; one universe, one sample path, ~21 years; yfinance data; costs are a flat assumption; no taxes; in-sample for the strategy family (12-1 momentum and a 200-day trend filter are literature defaults, not fitted here, but the author has seen general market history). No walk-forward.
- The original F5 run is retained unchanged and labelled "as-run: implementation deviated from the frozen spec (execution timing) and CAGR CI invalid". It is superseded for the H-17 verdict by this corrected run (F9).
- EXPLORATORY. Never the scorecard, D-75 pass bar, kill rule or forward verdict. No live decision, no parameter change, no comparator promotion. Any new variant needs a new H-id and a new pre-registration.
