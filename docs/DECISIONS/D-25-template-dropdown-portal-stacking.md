# D-25: TemplateDropdown Portal for Pointer-Events Escape

**Status:** Accepted
**Date:** 2026-07-14

## Context
The `TemplateDropdown` in `ScreenerPage.tsx` used absolute positioning (`absolute top-full left-0 right-0 z-50`) within the component tree. When the dropdown extended below the screener header into the results table area, items below the visible scroll area could not be clicked. Playwright reported:

> `<div class="flex-1 overflow-auto">` from `<div class="flex-1 overflow-hidden relative">` subtree intercepts pointer events

The results table container's `overflow-hidden relative` creates a stacking context that traps pointer events — items rendered within this context cannot receive clicks when another element occupies the same viewport space, regardless of z-index.

## Decision
Convert `TemplateDropdown` to use the same portal-based fixed positioning pattern already proven by `ColumnCustomizer` (see D-22):

1. **Portal rendering**: Dropdown menu rendered via `createPortal` to `document.body` with `position: fixed`
2. **Dynamic positioning**: Button position measured via `getBoundingClientRect()` on open, stored in state
3. **High z-index**: `zIndex: 9999` to stack above all page content
4. **Dual outside-click detection**: Handler checks both the parent wrapper AND the portal dropdown ref

### Implementation
```tsx
// Position state
const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});

// Recalc on open
useEffect(() => {
  if (!open || !btnRef.current) return;
  const rect = btnRef.current.getBoundingClientRect();
  setDropdownStyle({
    position: 'fixed',
    left: rect.left,
    top: rect.bottom + 4,
    minWidth: rect.width,
    zIndex: 9999,
  });
}, [open]);

// Portal render
{open && createPortal(
  <div ref={dropdownRef} style={dropdownStyle} ...>,
  document.body
)}
```

## Consequences
- **Positive**: Dropdown items at any scroll position are fully clickable regardless of parent stacking contexts
- **Positive**: Pattern consistency with `ColumnCustomizer` (D-22) — same approach used for the same class of problem
- **Positive**: No layout shift concerns — fixed positioning decouples from component flow
- **Trade-off**: Slight complexity increase (position state, dual refs, portal)
- **Risk**: If button moves after open (window resize, scroll), dropdown position becomes stale — acceptable for a short-lived menu

## Related
- D-22: ColumnCustomizer Portal for Z-Index Escape (same pattern, earlier fix)
