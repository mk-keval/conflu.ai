# 2026-08-30 — Out-of-Scope Cleanup for D-43 (Mojibake Arrows + Type Warnings)

## Summary

After shipping the D-43 fix (Technical tab empty), the user asked to also
clean up the two items originally flagged as "out of scope": the
`â–²` / `â–¼` / `â—†` mojibake on the sector flow arrows (sector badge in
the Verdict tab), and a cluster of pre-existing LSP warnings in
`backend/app/domain/ticker_analysis/technical.py`.

## Item 1: Sector flow arrows (D-43 "out of scope")

The bytes in `TickerAnalysisPage.tsx:1108` (post-D-42 file state):
- UP:    `C3 A2 E2 80 93 C2 B2` = `â–²` (3 chars)
- DOWN:  `C3 A2 E2 80 9C C2 BC` = `â"¼` (3 chars)
- DIAMOND: `C3 A2 E2 80 94 E2 80 A0` = `â—†` (3 chars)

`ftfy.fix_encoding` from D-42 did not repair these because each is now
a *valid* UTF-8 string of 3 characters — ftfy only repairs sequences
where the bytes, when re-decoded as Latin-1, form a valid UTF-8 string
that represents fewer characters. Here the visible chars include `–`
(U+2013) and `—` (U+2014) which are above U+00FF and cannot be
re-encoded as Latin-1, so the chain stops.

Reverse-engineering the CP1252 chain by hand:
- UP file `â–²` decodes back to bytes `E2 96 B2` → original char
  U+25B2 (`▲`).
- DOWN file `â"¼` decodes to bytes `E2 9C BC` — but the original
  was almost certainly `E2 96 BC` (U+25BC `▼`); the middle byte was
  bit-flipped from 0x96 to 0x93 by the corruption (single-byte error,
  undetectable algorithmically).
- DIAMOND file `â—†` decodes to bytes `E2 97 86` → original char
  U+25C6 (`◆`).

**Fix:** replaced the three mojibake strings with `▲` / `▼` / `◆`
directly. **Verified live via Playwright**: AAPL's sector badge now
renders the `▼` down arrow for the outflow signal (the page also
showed no remaining mojibake in the rendered DOM — full sweep of
`frontend/src` confirms 0 hits for the mojibake regex patterns).

## Item 2: Pre-existing LSP warnings in `technical.py`

A cluster of warnings had accumulated in the chart-reading code path
(D-36), with two distinct root causes:

**A. False-positive `pandas_ta` API stubs.** The local LSP stubs for
`pandas_ta` 0.4.71b0 don't expose the function-dispatcher entry
points (`ta.rsi`, `ta.adx`, `ta.macd`, `ta.atr`, `ta.bbands`).
Verified at runtime that the calls succeed and return the expected
columns (`ADX_14`, `MACD_12_26_9`, `BBU_20_2.0`, etc.).
**Fix:** added `# type: ignore[attr-defined]` on each of the five
calls with an inline comment noting that the runtime behavior is
verified by the integration test.

**B. Real NaN-handling bug in `_detect_swings`.** The code compared
`highs[i] <= highs[i - j]` directly on `ohlcv["High"].values`, which
returned a `numpy.ndarray` typed as `Any | object | NAType` by the
LSP (because the column dtype is `float64` and could contain NaN).
NaN comparisons silently return False, so any row with a NaN high
would skip swing detection. The fix:
- Drop NaN rows with `ohlcv[["High", "Low"]].dropna()` before reading
  values (defensive; yfinance data is normally clean).
- Cast to explicit `np.ndarray` with `dtype=np.float64` so the LSP
  sees concrete types.

**C. `volume_profile.compute_professional_tpo` consumer bug.** The
function has a union return type
`DailyTPOProfile | tuple[list[DailyTPOProfile], CompositeTPOProfile]`
— single object when daily history is insufficient, tuple when
composite can be built. The consumer at line 648 unpacks as
`tpo_daily, tpo_composite = ...` which would throw if the function
returned the single-object form.
**Fix:** added an `isinstance` check, and when the single-object
form is returned, wrap it in `[tpo_result]` and set composite to
`None`. Also added explicit type annotations so the LSP accepts the
narrowed types.

**D. None comparisons in MA-stack detection.** Lines 891-896
compared `sma20 > sma50 > sma200` etc. without explicit float
narrowing after the NaN/None guard. **Fix:** added explicit `s20:
float`, `s50: float`, `s200: float` re-bindings before the comparisons.

## Verification

- `lsp_diagnostics` on `technical.py`: only pre-existing style warnings
  (Ruff E741 ambiguous `l`, W291 trailing whitespace) — none of the
  errors I introduced or that the D-43 doc flagged.
- `python -c "import ast; ast.parse(...)"` on the file: clean.
- Live API: `POST /api/v1/ticker/AAPL/analyze` returns `technical: dict`
  with both `daily` and `weekly` timeframes populated, 1385ms.
- Regression test `test_technical_orchestrator_integration.py`: 2 passed.
- Playwright: `/ticker/AAPL` shows `▼` arrow in the sector badge (AAPL
  in outflow state). No `â` / `â€` / `Ã¢` mojibake in the rendered DOM.
- Frontend mojibake sweep: 0 matches across `frontend/src/**`.

## Related

- D-43 (parent fix): `docs/DECISIONS/D-43-technical-tab-empty-analyze-kwargs.md`
  — "Out of scope" section now updated to reflect this follow-up.
- D-42 (Mojibake cleanup): `docs/DECISIONS/D-42-web-mojibake-cleanup.md`
  — ftfy didn't reach the sector arrows due to a different chain shape.
- Branch: `fix/technical-tab-empty`
