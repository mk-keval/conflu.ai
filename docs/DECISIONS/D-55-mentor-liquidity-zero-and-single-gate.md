# D-55: Preserve zero dollar volume and use one mentor liquidity check

Date: 2026-09-17
Status: Implemented for critical-illiquidity scoring only

## Context

The in-progress liquidity wiring contained two mentor checks in synthesis and a truthiness-based merge that discarded computed zero dollar volume. This is separate from the planned seven-step workflow gate. IDs D-52 through D-54 remain reserved by the existing plan.

## Decision

- Keep one mentor liquidity check reading `avg_daily_volume_usd_calc` in synthesis.
- Merge this metric with explicit missing-value checks so zero remains evidence of illiquidity. Preserve the existing merge rules for other indicators.
- Retain the existing $100K critical-illiquidity threshold. This does not implement or replace the planned $10M workflow liquidity rule.
- Do not attach a false-PASS stub or the unrelated validation pipeline enum to `AnalysisVerdict`. The planned workflow evaluator must exist before verdict wiring can be completed.

## Verification

The zero-merge integration case failed before the correction with `KeyError: 'avg_daily_volume_usd_calc'` and passed afterward. Related synthesis, orchestration, data-quality and narration tests: 63 passed, 3 skipped. Explicit final LSP checks returned no errors for the changed production modules and integration test. No red-to-green run was performed for the separate duplicate-gate deletion.

GitNexus reported LOW risk for the orchestration method: four direct callers, including ticker-analysis and professional routes, with no indexed processes. Indexed coverage was incomplete for the helper and synthesis function; runtime tests supplied additional evidence.

## Limits

The helper still requires 50 history rows. Full backend testing stopped at an insider-cluster assertion outside this change after 282 passes; the baseline of that failure was not independently established. No routes or architecture were changed. Independent multi-agent review did not complete because delegations timed out. No commits were created.

See [session continuation](../SESSIONS/2026-09-16_gate-enforcement-spine-planning.md).
