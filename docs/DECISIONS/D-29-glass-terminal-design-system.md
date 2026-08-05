# D-29: Glass Terminal Design System & Brand Identity

**Status:** Accepted
**Date:** 2026-07-31

## Context

The trading platform's UI used Tailwind's stock dark-slate palette with a generic green accent — indistinguishable from the "AI dark trading template" (near-black + single bright green). The ui-ux-pro-max skill produced a functional but identity-less result. A design consultation with an "elite trader" persona (loaded skill) established requirements: speed, trust, calm (brand color must never collide with gain/loss red/green), focus, consistency — mapped to "rich, clean, modern, mobile-friendly."

## Decision

Adopt a **"Glass Terminal"** design system:

- **Palette**: deep ink `#05070D` background (not stock slate), frosted-glass panels (`bg-white/[0.03]` + `backdrop-blur-xl` + `white/10` borders) over subtle teal/indigo ambient glows.
- **Brand accent**: teal/cyan `#2DD4BF` (DEFAULT), `#5EEAD4` (light), `#14B8A6` (dark). Green `#22C55E` / red `#EF4444` are **strictly semantic** (gain/loss) and never used as brand color.
- **Typography**:
  - Display: **Newsreader** serif (semibold, tight tracking) for page titles and headline moments.
  - Body/UI: **Manrope** (300–800) — modern grotesque, replaces IBM Plex Sans.
  - Data: **JetBrains Mono** (unchanged) — tabular numerals.
- **Brand mark**: "Converging Flow" — three signal streams converge into a single rising stroke with an upward arrowhead (SVG, teal gradient `#0D9488 → #2DD4BF → #99F6E4`). Wordmark "conflu**.ai**" in Newsreader. Replaces text-in-box logo and the old purple favicon.
- **Signature element**: live ticker tape under the header, streaming `price:{SYMBOL}` WebSocket channels.
- **Responsive**: sidebar desktop-only (`lg:`), new mobile bottom-nav with slide-up "More" drawer, safe-area padding.
- **DX**: Vite `usePolling` for Docker bind-mount HMR.

## Consequences

- **Benefits**: distinctive identity; teal accent leaves red/green semantically pure; token-driven change ripples across all 74 components via `tailwind.config.ts`; first real mobile pass.
- **Costs/risks**: Tailwind v3 tree-shakes `@layer components` classes unused in content (`.glass`/`.page-title`/`.tape-item` must stay outside `@layer`); some components still use undefined legacy tokens (`text-dark-*`, `bg-dark-*`) — follow-up sweep needed; Docker rebuild required for config-level changes (only `src/`, `public/`, `index.html` are bind-mounted); `change_pct` absent from backend `price_update` payloads at runtime (tape renders it defensively).
- **Trade-offs**: dark-only theme (no light mode); Newsreader/Manrope add two Google Fonts families (minor load cost).

## Related

- Session: `docs/SESSIONS/2026-07-31_glass-terminal-design-tokens.md`
- Session: `docs/SESSIONS/2026-07-31_glass-terminal-responsive-shell.md`
- Session: `docs/SESSIONS/2026-07-31_ticker-tape-component.md`
- Session: `docs/SESSIONS/2026-07-31_glass-terminal-typography-brand-dx.md`

## Supersession Note

The **live ticker tape** (signature element) was **removed on 2026-08-04** — see [D-30: Remove Header TickerTape Component](D-30-remove-header-ticker-tape.md). It caused 4 bug classes (compile failure, route shadowing, response-validation 500s, React crash) and polled 24 uncached Yahoo calls every 5s for a decorative strip. All other D-29 decisions (palette, teal accent, Newsreader/Manrope, brand mark, responsive shell) stand unchanged.
