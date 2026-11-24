# ETF Data Quality Report (F2)

- Generated (UTC): 2026-11-24T05:08:20.488753+00:00
- Code revision: `d47951429a1f4ecad82244bd3e4f4fccfa538b5a`
- Snapshot dir: `research_data\etf_20261124`
- Manifest sha256: `c0bb469785aa64679f3b8f48e17f7ee42584d2d049a88b1a6b2b316f19aa9304`
- HARD findings: 0
- WARN findings: 2

## Symbol table

| Symbol | First date | Last date | Rows |
|---|---:|---:|---:|
| SPY | 2003-01-02 | 2026-11-23 | 6012 |
| QQQ | 2003-01-02 | 2026-11-23 | 6012 |
| IWM | 2003-01-02 | 2026-11-23 | 6012 |
| EFA | 2003-01-02 | 2026-11-23 | 6012 |
| EEM | 2003-04-14 | 2026-11-23 | 5942 |
| XLB | 2003-01-02 | 2026-11-23 | 6012 |
| XLE | 2003-01-02 | 2026-11-23 | 6012 |
| XLF | 2003-01-02 | 2026-11-23 | 6012 |
| XLI | 2003-01-02 | 2026-11-23 | 6012 |
| XLK | 2003-01-02 | 2026-11-23 | 6012 |
| XLP | 2003-01-02 | 2026-11-23 | 6012 |
| XLU | 2003-01-02 | 2026-11-23 | 6012 |
| XLV | 2003-01-02 | 2026-11-23 | 6012 |
| XLY | 2003-01-02 | 2026-11-23 | 6012 |
| TLT | 2003-01-02 | 2026-11-23 | 6012 |
| IEF | 2003-01-02 | 2026-11-23 | 6012 |
| LQD | 2003-01-02 | 2026-11-23 | 6012 |
| GLD | 2004-11-18 | 2026-11-23 | 5538 |
| VNQ | 2004-09-29 | 2026-11-23 | 5574 |
| SHY | 2003-01-02 | 2026-11-23 | 6012 |

## Findings

| Symbol | Check | Severity | Count | Detail |
|---|---|---|---:|---|
| EEM | close_moves | WARN | 2 | raw Close move > 20% with no Stock Splits |
| XLE | close_moves | WARN | 1 | raw Close move > 20% with no Stock Splits |

## Two-pull comparison

| Symbol | Rows pull 1 | Rows pull 2 | Close equal (common) | Ret diff count (tol 0.0005) | Ret diff fraction |
|---|---:|---:|---:|---:|---:|
| SPY | 6012 | 6012 | True | 0 | 0.000000 |
| QQQ | 6012 | 6012 | True | 0 | 0.000000 |
| IWM | 6012 | 6012 | True | 0 | 0.000000 |
| EFA | 6012 | 6012 | True | 0 | 0.000000 |
| EEM | 5942 | 5942 | True | 0 | 0.000000 |
| XLB | 6012 | 6012 | True | 0 | 0.000000 |
| XLE | 6012 | 6012 | True | 0 | 0.000000 |
| XLF | 6012 | 6012 | True | 0 | 0.000000 |
| XLI | 6012 | 6012 | True | 0 | 0.000000 |
| XLK | 6012 | 6012 | True | 0 | 0.000000 |
| XLP | 6012 | 6012 | True | 0 | 0.000000 |
| XLU | 6012 | 6012 | True | 0 | 0.000000 |
| XLV | 6012 | 6012 | True | 0 | 0.000000 |
| XLY | 6012 | 6012 | True | 0 | 0.000000 |
| TLT | 6012 | 6012 | True | 0 | 0.000000 |
| IEF | 6012 | 6012 | True | 0 | 0.000000 |
| LQD | 6012 | 6012 | True | 0 | 0.000000 |
| GLD | 5538 | 5538 | True | 0 | 0.000000 |
| VNQ | 5574 | 5574 | True | 0 | 0.000000 |
| SHY | 6012 | 6012 | True | 0 | 0.000000 |

## Tiingo cross-check

Tiingo cross-check: RUN (summary only; no Tiingo price data saved)

| Symbol | Common return days | Ret diff count (tol 0.0005) | Ret diff fraction |
|---|---:|---:|---:|
| SPY | 6011 | 9 | 0.001497 |
| QQQ | 6011 | 33 | 0.005490 |
| IWM | 6011 | 151 | 0.025121 |
| EFA | 6011 | 42 | 0.006987 |
| EEM | 5941 | 55 | 0.009258 |
| XLB | 6011 | 88 | 0.014640 |
| XLE | 6011 | 94 | 0.015638 |
| XLF | 6011 | 101 | 0.016803 |
| XLI | 6011 | 78 | 0.012976 |
| XLK | 6011 | 85 | 0.014141 |
| XLP | 6011 | 91 | 0.015139 |
| XLU | 6011 | 85 | 0.014141 |
| XLV | 6011 | 94 | 0.015638 |
| XLY | 6011 | 71 | 0.011812 |
| TLT | 6011 | 38 | 0.006322 |
| IEF | 6011 | 25 | 0.004159 |
| LQD | 6011 | 59 | 0.009815 |
| GLD | 5537 | 18 | 0.003251 |
| VNQ | 5573 | 52 | 0.009331 |
| SHY | 6011 | 17 | 0.002828 |

