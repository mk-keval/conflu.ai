# Session Log: 2026-10-19 — Dependency Security Remediation (npm + Python)

**Date:** 2026-10-19
**Branch:** `fix/technical-tab-empty`
**Type:** Tooling/deps — security scans + package upgrades (no application behavior changes)
**Decision:** [D-69](../DECISIONS/D-69-dependency-security-remediation.md)

## Summary

The user asked to run the security scan and upgrade packages. Both sides were scanned, fixed, and re-verified: **npm 24 → 10 advisories (0 critical)** and **Python 5/119 → 0/120** — which let the CI `security-scan.yml` pip-audit job drop its five `--ignore-vuln` stubs ("bump starlette to clear them for real" — done). Frontend vitest/tsc/build and 854 backend tests pass on the new stack.

## Scan findings (start of session)

**npm (frontend/) — 24 advisories: 2 critical / 14 high / 8 moderate**

- `axios <=1.19.0` (high × several advisories) — fixed in 1.20.0 (in-range).
- `tinypool <=2.1.1` + `vitest 0.0.95–4.1.10` (critical) + `@vitest/mocker` (moderate) — fixed in vitest ≥4.1.11.
- `esbuild <=0.24.2` (moderate, GHSA-67mh-4wv8-2f99) via `vite <=6.4.2` — fixed in vite 7.x.
- `ajv <=8.17.1` (moderate, ReDoS with `$data`) — fixed in 8.20.0.
- `braces` (high, **no fixed version**), `chokidar`, `fast-glob`, `micromatch`, `postcss-nested`, `postcss-selector-parser`, `tailwindcss` — the tailwind 3 chain; only clearable via tailwind 4.
- `react-router` / `react-router-dom` 6.x (moderate) — fixed only in 7.18.4+.
- `@redocly/openapi-core`→`js-yaml`, `brace-expansion`, `fast-uri`, `source-map-js`, `browserslist` — fixed in-range by `npm audit fix`.

**Python (uv.lock, audited via OSV `querybatch` against `uv export --frozen`) — 5 of 119 packages flagged**

- `anyio 4.14.1`, `pyjwt 2.13.0`, `soupsieve 2.8.4`, `urllib3 2.7.0`.
- `starlette 0.52.1` — including the five PYSECs ignored in CI (PYSEC-2026-161/248/249/2280/2281) + five matching GHSAs; fixes land in starlette 1.0.1 / 1.1.0 / 1.3.x → **no fix exists on the 0.5x line**, and instrumentator 7.1.0 capped `starlette<1.0.0`.
- Local `pip-audit` cannot resolve the lock on this machine's Python 3.14 (numba has no cp314 build → metadata build fails); the OSV batch query was used instead — same pinned inputs, no install step. CI stays on py3.12 with real `pip-audit`.

## What landed

**Frontend** (`frontend/package.json`, `package-lock.json`):

- `vite ^5.4.0 → ^7.3.7` (esbuild 0.27+; clears both the vite and esbuild advisories; `@vitejs/plugin-react@5.2.0` peer-supports ^7).
- `vitest ^3.2.4 → ^4.1.12` (clears critical tinypool + @vitest/mocker + vitest; one major step).
- `ajv 8.17.1 → 8.20.0` (exact-pin style kept).
- Removed `@vitejs/plugin-react-swc` (unused since the D-66 swc→babel move).
- `npm update` in-range bumps (~59 packages: playwright, tanstack, postcss/autoprefixer, prettier, etc.) + `npm audit fix` (axios → 1.20.0, js-yaml, fast-uri, brace-expansion, …).

**Backend** (`pyproject.toml`, `uv.lock`):

- `starlette 0.52.1 → 1.9.0` — required all three of: fastapi spec uncapped (`>=0.46`), `fastapi 0.139.0 → 0.148.0`, and the keystone pyproject bump `prometheus-fastapi-instrumentator >=7.0,<8 → >=8.1,<9` (8.1.0 requires `starlette>=1.0,<2`).
- `anyio 4.15.1`, `pyjwt 2.15.1`, `soupsieve 3.0.3`, `urllib3 2.8.0`.
- Riding along: opentelemetry instrumentation train (1.43→1.45.1 / 0.64b0→0.66b1) + `opentelemetry-exporter-http-transport` added by the otlp 1.45 split.

**CI** (`.github/workflows/security-scan.yml`):

- pip-audit: removed the five `--ignore-vuln` lines + NOTE (starlette clears for real).
- npm audit: debt comment refreshed — vite@8 note removed (vite 7.3.7 cleared it); remaining debt = tailwind 4 chain, react-router-dom@7, lint-staged@17.

**Generated types** (`frontend/src/types/__generated__/*`): regenerated — had drifted since the last regen on **2026-09-24** (filter-sweep, ticker analysis, workflow run-close/journal endpoints were missing). Nothing imports these files (reference only); `tsc` stays clean. Committed separately as drift cleanup.

## Verification

- npm: **24 → 10 advisories, 0 critical** (6 high / 4 moderate — all deferred majors); `npm audit --audit-level=critical` passes.
- Python: **0/120** flagged on re-query.
- Frontend: vitest **134/134** (11 files), `tsc --noEmit` clean, `vite build` green; `npm run typegen` runs cleanly on fastapi 0.148.
- Backend: `pytest backend/tests` → **854 passed**; remaining known: 4× pre-existing `test_regime_selector` (deleted `short-squeeze.yaml`, documented 2026-10-18) + 1 e2e (`test_multi_tf_with_template`) against the live `/api/v1/screen/tv/multi-tf` path. Direct probe (fresh server, JSON body): **HTTP 200 in 36 s**, handler `exec_ms=2810` — the excess is first-request engine/session warm-up on the TradingView path, just over the test's 30 s playwright budget. Environment/latency dependent, not a dependency regression.

## Deferred (tracked debt)

| Finding | Blocked by |
|---|---|
| tailwind 3 chain (braces/chokidar/fast-glob/micromatch/postcss-nested/postcss-selector-parser/tailwindcss) | tailwind 4 migration — `braces` has no fixed 3.x, the chain only leaves with tailwind 4 |
| react-router / react-router-dom 6 → 7 (GHSA-wrjc-x8rr-h8h6, GHSA-337j-9hxr-rhxg, moderate) | RR7 migration |
| React 19 + @types/react 19 (no finding — currency) | React 19 migration |
| eslint 9 → 10 (9.39.5 is marked deprecated) | eslint 10 migration |
| lint-staged 15 → 17 (high; not wired to any hook today — no config in frontend/) | trivial when the dep is next touched |
| vite 8 / @vitejs/plugin-react 6 | rolldown/oxc era — separate decision |

## Notes

- The global Python 3.14 dev env was updated in place (fastapi 0.148.0 / starlette 1.9.0 / instrumentator 8.1.0 / anyio 4.15.1 / pyjwt 2.15.1 / soupsieve 3.0.3 / urllib3 2.8.0) so the local suite runs against the lock; CI remains on 3.12.
- `_patch_instrumentator_routing()` (FastAPI ≥0.138 `_IncludedRouter` workaround in `backend/app/api/observability.py`) tolerated the instrumentator 7 → 8 bump — startup + metrics init logs normal.
- Per repo rules: `gitnexus_detect_changes` run before the commits.
