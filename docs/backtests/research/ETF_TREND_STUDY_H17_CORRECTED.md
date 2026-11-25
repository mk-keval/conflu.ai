# ETF Trend Study H-17 (F9-corrected)

> EXPLORATORY — never the scorecard, D-75 pass bar, kill rule or any forward verdict.

## Run metadata

- Run label: `F9-corrected`
- Generated UTC: 2026-11-25T01:33:46.426750+00:00
- Code revision: `19176e2ebc3eacd41cd25470b84069f396cb8932`
- Dirty: `False`
- Prereg: `docs/backtests/research/PREREGISTRATION-H-17-v1.md`
- Prereg sha256: `3a1300d840592287f28fcc0442f84609118878e9fd53a98a1aee3f4dff1f12af`
- Snapshot dir: `research_data/etf_20261124`
- Manifest sha256: `c0bb469785aa64679f3b8f48e17f7ee42584d2d049a88b1a6b2b316f19aa9304`
- Correction protocol: `docs/backtests/research/H17_CORRECTION_PROTOCOL.md`
- Correction protocol sha256: `442e721d3b17821569a631e296167453842405b0b7c7a5da6cc3534c9f94fb44`

## Frozen limits

the 19 ETFs were chosen in 2026 from survivors (ETF survivorship is mild but not zero); 2005-2015 includes 2008; one universe, one sample path, ~21 years; yfinance data; costs are a flat assumption; no taxes; in-sample for the strategy family (12-1 momentum and a 200-day trend filter are literature defaults, not fitted here, but the author has seen general market history); EXPLORATORY, never the scorecard, D-75 pass bar, kill rule or any forward verdict. In-sample, survivorship-biased universe; no walk-forward.

## Primary strategy — Tier A/B (holdout)

- Tier A: **False**
- Tier B: **False**
- Four-way label: **neither**

## Holdout point estimates and CIs (primary vs SPY)

| Metric | Point | 95% month-block CI | CI includes zero/1? |
|---|---:|---:|---:|
| Sharpe diff (strategy-SPY) | -0.1827 | [-0.5862, 0.1856] | True |
| CAGR diff (strategy-SPY) | -0.0547 | [-0.1241, 0.0086] | True |
| MaxDD magnitude ratio (strategy/SPY) | 0.6076 | [0.5270, 1.3855] | True |

If a CI includes zero (or 1 for the ratio) the report must say the bar was met on point estimates and that the difference is not statistically distinguishable.

## Development window (2005-01-01..2015-12-31) — reported only

| Strategy | CAGR | Sharpe | MaxDD | Calmar | Ann turnover | Share days SHY |
|---|---:|---:|---:|---:|---:|---:|
| primary_cost_10 | 9.38% | 0.6742 | -25.66% | 0.3656 | 3.0865 | 0.00% |
| top3 | 9.14% | 0.6017 | -26.22% | 0.3486 | 3.6861 | 0.00% |
| top8 | 8.79% | 0.6848 | -22.46% | 0.3916 | 2.4231 | 0.00% |
| trend_only | 7.05% | 0.6064 | -30.98% | 0.2276 | 2.1464 | 0.00% |
| momentum_no_trend | 12.28% | 0.8268 | -20.05% | 0.6122 | 2.6651 | 0.00% |
| primary_cost_0 | 10.06% | 0.7154 | -25.14% | 0.4001 | 3.0865 | 0.00% |
| primary_cost_25 | 8.37% | 0.6121 | -26.44% | 0.3166 | 3.0865 | 0.00% |
| spy_ief_60_40 | 6.82% | 0.6643 | -32.17% | 0.2120 | 0.1253 | 0.00% |
| equal_weight_19 | 7.89% | 0.5509 | -44.89% | 0.1757 | 0.1675 | 0.00% |
| spy_buy_hold | 7.02% | 0.4397 | -55.19% | 0.1272 | 0.0000 | 0.00% |

## Holdout window (2016-01-01..latest) — primary

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

## Primary strategy per-calendar-year returns

| Year | Return | Days |
|---:|---:|---:|
| 2003 | 2.61% | 252 |
| 2004 | 13.86% | 252 |
| 2005 | 18.01% | 252 |
| 2006 | 22.15% | 251 |
| 2007 | 13.20% | 251 |
| 2008 | -13.45% | 253 |
| 2009 | 18.65% | 252 |
| 2010 | 5.97% | 252 |
| 2011 | -5.21% | 252 |
| 2012 | 6.07% | 250 |
| 2013 | 38.74% | 252 |
| 2014 | 11.52% | 252 |
| 2015 | -3.04% | 252 |
| 2016 | 4.08% | 252 |
| 2017 | 17.63% | 251 |
| 2018 | -2.79% | 251 |
| 2019 | 14.66% | 252 |
| 2020 | 11.09% | 253 |
| 2021 | 14.36% | 252 |
| 2022 | -8.93% | 251 |
| 2023 | 5.00% | 250 |
| 2024 | 17.97% | 252 |
| 2025 | 22.26% | 250 |
| 2026 | 3.25% | 225 |

## Primary strategy drawdowns in 2008/2020/2022

| Period | Max drawdown (window equity restarts at 1.0) |
|---|---:|
| 2008 | -23.95% |
| 2020 | -20.49% |
| 2022 | -12.91% |

