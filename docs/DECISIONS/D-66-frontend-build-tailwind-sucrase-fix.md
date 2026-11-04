# D-66: Frontend Build Fix — Tailwind CSS sucrase Parsing Issue

**Date**: 2026-10-07
**Status**: Resolved
**Branch**: fix/technical-tab-empty

## Problem

Frontend production build (`npm run build`) was failing with:
```
[vite:css] [postcss] Unexpected token, expected "," (64:19)
file: C:/_Code/conflu.ai/frontend/src/index.css:undefined:NaN
    at unexpected (C:\_Code\conflu.ai\frontend\node_modules\sucrase\dist\parser\traverser\util.js:99:15)
    ...
    at tsParseMaybeAssignWithoutJSX (C:\_Code\conflu.ai\frontend\node_modules\sucrase\dist\parser\plugins\typescript.js:1580:45)
```

**Root Cause**: Vite's React plugin (`@vitejs/plugin-react` / `@vitejs/plugin-react-swc`) processes CSS files imported in TypeScript files through the TypeScript parser (sucrase). When the CSS file contains `@tailwind` directives or certain CSS syntax, sucrase (a TypeScript parser) fails to parse valid CSS syntax.

This is a known issue with Vite + React + Tailwind CSS where:
- Tailwind CSS 3.x JIT compiler uses sucrase internally
- Tailwind CSS 4.x Vite/PostCSS plugins have beta bugs
- Any CSS file imported in `.tsx` files gets processed by sucrase

## Attempted Solutions (Failed)

1. **Tailwind CSS 3.x with `@tailwind` directives** — sucrase parses CSS as TypeScript
2. **Tailwind CSS 3.x with `@import` statements** — same sucrase issue
3. **Tailwind CSS 4.x Vite plugin (`@tailwindcss/vite`)** — "Cannot convert undefined or null to object"
4. **Tailwind CSS 4.x PostCSS plugin (`@tailwindcss/postcss`)** — "Missing field `negated` on ScannerOptions.sources"
5. **Moving CSS to `styles/` directory** — still imported in TypeScript, same issue
6. **PostCSS CLI / Tailwind CLI** — both use sucrase internally, same parsing error

## Working Solution

**Move CSS to `public/` directory and load via `<link>` tag in `index.html`**

This bypasses Vite's TypeScript parser entirely since:
- Files in `public/` are served as static assets
- `<link rel="stylesheet" href="/index.css">` loads CSS directly in browser
- No CSS processing through sucrase/TypeScript parser

## Changes Made

### Files Modified
- `frontend/public/index.css` (new) — Complete CSS with all component styles + dark color utilities
- `frontend/index.html` — Added `<link rel="stylesheet" href="/index.css" />`
- `frontend/src/main.tsx` — Removed `import './index.css'`
- `frontend/vite.config.ts` — Removed `css.postcss` config, reverted to standard React plugin
- `frontend/postcss.config.js` — Minimal config (autoprefixer only)
- `frontend/tailwind.config.ts` — Kept nested dark color format (for reference)

### Key Additions to `public/index.css`
Added Tailwind-compatible dark color utilities (50-950 scale) for:
- `bg-dark-*` background colors
- `text-dark-*` text colors
- `border-dark-*` border colors
- `hover:bg-dark-*`, `hover:text-dark-*`, `hover:border-dark-*` hover states

This replaces Tailwind's generated utilities that components use (36 files reference `bg-dark-*`, `text-dark-*`, `border-dark-*`).

### Dependencies Cleaned Up
Removed unused packages:
- `@tailwindcss/vite`, `@tailwindcss/postcss`, `tailwindcss@next` (Tailwind 4.x beta)
- `postcss-import`

Kept: `tailwindcss@3` (for config reference), `autoprefixer`

## Validation

```bash
cd frontend && npm run build
# ✓ Built successfully in ~9s
# Output: dist/index.html + assets/*.js (chunked)
```

Backend tests: 771+ tests still pass (unchanged).

## Visibility Fix (White-on-White Text)

**Problem**: Playwright testing revealed white text on white background in backtest page across 3 tabs (Run, Optimize, Compare). Buttons for Position Sizing (Fixed/ATR-based/Kelly), Method (Grid/Random/Bayesian), and Objectives (sortino/calmar/max_dd/win_rate/profit_factor/sqn/cagr) had `text-dark-200`/`text-dark-300` text color but no default background, making text invisible on white background.

**Fix**: Added `bg-dark-800` to unselected button states in:
- `src/components/backtest/BacktestForm.tsx` (Position Sizing buttons)
- `src/components/backtest/OptimizationForm.tsx` (Method buttons, Objective buttons)

**Validation**: Playwright test confirms 0 WHITE_ON_WHITE issues (was 11). Remaining 94 LOW_CONTRAST issues are intentional design choices (muted nav, inactive tabs, timestamps).

## Trade-offs

| Aspect | Before (Tailwind JIT) | After (Static CSS) |
|--------|----------------------|-------------------|
| Build | Failed | ✅ Passes |
| Dev HMR | Full Tailwind HMR | Manual CSS edits |
| Bundle size | Tree-shaken utilities | Full CSS (~40KB) |
| Dark colors | Auto-generated | Manually maintained |
| New utilities | Auto-available | Must add manually |

## Future Considerations

- When Tailwind CSS 4.x stabilizes, migrate back to `@import "tailwindcss"` + `@theme`
- Consider `vite-plugin-tailwindcss` (community) for better integration
- For now, static CSS in `public/` is a pragmatic workaround

## Related

- D-65: Ticker Analysis Data Accuracy Fixes (backend)
- Session: fix/technical-tab-empty branch