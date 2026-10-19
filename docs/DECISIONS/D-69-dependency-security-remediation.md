# D-69: Dependency Security Remediation — vite 7 / vitest 4 / starlette 1.9

**Date**: 2026-10-19
**Status**: Accepted — applied in this session
**Branch**: fix/technical-tab-empty

## Context

- Follow-up to the paper-journal session: "lets check for security scan as well, there should be upgrades to packages."
- `.github/workflows/security-scan.yml` gates on pip-audit (Python) and `npm audit --audit-level=critical` (frontend). The pip-audit job carried five explicit `--ignore-vuln` starlette stubs with a NOTE to "bump starlette to clear them for real"; the npm job carried documented major-upgrade debt (vite@8 for the esbuild GHSA, react-router-dom@7).
- Scan results at session start — npm: **24 advisories (2 critical / 14 high / 8 moderate)**; Python: **5 of 119 pinned packages flagged** (anyio, pyjwt, soupsieve, starlette, urllib3 — including the five CI-ignored starlette PYSECs plus five matching GHSAs).

## Decision

1. **Frontend** (`frontend/package.json`, `package-lock.json`):
   - `vite ^5.4.0 → ^7.3.7` — clears the vite advisories (`<=6.4.2`) and the esbuild GHSA-67mh-4wv8-2f99 (`<=0.24.2`; vite 7 ships esbuild 0.27+). **Not vite 8**: that line moves to the rolldown/oxc plugin era (plugin-react 6) and deserves its own decision, especially given the D-66 build scar.
   - `vitest ^3.2.4 → ^4.1.12` — clears the critical tinypool + @vitest/mocker + vitest advisories (flagged ranges end at vitest/@vitest/mocker 4.1.10; ≥4.1.11 dropped tinypool entirely). One major step, not two (5.x not needed to clear findings).
   - `ajv 8.17.1 → 8.20.0` (ReDoS with `$data`; exact-pin style kept).
   - Removed `@vitejs/plugin-react-swc` — dead weight since the D-66 swc→babel move.
2. **Backend** (`pyproject.toml`, `uv.lock`):
   - `starlette 0.52.1 → 1.9.0` — the keystone; required all three of: fastapi's spec is uncapped (`starlette>=0.46.0`), `fastapi 0.139.0 → 0.148.0`, and the pyproject cap `prometheus-fastapi-instrumentator >=7.0,<8 → >=8.1,<9` (7.1.0 capped `starlette<1.0.0`; **8.1.0 requires `starlette>=1.0,<2`**).
   - `anyio 4.15.1`, `pyjwt 2.15.1`, `soupsieve 3.0.3`, `urllib3 2.8.0`.
   - Riding along: the opentelemetry instrumentation train (1.43→1.45.1 / 0.64b0→0.66b1) + `opentelemetry-exporter-http-transport` (added by the otlp 1.45 split).
3. **CI** (`.github/workflows/security-scan.yml`): removed the five stale `--ignore-vuln` stubs; refreshed the npm-audit debt comment (vite@8 note removed — no longer present).
4. **Generated types**: regenerated `frontend/src/types/__generated__/*` (drifted since 2026-09-24) — committed separately as drift cleanup; nothing imports them (reference only).

## Rationale

- "Bump starlette" was structurally impossible before this: the 0.5x line has **no fixed releases** (fixes land in 1.0.1 / 1.1.0 / 1.3.x) and instrumentator 7.1.0 capped `starlette<1.0.0`. The pyproject bump was the keystone, not an incidental upgrade.
- vite 7 is the mature rollup-based line and the lowest-risk vehicle for the esbuild fix in a codebase recently affected by D-66; vite 8 changes the bundler/plugin generation.
- The npm criticals were dev-tooling (vitest/tinypool local runner), but they trip the CI critical gate — vitest 4.1.12 clears them without a double major jump.
- Remaining npm advisories are all behind majors (tailwind 3 chain → tailwind 4; RR 6→7; lint-staged 15→17) and none of them gate CI (critical-only threshold).

## Consequences

- **Positive:** CI pip-audit runs without ignore flags; npm criticals at 0; the Python lock audits clean (0/120); dead swc plugin removed; backend on current fastapi/starlette.
- **Trade-offs:** starlette 0.x → 1.9.0 and fastapi 0.139 → 0.148 are significant jumps — the 854-test backend suite is the safety net, and the instrumentator `_patch_instrumentator_routing()` monkeypatch should be re-checked at each instrumentator bump. vite 7 requires Node ≥20.19 (repo uses 24).
- **Deferred (tracked debt):** tailwind 4 migration (the only way to clear the braces/chokidar/fast-glob/micromatch/postcss-nested/postcss-selector-parser/tailwindcss chain — `braces` has no fixed 3.x); react-router-dom 7 (moderate: GHSA-wrjc-x8rr-h8h6 / GHSA-337j-9hxr-rhxg); React 19 + @types 19; eslint 10; lint-staged 17; vite 8 / plugin-react 6.

## Validation

- npm: **24 → 10** advisories — **0 critical** (6 high / 4 moderate, all deferred majors); `npm audit --audit-level=critical` passes.
- Python: **5/119 → 0/120** (OSV `querybatch` against the frozen `uv export`).
- Frontend: vitest **134/134** (11 files), `tsc --noEmit` clean, `vite build` green on vite 7.3.7.
- Backend: `pytest backend/tests` → **854 passed**; remaining: 4× pre-existing `test_regime_selector` (deleted `short-squeeze.yaml`, documented 2026-10-18) + 1 e2e (`test_multi_tf_with_template`) against the live `/api/v1/screen/tv/multi-tf` path. Direct probe: **HTTP 200 in 36 s** with the handler itself reporting `exec_ms=2810` — ~33 s is first-request engine/session warm-up (TradingView), just over the test's 30 s playwright budget. Environment/latency dependent, not a dependency regression.

## Related

- Implements the "bump starlette to clear them for real" TODO in `.github/workflows/security-scan.yml`.
- Predecessor: **D-66** (frontend build fix — the swc→babel move that made the dead-dependency removal possible).
- Session: [2026-10-19 dependency security remediation](../SESSIONS/2026-10-19_dependency-security-remediation.md)
