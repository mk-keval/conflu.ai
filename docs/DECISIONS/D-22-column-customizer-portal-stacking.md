# D-22: ColumnCustomizer Portal for Z-Index Escape

**Status:** Accepted
**Date:** 2026-07-03

## Context

The Screener page has a ColumnCustomizer dropdown button that shows/hides table columns. When opened, the dropdown appeared behind the table body because the parent `ScreenerHeader` component uses Tailwind's `backdrop-blur-sm`, which creates an isolated CSS stacking context. The dropdown's `z-50` was rendered relative to this context, placing it beneath the table's content area below.

## Decision

Replace the inline dropdown with `createPortal` to render into `document.body`, combined with `position: fixed` positioning computed from the button's `getBoundingClientRect()`:

```tsx
{open && createPortal(
  <div style={{ position: 'fixed', top: rect.bottom + 4, right: ..., zIndex: 9999 }}>
    {/* dropdown content */}
  </div>,
  document.body
)}
```

This completely escapes any parent stacking context and ensures the menu always renders above all page content regardless of `transform`, `filter`, or `backdrop-filter` on ancestor elements.

## Consequences

**Positive:**
- Dropdown always visible above all content, regardless of parent stacking context
- No CSS dependency on specific z-index values that can break
- Clean separation — portal handles DOM placement, JS handles positioning
- Positioning recalculates on every open (handles resize/move)

**Negative:**
- Slightly more complex than a pure CSS solution
- Doesn't auto-reposition on scroll (but re-opens will recalculate)
- Fixed positioning breaks if parent scrolled while open (acceptable for this use case)

**Alternatives Considered:**
- Setting `isolation: isolate` / `z-index` higher on dropdown (fails with deeper nesting)
- `position: relative` on header with higher z-index (defeats backdrop purpose)
- CSS `isolation: isolate` removal from header (affects header's own visual behavior)
