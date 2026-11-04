# 2026-08-30 — Web Mojibake Cleanup (CP1252→UTF-8 Double-Encoding)

## Summary

Fixed visible mojibake on the deployed web UI (em-dash displayed as a 3-character
garble starting with `a-circumflex`, warning sign similarly corrupted) by reversing
a UTF-8 double-encoding corruption in 5 source files. All 5 files had been written
through a Windows editor that read UTF-8 bytes as CP1252 and re-saved them as UTF-8.

## Root Cause

Investigated the user-reported artifacts on the live site:

1. **File-level inspection** showed every affected file starts with a UTF-8 BOM
   (`EF BB BF`). The BOM confused a Windows editor, which then read the multi-byte
   UTF-8 sequences as CP1252.
2. For example, the em-dash `—` (UTF-8: `E2 80 94`) was read as 3 CP1252 chars:
   `â` + `€` + `"` (codepoints U+00E2, U+20AC, U+201D). Those 3 chars were
   re-saved as UTF-8 → 8 bytes: `C3 A2 E2 82 AC E2 80 9D`. The browser displays
   that as a 3-char mojibake artifact (`a-circumflex` + `Euro` + `right-double-quote`).
3. **ftfy.fix_encoding** correctly reverses this — it's the canonical library for
   mojibake repair.

## Files Changed

| File | Lines | User-visible? |
|---|---|---|
| `frontend/src/components/ticker-analysis/TickerAnalysisPage.tsx` | 72 | **YES** (browser) |
| `docs/index.md` | 17 | **YES** (mkdocs at keval.github.io) |
| `backend/app/infrastructure/professional/education.py` | 7 | No (docstrings) |
| `INDEX.md` | 44 | No (root project hub) |
| `docs/SESSIONS/2026-07-31_glass-terminal-typography-brand-dx.md` | 2 | No (session log) |

Total: 5 files, 144 lines changed, 144 insertions / 144 deletions (pure character
replacements, no whitespace noise — per-line endings preserved exactly).

## Characters Restored

- Em-dash `—` (U+2014) — 80+ occurrences
- En-dash `–` (U+2013) — 1 occurrence
- Bullet `•` (U+2022) — 4 occurrences
- Warning sign `⚠` + variation selector `️` (U+26A0 + U+FE0F) — 2 occurrences
- Less-than-or-equal `≤` (U+2264) — 1 occurrence
- Middle dot `·` (U+00B7) — 1 occurrence
- Box-drawing horizontal `─` (U+2500) — 8 occurrences
- Greek beta `β` (U+03B2) — 2 occurrences
- UTF-8 BOM stripped from all 5 files

## Verification

- `frontend/node_modules/.bin/tsc --noEmit` → **exit 0** (TypeScript clean)
- `python -m py_compile backend/.../education.py` → **OK** (Python syntax clean)
- Full-repo regex sweep for mojibake patterns (CP1252-lead bytes followed by
  other high-bit chars, plus U+FFFD replacement char) on web-displayable files → **0 matches**

## Out of Scope (deferred)

- 8 files with UTF-8 BOM but no actual mojibake content. Cleaning the BOMs requires
  project-wide policy (`editorconfig` + pre-commit hook) — separate ADR.
- 2 session logs with `?` (U+FFFD) replacement chars from prior corruption. These
  are internal logs not displayed on the web; manual review needed (replacement char
  is ambiguous).

## Related

- [D-42: Web Mojibake Cleanup](../DECISIONS/D-42-web-mojibake-cleanup.md)
- Branch: `fix/web-mojibake-cleanup`
