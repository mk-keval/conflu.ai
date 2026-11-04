# Control Study — Voided 2026-09 Bypass Cohort (Phase 0A-ii)

**Status:** READ-ONLY measurement over `docs/paper_trades/archive/2026-09-bypass-path-voided/` (7 files, 31 rows). The archive is untouched (D-50). This is **not** a measurement of the intended system — it measures the broken bypass path it replaced.

> **Caveat:** n=31 is far below any statistical threshold — directionally informative, not conclusive.

## Manufacture detector (R25 classification)

| date | symbol | action | rr_1 | rr_2 | stop % | class | fingerprint |
|---|---|---|---|---|---|---|---|
| 2026-09-03 | BULL | BUY | 3.99 | 4.598 | 22.82 | indeterminate | — |
| 2026-09-03 | PAGP | ACCUMULATE | 1.0 | 2.198 | 3.83 | manufactured | R20 t1=1.0R |
| 2026-09-03 | SLDE | ACCUMULATE | 0.542 | 0.977 | 17.94 | indeterminate | — |
| 2026-09-03 | ZETA | ACCUMULATE | 1.43 | 2.037 | 9.16 | indeterminate | — |
| 2026-09-03 | GNW | ACCUMULATE | 1.921 | 2.921 | 3.77 | indeterminate | — |
| 2026-09-03 | INVX | ACCUMULATE | 1.322 | 2.115 | 9.34 | indeterminate | — |
| 2026-09-03 | GWRE | ACCUMULATE | 1.305 | 1.468 | 30.61 | indeterminate | — |
| 2026-09-03 | DOCU | ACCUMULATE | 1.611 | 2.387 | 7.5 | indeterminate | — |
| 2026-09-03 | HRMY | ACCUMULATE | 1.644 | 2.708 | 5.48 | indeterminate | — |
| 2026-09-03 | LNG | ACCUMULATE | 1.0 | 1.9 | 5.29 | manufactured | R20 t1=1.0R |
| 2026-09-03 | CVX | STRONG BUY | 1.0 | 2.2 | 3.72 | manufactured | R20 t1=1.0R |
| 2026-09-03 | PSX | STRONG BUY | 2.276 | 3.707 | 4.63 | indeterminate | — |
| 2026-09-03 | VLO | STRONG BUY | 1.777 | 2.996 | 5.98 | indeterminate | — |
| 2026-09-05 | DOCU | BUY | 2.348 | 3.657 | 6.54 | indeterminate | — |
| 2026-09-05 | TARS | ACCUMULATE | 0.435 | 0.634 | 20.9 | indeterminate | — |
| 2026-09-05 | VLO | ACCUMULATE | 1.38 | 2.091 | 6.59 | indeterminate | — |
| 2026-09-05 | CVX | STRONG BUY | 1.606 | 2.478 | 5.34 | indeterminate | — |
| 2026-09-05 | PSX | STRONG BUY | 1.697 | 2.472 | 5.36 | indeterminate | — |
| 2026-09-06 | DOCU | BUY | 1.356 | 2.004 | 7.75 | indeterminate | — |
| 2026-09-06 | CVX | STRONG BUY | 1.0 | 2.201 | 3.73 | manufactured | R20 t1=1.0R |
| 2026-09-06 | PSX | STRONG BUY | 2.266 | 3.691 | 4.72 | indeterminate | — |
| 2026-09-06 | VLO | STRONG BUY | 1.785 | 3.008 | 5.98 | indeterminate | — |
| 2026-09-09 | NVDA | STRONG BUY | 1.068 | 1.617 | 7.45 | indeterminate | — |
| 2026-09-09 | MU | STRONG BUY | 2.205 | 3.172 | 6.48 | indeterminate | — |
| 2026-09-09 | LRCX | STRONG BUY | 2.106 | 3.189 | 5.66 | indeterminate | — |
| 2026-09-10 | MU | STRONG BUY | 1.453 | 2.2 | 9.07 | indeterminate | — |
| 2026-09-10 | INTC | STRONG BUY | 2.78 | 2.81 | 15.05 | indeterminate | — |
| 2026-09-12 | MU | STRONG BUY | 1.265 | 1.329 | 9.1 | indeterminate | — |
| 2026-09-12 | INTC | STRONG BUY | 2.179 | 2.204 | 17.4 | indeterminate | — |
| 2026-09-15 | T | STRONG BUY | 0.51 | 0.598 | 15.7 | indeterminate | — |
| 2026-09-15 | VZ | STRONG BUY | None | None | None | indeterminate | — |

**Totals:** 4 manufactured · 0 structural · 27 indeterminate

- **manufactured** — the recorded tuple could only arise from the fixed multipliers (R20 `t1 = entry + risk·1.0`, R18 `t2 = entry + risk·rr` with a round heuristic `rr`). Zero chart information.
- **structural** — never assignable from the 12-column schema: proving a chart-derived target needs `entry_low`/`entry_high`, which were not recorded. Reported 0 by construction (R25).
- **indeterminate** — no mechanical signature; the entry basis and rr path are unrecorded, so the structural path is indistinguishable from manufacture in the data (R25).

## Gate verdict tagging (0A-ii)

| date | symbol | action | gate_verdict | gate_failed_step |
|---|---|---|---|---|
| 2026-09-03 | BULL | BUY | CONDITIONAL | Liquidity |
| 2026-09-03 | PAGP | ACCUMULATE | CONDITIONAL | Liquidity |
| 2026-09-03 | SLDE | ACCUMULATE | CONDITIONAL | Liquidity |
| 2026-09-03 | ZETA | ACCUMULATE | CONDITIONAL | Liquidity |
| 2026-09-03 | GNW | ACCUMULATE | CONDITIONAL | Liquidity |
| 2026-09-03 | INVX | ACCUMULATE | CONDITIONAL | Liquidity |
| 2026-09-03 | GWRE | ACCUMULATE | CONDITIONAL | Liquidity |
| 2026-09-03 | DOCU | ACCUMULATE | CONDITIONAL | Liquidity |
| 2026-09-03 | HRMY | ACCUMULATE | CONDITIONAL | Liquidity |
| 2026-09-03 | LNG | ACCUMULATE | CONDITIONAL | Liquidity |
| 2026-09-03 | CVX | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-03 | PSX | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-03 | VLO | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-05 | DOCU | BUY | CONDITIONAL | Liquidity |
| 2026-09-05 | TARS | ACCUMULATE | CONDITIONAL | Liquidity |
| 2026-09-05 | VLO | ACCUMULATE | CONDITIONAL | Liquidity |
| 2026-09-05 | CVX | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-05 | PSX | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-06 | DOCU | BUY | CONDITIONAL | Liquidity |
| 2026-09-06 | CVX | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-06 | PSX | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-06 | VLO | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-09 | NVDA | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-09 | MU | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-09 | LRCX | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-10 | MU | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-10 | INTC | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-12 | MU | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-12 | INTC | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-15 | T | STRONG BUY | CONDITIONAL | Liquidity |
| 2026-09-15 | VZ | STRONG BUY | CONDITIONAL | Liquidity |

**Totals:** 0 PASS · 0 FAIL · 31 CONDITIONAL

## Stop-distance distribution (Sec.1E / D8 ceiling 10%)

- Rows with a stop: **30** (no stop: 1)
- Min **3.72%** · mean **9.43%** · max **30.61%**
- Exceeding 10% ceiling (`MAX_STOP_DISTANCE_PCT`): **7** — BULL 22.82%, SLDE 17.94%, GWRE 30.61%, TARS 20.9%, INTC 15.05%, INTC 17.4%, T 15.7%

### Sizing check

- Violating the 5% blueprint single-name cap: **29/31** (PAGP 16.5%, SLDE 16.5%, ZETA 8.8%, GNW 16.5%, INVX 8.8%, GWRE 8.8%, DOCU 8.8%, HRMY 8.8%, LNG 16.5%, CVX 16.5%, PSX 16.5%, VLO 16.5%, DOCU 11.2%, TARS 9.4%, VLO 9.4%, CVX 9.4%, PSX 9.4%, DOCU 8.0%, CVX 15.0%, PSX 15.0%, VLO 15.0%, NVDA 6.4%, MU 6.4%, LRCX 6.4%, MU 6.8%, INTC 6.8%, MU 9.4%, INTC 9.4%, T 8.0%)
- Exceeding the 2D 25% cap: **0** (none)

## Exit replay (Sec.2E conservative fill model)

Resolved: **18** · Unresolvable: **13**

| symbol | entered | closed | exit | R | mfe_r | mae_r | amb |
|---|---|---|---|---|---|---|---|
| SLDE | 2026-09-03 | 2026-09-14 | target_1 @ 26.05 | +0.54 | 0.65 | 0.08 |  |
| INVX | 2026-09-03 | 2026-09-21 | stop @ 27.76 | -1.00 | 0.33 | -1.17 |  |
| DOCU | 2026-09-03 | 2026-09-04 | target_1 @ 68.71 | +1.61 | 1.98 | 0.62 |  |
| HRMY | 2026-09-03 | 2026-09-08 | target_1 @ 43.0 | +1.64 | 1.87 | 0.88 |  |
| LNG | 2026-09-03 | 2026-09-08 | stop @ 275.46 | -1.00 | 0.35 | -1.06 |  |
| CVX | 2026-09-03 | 2026-09-22 | stop @ 201.87 | -1.20 | 0.82 | -1.34 |  |
| PSX | 2026-09-03 | 2026-09-17 | target_1 @ 269.33 | +2.28 | 2.71 | 0.38 |  |
| VLO | 2026-09-03 | 2026-09-10 | target_1 @ 392.23 | +1.78 | 1.84 | 0.27 |  |
| DOCU | 2026-09-05 | 2026-09-15 | target_1 @ 69.99 | +2.35 | 3.37 | 0.75 |  |
| VLO | 2026-09-05 | 2026-09-10 | target_1 @ 389.26 | +1.38 | 1.56 | 0.86 |  |
| PSX | 2026-09-05 | 2026-09-17 | target_1 @ 267.84 | +1.70 | 2.18 | 0.6 |  |
| DOCU | 2026-09-06 | 2026-09-15 | target_2 @ 73.19 | +2.00 | 2.18 | 0.06 |  |
| CVX | 2026-09-06 | 2026-09-10 | target_1 @ 216.38 | +1.00 | 1.13 | 0.07 |  |
| PSX | 2026-09-06 | 2026-09-17 | target_1 @ 270.01 | +2.27 | 2.63 | 0.83 |  |
| VLO | 2026-09-06 | 2026-09-10 | target_1 @ 392.33 | +1.78 | 1.84 | 1.06 |  |
| MU | 2026-09-09 | 2026-09-22 | target_1 @ 1079.31 | +2.21 | 2.41 | -0.68 |  |
| LRCX | 2026-09-09 | 2026-09-11 | stop @ 296.29 | -1.00 | 0.46 | -1.1 |  |
| MU | 2026-09-12 | 2026-09-22 | target_2 @ 1089.12 | +1.33 | 1.36 | -0.78 |  |

- **Win rate:** 77.8%
- **Expectancy:** +1.093 R/trade (avg win +1.71R · avg loss -1.05R)
- **Profit factor:** 5.683

> n is far below any statistical threshold — directionally informative, not conclusive.

### Unresolvable

- BULL (2026-09-03): exit not reached in available data
- PAGP (2026-09-03): exit not reached in available data
- ZETA (2026-09-03): exit not reached in available data
- GNW (2026-09-03): exit not reached in available data
- GWRE (2026-09-03): exit not reached in available data
- TARS (2026-09-05): exit not reached in available data
- CVX (2026-09-05): exit not reached in available data
- NVDA (2026-09-09): exit not reached in available data
- MU (2026-09-10): exit not reached in available data
- INTC (2026-09-10): exit not reached in available data
- INTC (2026-09-12): exit not reached in available data
- T (2026-09-15): exit not reached in available data
- VZ (2026-09-15): no geometry

---

Generated by `control_study_voided_cohort.py` · read-only on the archive.