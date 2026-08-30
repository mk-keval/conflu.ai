# Session Log — 2026-08-21: Swing Parity Waves 1–2 (branch feat/swing-parity-upgrade)

**Branch:** feat/swing-parity-upgrade (from main @ 1777a13)
**Plan:** .sisyphus/plans/swing-parity-upgrade.md v1.1

## Commits (wave-aligned)

| Commit | Content |
|--------|---------|
| 558d99b | feat(synthesis): swing parity wave 1 — plan geometry invariants + classifier calibration (D-33) — pre-existing uncommitted Wave-1 work landed first per plan |
| 2f0bcea | test: restore missing screen templates + fix asyncio integration config |
| c25537c | feat(cache): TVCache stale-while-revalidate + circuit breaker (P1.0) |
| 348df50 | feat(professional): regime-driven screen weight remap (P1.1) |
| 46d1534 | feat(screener): One-Snapshot-Multi-Screen behind SNAPSHOT_MULTI_SCREEN flag (P1.2) |
| 3628efa | feat(screener): RS-vs-index percentile enrichment from same snapshot (P1.3) |
| a7e1f5e | feat(professional): catalyst-breakout badge on morning brief cards (P1.4) |
| e6b3c48 | feat(professional): earnings-proximity warning chip on brief cards + watchlist (P1.5) |

## STEP 0/1 notes

- Baseline reproduced exactly: 459 passed / 4 failed.
- stash@{2} (feat/add-missing-screen-templates) did NOT contain short-squeeze/distribution templates and the branch is gone → authored both YAMLs fresh against the FILTER_MAP registry (10 filters each, institutional gates + volume + technical, matching existing template conventions).
- Asyncio failures bisected to e2e+integration co-run; root cause: session-scoped `sync_playwright()` keeps its greenlet dispatcher suspended mid-run_until_complete for the whole pytest process, poisoning main-thread running-loop state for later pytest-asyncio Runners. Fix: module-scope e2e fixtures (documented in conftest). All 463 tests then green.

## Wave 2 gate evidence

- Full suite **542 passed / 0 failed** after P1.5; lsp clean across screener/, professional/, domain/ticker_analysis touched files; gitnexus_detect_changes run per commit (scope confined to screener/professional flows).
- Live replay vs conflu-api (container recreated with `config/regime_screens.yaml` mount added to docker-compose):
  - `GET /api/v1/professional/morning-brief?regime=neutral` ×2 consecutive:
    - 52-Week Breakout n=5 (PD, AVAH, PSNL, MRVI, ACRS — BUY conv 8)
    - Short Squeeze n=1 (DK BUY conv 5)
    - Statistical Mean Reversion = single defensive secondary
    - Sector Rotation XLV: LLY/JNJ/ABBV STRONG BUY conv 8–10
    - Zero sticky-empty sections both calls (pre-fix: defensive-only + cached-zero screens)

## Decisions

- D-34 records the full Wave-2 architecture (SWR+breaker, regime weights, snapshot engine, RS/badge/chip enrichments).

## Next

Wave 3 mentor narration layer → Wave 4 parallel fan-out → Wave 5 parity_replay.py codification → push + PR.
