# 2026-09-05 — Paper-Trade High-Conviction Run + Script Bugs

## Summary
Ran `backend/scripts/paper_trade_from_brief.py --min-conviction 7` against the
live morning brief and wrote 5 high-conviction paper trades to
`docs/paper_trades/2026-09-05.csv`. While doing so, surfaced two real defects
in the script (cosmetic on *nix, fatal on Windows) and one data-quality bug
in the backend macro note.

## Run Output (2026-09-05)

| Symbol | Sector      | Action       | Entry   | Stop    | T1     | T2     | Pos%  | Confluence |
|--------|-------------|--------------|---------|---------|--------|--------|-------|------------|
| DOCU   | Technology  | BUY          | 60.67   | 56.70   | 69.99  | 75.19  | 11.2% | 3          |
| TARS   | Healthcare  | ACCUMULATE   | 87.38   | 69.12   | 95.32  | 98.95  | 9.4%  | 3          |
| VLO    | Energy      | ACCUMULATE   | 356.82  | 333.32  | 389.26 | 405.95 | 9.4%  | 3          |
| CVX    | Energy      | STRONG BUY   | 201.73  | 190.96  | 219.03 | 228.42 | 9.4%  | 5          |
| PSX    | Energy      | STRONG BUY   | 245.53  | 232.38  | 267.84 | 278.04 | 9.4%  | 5          |

Regime: **Risk-On** (Positive market conditions, rising prices, healthy breadth).
5 of 4 sections represented; CVX & PSX are the two conviction=10 STRONG BUY names.

## Bugs Found

### 1. Script crashes on Windows console (cp1252)
- `paper_trade_from_brief.py:144` — `print(f"  ✓ {sym} → ...")` raises
  `UnicodeEncodeError: 'charmap' codec can't encode character '\u2713'`.
- `paper_trade_from_brief.py:157` — `print(f"\n💾 Wrote ...")` raises same
  error AFTER the `with open(...)` block has closed.
- **Impact on Windows**: every per-ticker `print` raises mid-loop, the
  traceback is sent to stderr, and the operator sees a flood of
  `✗ DOCU failed: 'charmap' codec can't encode character '\u2713'`
  messages even though the row was successfully built, appended, and
  written to CSV. This is misleading — yesterday's run and today's run
  both wrote valid CSVs despite the alarming stderr.
- **Fix**: wrap print calls with `sys.stdout.reconfigure(encoding='utf-8',
  errors='replace')` at top of `main()`, or drop the ✓ / 💾 / ⚠️
  glyphs in favor of ASCII. (Defer; today's CSV is intact.)

### 2. `--regime-only` mutates the iteration list (line 118-120)
The filter loop appends every ticker above `min_conviction` to
`candidates`, then *re-slices* `section["tickers"]` to only the
top-conviction one. This is dead code on its own line — by the time it
runs, the candidates list is already populated, so the slice has no
effect on output. Not exercised in today's run.

### 3. Backend macro note: `+nan%` (data bug, not script bug)
The `signal_at_entry` / `notes` columns contain the literal string
`leading sector XLE (+nan% today)`. This came from the backend's
sector-rotation enrichment (the `+nan%` survived into the brief and
into every per-ticker note). Frontend likely renders this same NaN
string. Needs investigation in the sector-rotation service — probably
a `pct_change()` call on a series whose first value is `nan` or where
`raw["change_pct"]` is missing.

## Verification
- CSV row count: 5 (expected — 5 candidates passed the conviction ≥ 7 filter)
- File: `docs/paper_trades/2026-09-05.csv` (UTF-8, properly quoted, 12 columns)
- Header matches `TEMPLATE.csv`
- Re-read the file with `encoding='utf-8'` — content is clean, no mojibake

## Next
- Patch `paper_trade_from_brief.py` to either reconfigure stdout to UTF-8
  or drop emoji. Low priority (cosmetic) but the misleading "✗ failed"
  stderr on Windows is worth fixing.
- File a follow-up for the `+nan%` sector-rotation data bug.

---

## Fixes Applied (D-49)

Both issues fixed and verified.

### Fix A — Windows cp1252 crash in `paper_trade_from_brief.py`
- Added `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at
  the top of `main()` with a `getattr` fallback for streams that don't
  support reconfigure (pipes, Python <3.7).
- Verified by re-running the script on Windows: clean output, all ✓/💾
  emoji render, no traceback. CSV written: `docs/paper_trades/2026-09-06.csv`
  (4 rows, regime=Neutral, 3 STRONG BUY Sector Rotation + 1 BUY DOCU).

### Fix B — `+nan%` literal in macro context notes
- Root cause: `backend/app/infrastructure/professional/macro_context.py:151`
  computed `(last / prev - 1) * 100` without checking if either value
  was finite. When yfinance returns a NaN close (partial trading day,
  delisted ticker, stale data), the NaN propagates through `_pct_change`
  → `sector_pcts` → `leading_sector_1d_pct` → orchestrator line 748
  `f"{...:+.1f}% today"` → renders as the literal string `+nan%`.
- Fix: added `if not (math.isfinite(prev) and math.isfinite(last)) or
  prev == 0: return None` guard. The function now returns `None` for
  untrustworthy data, which causes the sector to be dropped from the
  leader/lagger pool rather than selected with a NaN value.
- Added 3 regression tests in `backend/tests/test_macro_context.py`:
  `test_nan_prev_returns_none`, `test_nan_last_returns_none`,
  `test_inf_prev_returns_none`. All 24 tests in the file pass.
- Verified on live data: today's CSV (2026-09-06) has 0 rows with `+nan%`.
  Note: today's regime classified as "Neutral" so the orchestrator's
  calm-regime macro sentence doesn't fire at all — but the underlying
  NaN bug is closed and will not resurface the next calm day with bad data.

### Followups (not fixed)
- The `--regime-only` dead-code branch (line 118-120) is still there.
  Low priority, doesn't affect output.
- Pre-existing LSP warnings (`pd is not defined`) in macro_context.py
  predate this change. Out of scope.
