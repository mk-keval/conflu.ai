# 2026-10-29 — Bundle A Implemented & Live (D-77)

**Branch:** `fix/technical-tab-empty`
**Decision:** [D-77](../DECISIONS/D-77-bundle-a-exit-geometry.md)
**Spec:** [BUNDLE_A_EXIT_GEOMETRY.md](../PAPER_TRADING/BUNDLE_A_EXIT_GEOMETRY.md)
**Pre-registration:** [PRE_REGISTRATION-v0.2.md](../PAPER_TRADING/PRE_REGISTRATION-v0.2.md)
**Implementation commit:** `dad6ac8`
**Go-live commit:** the commit that flips `CURRENT_SAMPLE_VERSION` to `v0.2`

## What shipped

The frozen Bundle A design is code. v0.1 rows are untouched: a row with
`setup_family = NULL` keeps the legacy single-exit walker and midpoint /
last-target Plan R.

| Piece | Behaviour |
|---|---|
| `exit_policy.py` | `screen_name` → family; nearest structural level inside the family band (no ATR/percentage fallback); family tranches; breakeven at +1R close; ATR trail after T1; calendar time stops; one `simulate_exit` shared by live sync and replay |
| `gate.py` | Family half-size / full-size floors; step 5c measures T1 from `entry_low` for v0.2 and the last target for v0.1 |
| `synthesis.py` | `setup_family` drives the band, ATR provenance, target-anchored `scale_out`, trail/BE/time-stop overrides, and `plan_rejection` (`target too close` / `target too far` / `no structural objective`) |
| `pnl.plan_metrics` | `basis="planned_fill"` → Plan R = T1 R from `entry_low`; `stretch_rr` = T3 R; legacy midpoint basis unchanged |
| Journal/pending | `setup_family`, `stretch_rr`, `atr_at_entry`, `exit_legs` columns (migrated; existing rows backfilled); fills inherit family/ATR; a same-session stop writes one full leg; a same-day re-run never adds v0.2 provenance to a v0.1 row |
| Workflow router | Rows store family provenance and planned-fill metrics; plan rejections land at failed step `plan`; sync exits branches to `simulate_exit` for family rows and `infer_exit` for NULL-family rows |
| Verifier | Leg integrity (sum 100%, VWAP = `exit_price`, weighted R = `realized_r`), family provenance, and scored Plan-R gaps as hard failures; v0.1 Plan-R gaps stay warnings |
| Scorecard | Per-family breakdown as context; D-75 pass bar unchanged |

One operational fix outside the trading rules: `journal_store._migrate` now
tolerates a concurrent process winning the `ALTER TABLE` race (API server + CLI
starting together). Schema outcome is identical; no trading effect.

One integrity guard added after go-live: `upsert_entry` preserves the stored
family/ATR/stretch on a v0.1 row and strips them on an explicit v0.1 insert, so
re-running an old date cannot retro-label history under v0.2 rules.

## Evidence

- **216 focused tests pass** (journal, pending, verification, scorecard,
  workflow endpoints, CLI, pnl, exits, gate, synthesis geometry, exit policy,
  Bundle A). 72 of them are new: `test_exit_policy.py` (38),
  `test_bundle_a.py` (14), `test_bundle_a_journal.py` (17),
  `test_bundle_a_workflow.py` (3).
- **Full backend suite:** 1017 passed, 5 failed. The 5 failures are
  `test_insider_cluster.py` (4) and
  `test_technical_data_quality.py::test_earnings_filter_missing_file_safe_default`;
  they reproduce identically at `HEAD` (`21bfd5f`) in a clean worktree, so they
  are pre-existing and unrelated.
- `python scripts/verify_journal.py` → **PASS**: 0 phantom fills, 0 P&L
  mismatches, 0 version issues, 0 leg issues, 0 family issues, 0 scored Plan-R
  failures; 3 v0.1 Plan-R warnings (CRS, IOSP, SF) reported, not hidden.
- `python scripts/scorecard.py` → exits 0; 0 scored rows, v0.1 reference only.

## State at go-live

- `SCORED_SAMPLE_VERSION = "v0.2"`, `CURRENT_SAMPLE_VERSION = "v0.2"`.
- Live journal unchanged: 10 rows, all `v0.1`; 3 forward (CRS closed −1.00R,
  SF/IOSP open), 1 pending DUK limit **122.57**, 3 filled orders.
- **No `interim` row was ever created.** The go-live commit preceded the first
  loop run on 2026-10-29.
- No v0.2 row exists yet; the clock starts at the first v0.2 fill.
- DB backup before the schema migration:
  `data/backups/paper_trades_20261029T002004Z.db`.

## Notes

- `backend/scripts/paper_trade_from_brief.py` is gitignored by
  `.gitignore:206` (`backend/scripts/`). Its matching family/ATR/legs changes
  are local-only; the API router path is committed.
- The gate enforces family **floors**, not the selection cap. A hand-built 4.5R
  T1 passes for trend; the family maximum is enforced in target selection.

## Next

1. Run the 2026-10-29 close loop in one go: DUK's third eligible session fills
   at 122.57 or expires — it remains `v0.1`, reference only; any new row is
   `v0.2`.
2. H-09 replay after go-live: same window/universe/costs, D-73 entry model,
   shared `exit_policy.simulate_exit`, `rules_version='v0.2'`, exploratory only,
   never evidence.
3. Watch the first v0.2 fill: it starts the sample clock.
