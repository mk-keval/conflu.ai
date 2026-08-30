# D-34: Discovery Flow Redesign — Regime Weights, Snapshot Multi-Screen, RS/Catalyst/Earnings Enrichment (Swing Parity Wave 2)

**Status:** Accepted
**Date:** 2026-08-21
**Evidence:** Live NEUTRAL-regime replays (2026-08-21, post-deploy, two consecutive calls); plan `.sisyphus/plans/swing-parity-upgrade.md` v1.1; Oracle prerequisite mandate

## Context

Stage 1/2 of the parity replay failed on discovery: a NEUTRAL composite (53/100) mapped to `ranging` → all-defensive screens (mean-reversion/low-vol only), momentum templates compiled TV filters returning ~0 rows that were then cached sticky for 60s. The API-minimization mandate caps upstream calls while requiring fresh discovery.

## Decision

### P1.0 — TVCache stale-while-revalidate + circuit breaker (Oracle prerequisite)

- `TVCache.get_with_freshness()` tri-state lookup (fresh / stale / miss) with `stale_ttl=300s`; legacy `get()` keeps strict freshness semantics. Empty cached states are never served fresh or stale (`_is_serveable` guard).
- `TVScreenEngine.discover` serves stale entries immediately and schedules a deduped background refresh; an empty refresh result keeps the good stale entry instead of overwriting it.
- New `TVCircuitBreaker`: sliding-window volume guard (>20 TV calls/60s ⇒ open). `rate_limiter_stats()` exposes breaker state additively.

### P1.1 — Config-driven per-regime screen weights

- `config/regime_screens.yaml`: weighted per-regime lists; selector precedence config → heuristic scoring → hardcoded fallback. Top-3 by weight guarantees exactly one `role: defensive` secondary; failed template loads backfill from remaining weighted candidates.
- `_REGIME_LABEL_MAP`: `Neutral → neutral`, `Cautious → choppy` as first-class regimes (was `ranging`, the RC1 root cause).

### P1.2 — One-Snapshot-Multi-Screen behind `CONFLU_SCREEN_SNAPSHOT_MULTI_SCREEN` (default OFF)

- `SnapshotMultiScreenEngine`: ONE broad base query (liquid US equities gates server-side, SNAPSHOT_COLUMNS + dynamic EMA columns from template params) → per-template local masking via pandas shims (`tv_local_eval.LocalColumn/LocalCond`) fed into the SAME `FILTER_MAP` lambdas — one source of truth for filter semantics.
- `_and/_or` in tv_specialist are polymorphic (local conds reduce via &/|). Local evaluation fails closed: unknown indicator or missing column ⇒ template omitted and individually routed to legacy discovery.
- `TVScreenEngine.screen_batch()`: flag + breaker gating; snapshot participates in SWR cache; response contract identical to `gather(screen(...), return_exceptions=True)` (per-item Exceptions preserved).
- Known accepted divergence while flag is OFF-by-default: non-default timeframes evaluate against the single snapshot interval.

### P1.3 — RS-vs-index percentiles from the same snapshot

- `Perf.1M`/`Perf.3M` added to `SNAPSHOT_COLUMNS`; `compute_rs_percentiles()` anchors on the SPY row when present, else cross-sectional median; attaches additive `item["rs"]` blocks (excess, pct_1m/pct_3m, composite) on the snapshot path only.

### P1.4/P1.5 — Catalyst-Breakout badge + earnings-proximity chip

- Badge = EPS beat > 0 AND rvol > 1.2 AND close ≥ 97% of 52-week high. Single evaluation point at the quote-attach pass using `tv_data_by_symbol` + `earningsSurprisePct` riding along on the SAME yfinance .info payload as premarket quotes — zero extra upstream calls. Unknown components keep the badge off.
- `days_to_earnings` added to TickerBrief + WatchlistItemResponse; `EarningsAnalysis.days_until_earnings` persisted at analyze stage.
- **Latent bug fixed en route**: naive-vs-aware datetime subtraction raised inside earnings.py's try block, silently killing ALL proximity logic (risk-window finding never fired); normalized tz handling now makes it reachable.

## Consequences

- **Positive (live NEUTRAL replay ×2 consecutive)**: sections now 52-Week Breakout n=5 (PD/AVAH/PSNL/MRVI/ACRS — BUY conv 8), Short Squeeze n=1 (DK BUY), Statistical Mean Reversion demoted to one defensive secondary, Sector Rotation XLV STRONG BUYs intact (LLY/JNJ/ABBV conv 8–10). Zero sticky-empty sections across consecutive cycles. Pre-fix state served ONLY defensive screens.
- **Positive**: brief-cycle upstream budget drops toward 1–3 TV calls once the snapshot flag is enabled; SWR already protects rate-limit bursts today.
- **Risk**: promotion-style weight swaps could mask regime mis-detection — mitigated by config-file tunability without code changes.
- **Neutral**: catalyst badges honestly False on replay day (no EPS-beat+near-high+rvol confluence); fields stay additive-safe for the frontend.

## Verification

- Full suite **542 passed / 0 failed** (16 new engine/cache tests, 25 shim/batch tests, 8 RS tests, 12 badge tests, 8 chip tests); lsp clean on all touched trees.
- `gitnexus_detect_changes` clean at each commit; impact analyses run before each symbol edit (discover LOW; TVCache LOW; RegimeScreenSelector LOW; TickerBrief MEDIUM additive-only).
- Live gate evidence: two consecutive `/morning-brief?regime=neutral` calls returned identical healthy section sets with zero sticky-empty results.
