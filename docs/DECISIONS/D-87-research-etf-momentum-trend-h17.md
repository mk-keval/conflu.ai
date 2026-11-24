# D-87: ETF momentum + trend filter pre-registered study (H-17)

**Date:** 2026-11-24
**Status:** Recorded. Exploratory only. Phase 4 (F0-F6) added a frozen 20-ETF snapshot, pure data-quality checks, a frozen pre-registration, a pure study module + synthetic tests + script, and one real run on the frozen snapshot. No live decision changed and no pass bar moved.
**Branch:** `research/baseline-backtesting`
**Commits:**

| Task | Commit | Message |
|---|---|---|
| F0 | `5057888`, `9247522` | F0 start log/gates (recorded in work log) |
| F1 | `d479514` | `research: add ETF snapshot data-quality checks (F1)` |
| F2 | `630b977` | `research: freeze ETF snapshot and data-quality report (F2)` |
| F3 | `90dab04386761a68d4cc6de756d9354cb4b0be18`, `8dbd478` | `docs (research): pre-register H-17 ETF momentum + trend filter (F3)` / hash record |
| F4 | `ea6411e` | `research: add ETF trend study module, tests and script (F4)` |
| F5 | `e28b31d` | `research: run H-17 ETF trend study (F5)` |
| F6 | `<this commit>` | `docs (research): record H-17 ETF trend study outcome (F6)` |

**Related:** [PREREGISTRATION-H-17-v1.md](../backtests/research/PREREGISTRATION-H-17-v1.md), [ETF_DATA_QUALITY.md](../backtests/research/ETF_DATA_QUALITY.md), [ETF_TREND_STUDY_H17.md](../backtests/research/ETF_TREND_STUDY_H17.md), [HYPOTHESIS_LOG.md](../backtests/HYPOTHESIS_LOG.md), [D-84](D-84-research-signal-information-and-exit-shape.md), [D-85](D-85-research-vol-matched-remeasurement.md), [D-86](D-86-research-pre2016-check-and-survivorship-estimate.md), [research-etf-log.nd](../SESSIONS/research-etf-log.nd).

---

## 1. Why this was run

Phase 4 tested one pre-registered ETF momentum + trend filter (H-17) on a frozen 20-ETF survivor universe. The question was narrow: on a 2016-onward holdout, does the frozen strategy meet a drawdown bar (Tier A) or a return bar (Tier B) against SPY buy-and-hold, net of 10 bps cost? The study is EXPLORATORY; a pass would only justify a forward paper test, not a live change.

## 2. Pre-registration (frozen before code/run)

- Pre-registration: `docs/backtests/research/PREREGISTRATION-H-17-v1.md` (frozen 2026-11-24, commit `90dab04386761a68d4cc6de756d9354cb4b0be18`; hash recorded in work log `8dbd478`).
- Snapshot: `research_data/etf_20261124/`, manifest sha256 `c0bb469785aa64679f3b8f48e17f7ee42584d2d049a88b1a6b2b316f19aa9304` (from `ETF_DATA_QUALITY.md`). No re-download for the run.
- Primary strategy (frozen): 19 risk ETFs + SHY cash; signal last SPY trading day of month; eligible >=253 Adj Close bars through s; momentum `AdjClose[s-21]/AdjClose[s-252]-1`; trend `AdjClose[s] > mean(last 200 Adj Close through s)`; top 5 by momentum, ties alphabetical; 1/5 weight per selected slot, unfilled slots in SHY; execute close of s+1; new weights earn returns from close of s+1 to s+2 onward; weights drift `w_i <- w_i*(1+r_i)/(1+r_p)`; execution-day cost `(cost_bps/10000)*sum|w_target-w_drifted|` subtracted from that day’s portfolio return; primary cost_bps 10.
- Primary bars (holdout, net cost_bps=10): Tier A = `abs(MaxDD_strategy) < 0.6 * abs(MaxDD_SPY)` AND `Sharpe_strategy >= Sharpe_SPY`; Tier B = `CAGR_strategy > CAGR_SPY` (strict, equal not pass). Four-way label reported: A only / B only / both / neither.
- Bootstrap (descriptive): 95% month-block bootstrap CI, 2000 resamples, seed 17000, whole calendar months of paired daily returns resampled with replacement, for Sharpe diff, CAGR diff, and MaxDD magnitude ratio `abs(MaxDD_strategy)/abs(MaxDD_SPY)`. CI including zero/1 means the bar, if met on point estimates, is not statistically distinguishable.

## 3. Data and provenance

| Item | Value |
|---|---|
| Snapshot | `research_data/etf_20261124/` (20 csv.gz + manifest.json) |
| Manifest sha256 | `c0bb469785aa64679f3b8f48e17f7ee42584d2d049a88b1a6b2b316f19aa9304` |
| Prereg | `docs/backtests/research/PREREGISTRATION-H-17-v1.md` |
| Prereg sha256 | `3a1300d840592287f28fcc0442f84609118878e9fd53a98a1aee3f4dff1f12af` |
| Run code revision | `ea6411e5993e312e389f6f6a1df03b64e01b1c5e` |
| Dirty | `False` |
| Dev window | 2005-01-01..2015-12-31 (reported only) |
| Holdout window | 2016-01-01..2026-11-23 (latest snapshot date) |
| Script | `python scripts/research_etf_trend.py --snapshot-dir research_data/etf_20261124 --prereg docs/backtests/research/PREREGISTRATION-H-17-v1.md --report docs/backtests/research/ETF_TREND_STUDY_H17.md --json-dir docs/backtests/research/etf_trend` |
| Report | `docs/backtests/research/ETF_TREND_STUDY_H17.md` |
| JSON | `docs/backtests/research/etf_trend/etf_trend_20261124_152807.json` |

## 4. Holdout primary result (copied from report)

| Item | Value |
|---|---|
| Tier A | **False** |
| Tier B | **False** |
| Four-way label | **neither** |

95% month-block bootstrap CIs (2000 resamples, seed 17000):

| Metric | Point | 95% month-block CI | CI includes zero/1? |
|---|---:|---:|---:|
| Sharpe diff (strategy-SPY) | -0.1740 | [-0.5489, 0.1777] | True |
| CAGR diff (strategy-SPY) | -0.0536 | [-49.5462, 0.0000] | True |
| MaxDD magnitude ratio (strategy/SPY) | 0.6827 | [0.5423, 1.3605] | True |

The pre-registered bars were not met. CIs include zero/1, so point differences are not statistically distinguishable.

## 5. Holdout comparators (descriptive, copied from report)

| Strategy | CAGR | Sharpe | MaxDD | Calmar | Ann turnover | Share days SHY |
|---|---:|---:|---:|---:|---:|---:|
| primary_cost_10 | 8.76% | 0.6582 | -23.02% | 0.3805 | 3.3166 | 0.77% |
| top3 | 8.28% | 0.5675 | -23.63% | 0.3506 | 3.9392 | 0.77% |
| top8 | 8.28% | 0.6996 | -20.32% | 0.4077 | 2.7549 | 0.77% |
| trend_only | 8.81% | 0.7621 | -20.97% | 0.4203 | 2.7551 | 0.77% |
| momentum_no_trend | 10.38% | 0.7055 | -23.24% | 0.4466 | 2.8846 | 0.00% |
| primary_cost_0 | 9.48% | 0.7043 | -22.90% | 0.4139 | 3.3156 | 0.77% |
| primary_cost_25 | 7.69% | 0.5888 | -23.20% | 0.3314 | 3.3184 | 0.77% |
| spy_ief_60_40 | 9.02% | 0.8742 | -21.28% | 0.4239 | 0.0992 | 0.00% |
| equal_weight_19 | 10.52% | 0.8117 | -28.77% | 0.3655 | 0.1563 | 0.00% |
| spy_buy_hold | 14.12% | 0.8322 | -33.72% | 0.4189 | 0.0000 | 0.00% |

Comparators are descriptive only, not pass cells.

## 6. Primary per-year returns and stress drawdowns (copied from report)

| Year | Return | Days |
|---:|---:|---:|
| 2003 | 2.61% | 252 |
| 2004 | 15.02% | 252 |
| 2005 | 18.25% | 252 |
| 2006 | 21.49% | 251 |
| 2007 | 12.74% | 251 |
| 2008 | -12.68% | 253 |
| 2009 | 22.15% | 252 |
| 2010 | 5.65% | 252 |
| 2011 | -4.15% | 252 |
| 2012 | 4.23% | 250 |
| 2013 | 38.45% | 252 |
| 2014 | 12.31% | 252 |
| 2015 | -1.06% | 252 |
| 2016 | 4.56% | 252 |
| 2017 | 17.65% | 251 |
| 2018 | -3.60% | 251 |
| 2019 | 17.16% | 252 |
| 2020 | 9.79% | 253 |
| 2021 | 16.32% | 252 |
| 2022 | -9.56% | 251 |
| 2023 | 5.03% | 250 |
| 2024 | 17.81% | 252 |
| 2025 | 20.98% | 250 |
| 2026 | 3.84% | 225 |

| Period | Max drawdown (window equity restarts at 1.0) |
|---|---:|
| 2008 | -23.38% |
| 2020 | -23.02% |
| 2022 | -15.01% |

## 7. Evidence / gates

F4/F5 end gates (exact CI list/scope): `163 passed` and `All checks passed!` (ruff). F6 is docs-only; F6 start gates: `163 passed`, `All checks passed!`.

## 8. Deviations and limits

- **Authorized F2 deviation:** `check_adj_ratio` tolerance relaxed from 1e-6 to 1e-4 in `backend/app/research/data_quality.py` after investigation showed ~1e-6..1.6e-6 yfinance Adj Close/Close precision drift on non-dividend/non-split days. Explicit user authorization (Option 1), logged in work log and code docstring; no other check/threshold weakened.
- **Exploratory only.** The 19 ETFs were chosen in 2026 from survivors (ETF survivorship is mild but not zero); 2005-2015 includes 2008; one universe, one sample path, ~21 years; yfinance data; costs are a flat assumption; no taxes; in-sample for the strategy family (12-1 momentum and 200-day trend filter are literature defaults, not fitted here, but the author has seen general market history). No walk-forward.
- **No live decision.** Never the scorecard, D-75 pass bar, kill rule or any forward verdict. A pass would have meant “record as hypothesis only; next step forward paper test”; a fail means record and stop — no re-run with other parameters. Any new variant needs a new H-id and a new pre-registration.

## 9. Decision

Record H-17 as **EXPLORATORY, pre-registered, FAIL (neither Tier A nor Tier B on holdout)**.

- The frozen strategy did not meet Tier A (drawdown/Sharpe bar) or Tier B (CAGR bar) against SPY buy-and-hold on the 2016-onward holdout, net of 10 bps.
- Bootstrap CIs include zero/1, so differences are not statistically distinguishable.
- Do not tune, re-run with different parameters, or promote any comparator. Any new variant requires a new H-id and a new pre-registration.
- No live decision, scorecard, D-75 pass bar, kill rule, or forward verdict changes.