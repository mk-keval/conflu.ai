# Research Harden D-82 — Work Log

Append-only log for the D-82 research-harness hardening tasks. One entry per task.

---

## T0 — Verification (change no code)

- **Date:** 2026-11-12
- **Branch:** `research/baseline-backtesting` @ `90bfea5` (pulled; already up to date)
- **What changed and why:** nothing in code. Baseline verification of the state left by
  D-81 before starting T1.
- **Files touched:** `docs/SESSIONS/research-harden-d82-1og.md` (this file only).

### Commands and exact output

```text
$ pytest backend/tests/test_research_control.py backend/tests/test_research_data.py backend/tests/test_research_engine.py backend/tests/test_research_metrics.py -q
...........................................                                                                                                                                                               [100%]
43 passed in 4.04s
LASTEXIT=0
```

Note: the D-81 session note claims "58 passed". The command specified for T0 covers
four of the six research test modules and yields **43**. The 58 figure came from a
six-module run in D-81 (`test_research_data`, `test_research_engine`,
`test_research_metrics`, `test_research_setups`, `test_research_indicators`,
`test_research_control`). No test was skipped or modified here.

```text
$ ruff check backend/app/research scripts/run_research_baseline.py scripts/make_baseline_report.py backend/tests/test_research_*.py
All checks passed!
LASTEXIT=0
```

```text
$ python scripts/run_research_baseline.py --quick
...
Reconciliation: OK
INFO: NOT statistically significant vs controls (best p=0.6667 on permuted)
LASTEXIT=0
```

The quick run used `.cache/research_quick`, completed, printed `Reconciliation: OK`
and an `INFO:` significance line, and exited 0. Yahoo access worked (the run
downloaded or reused the quick cache without a network error). Result artifact:
`.cache/research_quick/out/statistical_mean_reversion_20261112_180109.json`
(ignored by git).

### Outcome

- Tests: **pass** (43/43).
- Ruff: **clean**.
- Quick run: **exit 0**, reconciliation OK, INFO line present.
- Skipped: none.
- Gate for T1: **open** (no earlier task outstanding).
