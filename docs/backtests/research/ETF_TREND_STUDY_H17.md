# ETF Trend Study H-17 (F4/F5)

> EXPLORATORY — never the scorecard, D-75 pass bar, kill rule or any forward verdict.

## Run metadata

- Generated UTC: 2026-11-24T15:28:07.177127+00:00
- Code revision: `ea6411e5993e312e389f6f6a1df03b64e01b1c5e`
- Dirty: `False`
- Prereg: `docs/backtests/research/PREREGISTRATION-H-17-v1.md`
- Prereg sha256: `3a1300d840592287f28fcc0442f84609118878e9fd53a98a1aee3f4dff1f12af`
- Snapshot dir: `research_data/etf_20261124`
- Manifest sha256: `c0bb469785aa64679f3b8f48e17f7ee42584d2d049a88b1a6b2b316f19aa9304`

## Frozen limits

the 19 ETFs were chosen in 2026 from survivors (ETF survivorship is mild but not zero); 2005-2015 includes 2008; one universe, one sample path, ~21 years; yfinance data; costs are a flat assumption; no taxes; in-sample for the strategy family (12-1 momentum and a 200-day trend filter are literature defaults, not fitted here, but the author has seen general market history); EXPLORATORY, never the scorecard, D-75 pass bar, kill rule or any forward verdict. In-sample, survivorship-biased universe; no walk-forward.

## Primary strategy — Tier A/B (holdout)

- Tier A: **False**
- Tier B: **False**
- Four-way label: **neither**

## Holdout point estimates and CIs (primary vs SPY)

| Metric | Point | 95% month-block CI | CI includes zero/1? |
|---|---:|---:|---:|
| Sharpe diff (strategy-SPY) | -0.1740 | [-0.5489, 0.1777] | True |
| CAGR diff (strategy-SPY) | -0.0536 | [-49.5462, 0.0000] | True |
| MaxDD magnitude ratio (strategy/SPY) | 0.6827 | [0.5423, 1.3605] | True |

If a CI includes zero (or 1 for the ratio) the report must say the bar was met on point estimates and that the difference is not statistically distinguishable.

## Development window (2005-01-01..2015-12-31) — reported only

| Strategy | CAGR | Sharpe | MaxDD | Calmar | Ann turnover | Share days SHY |
|---|---:|---:|---:|---:|---:|---:|
| primary_cost_10 | 9.84% | 0.7021 | -24.76% | 0.3974 | 3.0842 | 0.00% |
| top3 | 9.71% | 0.6325 | -24.42% | 0.3976 | 3.6845 | 0.00% |
| top8 | 9.49% | 0.7325 | -22.06% | 0.4303 | 2.4204 | 0.00% |
| trend_only | 7.86% | 0.6696 | -29.83% | 0.2636 | 2.1432 | 0.00% |
| momentum_no_trend | 12.25% | 0.8236 | -19.72% | 0.6209 | 2.6633 | 0.00% |
| primary_cost_0 | 10.52% | 0.7432 | -24.23% | 0.4341 | 3.0831 | 0.00% |
| primary_cost_25 | 8.83% | 0.6402 | -25.56% | 0.3456 | 3.0860 | 0.00% |
| spy_ief_60_40 | 6.68% | 0.6528 | -32.58% | 0.2049 | 0.1094 | 0.00% |
| equal_weight_19 | 7.73% | 0.5424 | -45.39% | 0.1702 | 0.1577 | 0.00% |
| spy_buy_hold | 7.02% | 0.4397 | -55.19% | 0.1272 | 0.0000 | 0.00% |

## Holdout window (2016-01-01..latest) — primary

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

## Primary strategy per-calendar-year returns

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

## Primary strategy drawdowns in 2008/2020/2022

| Period | Max drawdown (window equity restarts at 1.0) |
|---|---:|
| 2008 | -23.38% |
| 2020 | -23.02% |
| 2022 | -15.01% |

