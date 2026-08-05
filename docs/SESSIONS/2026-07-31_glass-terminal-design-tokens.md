# Session: Glass Terminal — Design Token Foundation

**Date**: 2026-07-31
**Branch**: fix/elite-trader-gaps

## Context
Design-system foundation transform for the trading platform: generic dark-slate/green theme → distinctive "glass terminal" (deep ink background, frosted-glass panels, teal/cyan brand accent, Newsreader editorial serif for display headlines). Values only — no token/class names renamed, so all existing components keep working.

## Files Changed (exactly 3)
- `frontend/tailwind.config.ts`
- `frontend/src/index.css`
- `frontend/index.html`

## Changes

### tailwind.config.ts
- **Palette**: `background #05070D`, `surface #0A0E17`, `surface-elevated #131A2A`, `surface-hover #1B2436`, border `rgba(148,163,184,0.14)`, `text-primary #F1F5F9` — cooler deep-ink scale than the previous slate
- **Added** `surface-tertiary #0D1320` — latent bug fix: referenced in 20+ components (WorkflowPage, SectorHeatMap, SectorDetailCard, professional/*, etc.) but was undefined
- **Accent → teal**: DEFAULT `#2DD4BF`, light `#5EEAD4`, dark `#14B8A6` (replaces green; green/red now reserved strictly for gain/loss semantics)
- **Fonts**: added `display: ['Newsreader', 'Georgia', 'serif']`; IBM Plex Sans + JetBrains Mono untouched
- **Shadows**: `glow-green`/`glow-red` → `glow-teal` `0 0 20px rgba(45,212,191,0.18)`; `card`/`card-hover` kept
- **Animation**: added `tape-scroll` (`tape-scroll 45s linear infinite`) + keyframes `translateX(0) → translateX(-50%)` (consumed by `TickerTape.tsx` via `animate-tape-scroll`)

### src/index.css
- `.card`/`.card-hover` → frosted glass (white/[0.03] + `backdrop-blur-xl` + white/10 border, hover white/[0.06])
- `.btn-primary` → teal bg with dark ink text `#042F2B`, `shadow-glow-teal`; `.btn-secondary`/`.btn-ghost` → glass-muted variants
- `.input`/`.select` → translucent ink bg, focus ring `accent/20`
- `.badge-neutral` → white/[0.06] + `text-text-secondary`; `.badge-green`/`.badge-red` unchanged (semantic)
- `.cell-price`/`.cell-gain`/`.cell-loss` unchanged
- **Added** `.page-title` (font-display), `.glass`, `.tape-item` utility classes
- `::selection` now uses `accent/20` (automatically teal)

### index.html
- **Newsreader** merged into the single Google Fonts link (`family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400`)
- Loading text `text-dark-200` (undefined token) → `text-text-muted`; spinner already uses `border-accent` → now teal automatically

## Verification
- Tailwind CLI + real PostCSS pipeline (same as vite): compiles clean, zero warnings
- `@apply` resolution confirmed for all classes (`font-display`, `shadow-glow-teal`, `text-[#042F2B]`, `bg-white/[0.03]`, `animate-tape-scroll` keyframes emitted)
- `tsc --noEmit`: no errors in the 3 edited files
- `vite build` blocked only by a parallel agent's in-flight `./TickerTape` import (out of scope)
- Note: Tailwind v3 emits `@layer components` classes only when used in scanned content — `.glass`/`.page-title`/`.tape-item` will appear in output once the shell components consume them (next agent's step)
- Diff scoped to exactly 3 files; EOL normalized to LF (repo convention)

## Notes
- `text-dark-200`/`text-dark-400`/`bg-dark-500`/`bg-dark-600` still present in several component files (backtest, risk, charts, screener) — pre-existing undefined tokens, outside this task's 3-file scope. Recommend a follow-up sweep mapping them to `text-text-muted`/`text-text-secondary`/`surface-*`.
