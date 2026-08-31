# D-42: Web Mojibake Cleanup — Reverse CP1252→UTF-8 Double-Encoding in Source Files

**Status:** Accepted
**Date:** 2026-08-30

## Context

The user reported visible mojibake on the deployed web UI (em-dash rendered as the
3-byte sequence `\xC3\xA2\xE2\x82\xAC\xE2\x80\x9D` which displays as
`a-circumflex + Euro + right-double-quote`; warning sign `⚠` rendered as the
6-byte `\xC3\xA2\xC5\xA1\xC2\xA0\xC3\xAF\xC2\xB8\xC2\x8F`; etc.).
Investigation revealed that five source files contained UTF-8 sequences that had been
**double-encoded**: an editor or save tool read each non-ASCII byte as Windows-1252
(likely due to a UTF-8 BOM confusing a Windows editor), then re-saved the resulting
CP1252-decoded characters as UTF-8. The result: characters that should have been
em-dash (U+2014), en-dash (U+2013), bullet (U+2022), warning sign (U+26A0),
less-than-or-equal (U+2264), Greek beta (U+03B2), etc. were stored as 3-6 byte
mojibake sequences on disk.

The browser rendered those bytes literally, producing the visible artifacts the user
reported (em-dash appeared as `a-circumflex + Euro + right-double-quote`,
warning sign appeared as a 6-character garble starting with `a-circumflex`).

### Affected Files

| File | Lines touched | User-visible? |
|---|---|---|
| `frontend/src/components/ticker-analysis/TickerAnalysisPage.tsx` | 72 | **YES** (rendered in browser) |
| `backend/app/infrastructure/professional/education.py` | 7 | No (docstrings only — but loaded by `EducationService` so worth cleaning) |
| `docs/index.md` | 17 | **YES** (published via `mkdocs.yml` at keval.github.io/conflu.ai) |
| `INDEX.md` | 44 | No (root project hub, not published) |
| `docs/SESSIONS/2026-07-31_glass-terminal-typography-brand-dx.md` | 2 | No (internal session log) |

Five other files have UTF-8 BOMs but **no actual mojibake content** — out of scope for this fix (no visible defect).

## Decision

Apply **`ftfy.fix_encoding`** (the standard library for repairing mojibake) to the
affected files, with the following guards:

1. **BOM stripping**: UTF-8 BOM (EF BB BF) is removed (project convention: no BOM).
2. **Per-line ending preservation**: each line's original ending (LF or CRLF) is
   remembered and re-applied, so the diff is purely character-level (no whitespace noise).
3. **`fix_encoding` only** (not full `fix_text`): we don't want ftfy's other
   transformations (curly-quote conversion, etc.) that could alter intentional
   wording.

Verified post-fix:
- `frontend/.../tsc --noEmit` → exit 0
- `python -m py_compile education.py` → OK
- Full-repo regex sweep for mojibake patterns (CP1252-lead bytes followed by other
  high-bit chars, plus U+FFFD replacement char) → **0 matches** in the
  web-displayable files (TickerAnalysisPage.tsx, education.py, docs/index.md).

## Why ftfy

- It's the canonical Python library for this exact problem (used by Mozilla, etc.)
- It only modifies text that is *demonstrably* mis-encoded; it leaves ASCII text alone
- It does not perform the looser "fix sloppy typing" transformations (curly quotes,
  etc.) when only `fix_encoding` is called
- It is small and pure-Python, no runtime impact on the project

## Out of Scope (deliberate)

- `INDEX.md` is the project hub, not published; included for hygiene.
- Session logs with `?` (U+FFFD replacement chars from prior corruption) — these are
  internal logs not displayed on the web. Cleaning them would require manual review
  (the replacement char is ambiguous — multiple UTF-8 sequences could produce it).
- Files with BOM but no mojibake (8 other files). Touching them is out of scope; if
  the team wants BOM-stripping enforced project-wide, that should be a separate ADR
  with an `.editorconfig`/pre-commit hook to prevent regressions.
