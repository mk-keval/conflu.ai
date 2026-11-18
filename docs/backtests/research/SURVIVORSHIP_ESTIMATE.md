# Survivorship / Current-Membership Size Estimate (E9)

**Label: MEASUREMENT — no pass/fail.**

Generated `2026-11-18T16:12:53` by `scripts/research_survivorship.py`.

## Definitions

- The panel = the 501 current-constituent symbols loaded exactly as in the other scripts.
- For each trading day d from 2016-01-01, `ew_ret[d] = mean` over panel symbols that have both `close[d]` and `close[d-1]` of `close[d]/close[d-1] - 1` (daily-rebalanced equal weight; no eligibility filter).
- Calendar-year return = `product(1 + ew_ret) - 1`.
- Benchmarks: RSP (equal-weight S&P 500 ETF, point-in-time membership, ~0.20%/yr fee) and SPY, same adjusted-close method.
- Per year report: panel EW return, RSP return, gap = panel EW - RSP (percentage points), SPY return, symbols with data; plus the cumulative 2016->latest of each series and the average annual gap.

## Data and provenance

| Item | Value |
|---|---|
| Requested span | 2015-01-01 -> 2026-11-17 |
| Actual panel | 2015-01-02 -> 2026-11-17 |
| Universe symbols | 503 |
| Cached for span | 501 |
| Not loaded (no cache, never downloaded) | 2 (KVUE, VYLR) |
| Panel symbols loaded | 501 |
| Dropped by loader | 0 |
| Cache hits / downloads | 504 / 0 |
| Git revision | `5808d4f0e955cd835509192a5dffcbfdddae1d0a` |
| Dirty worktree | no |
| Command | `scripts/research_survivorship.py` |
| Elapsed | 0.6 minutes |

## Per-year returns and gap

| Year | Panel EW return | RSP return | Gap (panel - RSP) | SPY return | Symbols with data |
|---|---|---|---|---|---|
| 2016 | 21.41% | 15.79% | +5.62 pp | 13.59% | 469 |
| 2017 | 27.21% | 18.52% | +8.69 pp | 21.71% | 472 |
| 2018 | -2.00% | -7.84% | +5.84 pp | -4.57% | 476 |
| 2019 | 35.06% | 28.91% | +6.15 pp | 31.22% | 482 |
| 2020 | 23.51% | 12.66% | +10.85 pp | 18.33% | 487 |
| 2021 | 32.52% | 29.41% | +3.11 pp | 28.73% | 491 |
| 2022 | -10.13% | -11.62% | +1.49 pp | -18.18% | 493 |
| 2023 | 23.34% | 13.70% | +9.64 pp | 26.18% | 494 |
| 2024 | 21.01% | 12.79% | +8.22 pp | 24.89% | 497 |
| 2025 | 17.23% | 11.21% | +6.02 pp | 17.72% | 499 |
| 2026 | 17.86% | 13.98% | +3.88 pp | 9.15% | 501 |

## Cumulative 2016 -> latest

| Series | Cumulative return |
|---|---|
| Panel EW | 520.03% |
| RSP | 241.49% |
| Gap (panel - RSP) | +278.54 pp |
| SPY | 336.88% |

Average annual gap: +6.32 pp (11 of 11 years positive).

## Caveats

- Gap = survivorship + current-membership selection + RSP fees + rebalancing-method differences.
- It is an indicator of size, NOT a corrected estimate.
- It says nothing about the sign of the bias on any one signal.
- Daily-rebalanced equal weight is not RSP's quarterly rebalance.
