# VOIDED - 2026-09 Bypass-Path Cohort (31 rows)

**Status:** VOID. Not a measurement sample. Do not include in any win-rate,
expectancy, or adherence calculation.

**Archived:** 2026-09-16

## Why

These 7 files (31 rows, 2026-09-03 -> 2026-09-15) were written by
`backend/scripts/paper_trade_from_brief.py`, which reads the morning brief
verdict and appends **every** candidate above a conviction floor - directly to
CSV. It does not run the validation gate, does not size by conviction, and
does not record a decision. The frontend workflow (gate -> execution ->
adherence) was never involved.

They are a **candidate dump**, not a set of trades.

## Why they cannot be graded

- **0 exits recorded.** The original schema had no `exit_price`, `status`,
  `pnl`, or `realized_r`. Result, hit rate, expectancy and average R are all
  not computable.
- **0 decisions recorded.** Every row is bullish (17 STRONG BUY / 11
  ACCUMULATE / 3 BUY). Nothing was ever rejected, so no selection signal
  exists to evaluate.
- **No sizing rule.** 29/31 rows violate the 5% single-name cap; conviction 3
  produced 7 different sizes and the best-R:R idea (BULL 3.99) got the
  smallest allocation (3.3%).

Grading them would measure the broken bypass path, not the intended system.

## Archived content

| File | Rows |
|---|---|
| `2026-09-03.csv` | 13 |
| `2026-09-05.csv` | 5 |
| `2026-09-06.csv` | 4 |
| `2026-09-09.csv` | 3 |
| `2026-09-10.csv` | 2 |
| `2026-09-12.csv` | 2 |
| `2026-09-15.csv` | 2 |

Original 12-column schema, retained byte-for-byte.

## Reference

Full findings: [`docs/SESSIONS/2026-09-16_paper-trade-evidence-audit.md`](../../../SESSIONS/2026-09-16_paper-trade-evidence-audit.md)

The measurement loop restarts at the first run written against the new
21-column schema in [`../../TEMPLATE.csv`](../../TEMPLATE.csv).
