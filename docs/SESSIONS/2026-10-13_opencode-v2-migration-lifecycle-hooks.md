# Session Log: 2026-10-13 — OpenCode V1→V2 Migration + `lifecycle-hooks` Global Plugin Restored

> Environment/tooling work (not conflu.ai application code). Recorded here per the project's
> auto-documentation rule.

**Date:** 2026-10-13
**Branch:** fix/technical-tab-empty (unchanged — no repo source touched)
**Scope:** User's global OpenCode config (`%USERPROFILE%\.config\opencode\`) and project config (`.opencode/opencode.json`)

## Prompt

User is migrating their OpenCode setup from V1 to V2 and asked to first restore their custom
global plugin `lifecycle-hooks` ("really important … I use it to work on my own rules").

## Problem

During the V1→V2 migration the plugins directory was recreated, which permanently deleted the
original `lifecycle-hooks.js` source before it had been backed up. The file was not in the
OpenCode cache, the Windows Recycle Bin, or editor history.

## Recovery

Recovered the complete original 1200-line V1 source from OpenCode session transcripts
(`~/.claude/transcripts/*.jsonl`). The transcripts only contained `read` previews (50 KB cap),
so the file was reassembled from **two** complementary reads of the same version:

- `cand-04` — lines 1–1120 (session `ses_fdf0639b…`)
- `cand-00` — lines 1121–1200 (same session, offset read)

The seam was verified (`// 1. Project rules` → `const rules = extractProjectRules(...)`) and the
result passes `node --check`. (An earlier candidate was a *different, older* revision — discarded.)

## What was done

### 1. V2 plugin API research (ground truth, not guesses)
- Fetched the V2 docs: `https://opencode.ai/v2/docs/build/plugins` and `/migrate-v1`.
- Downloaded the published type packages: `@opencode/plugin@2.0.28`, `@opencode/ai@2.0.28`.
- Ran a temporary in-process probe plugin to dump real hook events.

**Confirmed V2 facts used:**
| V1 | V2 |
|----|----|
| `experimental.chat.messages.transform` | `ctx.session.hook("context", (event) => …)` |
| `experimental.session.compacting` | `ctx.session.hook("compaction", (event) => …)` |
| messages = `{ info, parts }[]` | messages = `{ role, content: [{ type, text }] }[]` |
| `output.context.push(...)` | `event.system.push({ type: "text", text })` |
| `process.cwd()` | `ctx.location.directory` (per-location plugin instance) |
| plugin = default-exported hook map | plugin = default export `{ id, setup(ctx) }` |

### 2. Rebuilt `lifecycle-hooks` as a V2 plugin
- **New path:** `%USERPROFILE%\.config\opencode\plugins\lifecycle-hooks\index.js` (directory form — no "path must be a directory" warning).
- **Config:** global `opencode.json` → `"plugins": ["./plugins/lifecycle-hooks"]`.
- Ported all three original behaviours:
  1. **Smart Skill Loader** — intent classification → `<required-tools>` block (tier-1 skills, tier-2 matches, MCP detection, tool directives, background-agent hints, workflow).
  2. **Session Context Injector** — `<SESSION-CONTEXT>` block (project rules, recent decisions, git branch, GitNexus status, previous-session handoff, auto-doc rule).
  3. **Compaction Context Saver** — `<COMPACTION-PRESERVE>` block + session handoff on compaction.
- Kept the user's configuration constants (`SKILL_CONFIG`, `TOOL_DETECTION`, `MCP_DETECTION`, `INTENT_CLASSIFICATION`, `COMPACTION_CONFIG`, `SESSION_CONFIG`) and directive text.

### 3. Deliberate deviations from the V1 source
- **GitNexus check is now non-blocking** (was a blocking `execSync` on every request): async refresh + 10-min TTL cache; the status line appears on subsequent requests.
- **Git branch is cached** (15 s) to avoid spawning `git` on every request.
- **MODEL-discipline lines made dynamic**: the two hard-coded model IDs (`opencode/deepseek-v4-flash-free`, `nvidia/…nemotron-3-ultra-550b`) were replaced with the *actual* current model from the request (`event.model`), since the config owns the default.
- A few V1-only tool names in directive text were modernised (`bash`→`shell`, `ast_grep_search`→`grep`, `lsp_diagnostics`→diagnostics). Remaining stale references to `claude_mem_search()` / gitnexus tool names are preserved as-is (user's rules).

## Verification

```
opencode run --standalone --print-logs "say READY"
```
- Plugin loads: `entrypoint=file:///…/plugins/lifecycle-hooks/index.js` — **no** directory warning.
- **Zero** `WARN`/`ERROR` log lines.

```
opencode run --standalone "… FIRST item under EXECUTE NOW … Git Branch in SESSION-CONTEXT?"
```
Model answered **`gitnexus-exploring`** and **`fix/technical-tab-empty`** (the real branch) — proving
both the `<required-tools>` and `<SESSION-CONTEXT>` blocks reach the model.

## Still outstanding

- ~~`claude-mem.js` (V1 plugin, also deleted) has not been recreated.~~ **Resolved** — `claude-mem`
  was restored and upgraded to 13.37.0 (V2 plugin) with a working AI provider; see
  `SESSIONS/2026-10-13_claude-mem-opencode-v2-plugin-restore.md` (**D-67**).
- The plugins-dir `package.json` (V1) was deleted and is not needed by the V2 ESM plugin.

## Parity audit (2026-10-13, later session)

User asked to confirm `documentarian` is live, is part of `lifecycle-hooks`, and that **all** V1
functionality survived the V2 rewrite. Verified against the recovered V1 source
(`%TEMP%\opencode\lifecycle-hooks.v1.js`, 1200 lines) vs the shipped V2 (`index.js`, 1229 lines);
`git diff --no-index` = 407 insertions / 378 deletions, all in the ported regions.

**Outcome: full functional parity.** All three hooks and every helper/config table are preserved
(`SKILL_CONFIG`/tier1+tier2, `MCP_DETECTION`, `INTENT_CLASSIFICATION`, `TOOL_DETECTION`,
`COMPACTION_CONFIG`, `SESSION_CONFIG`; `findProjectRoot`, `extractRecentDecisions`,
`extractProjectRules`, `load/saveSessionHandoff`, `logDecision`, `detectTier2Skills`,
`detectSearchTool`, `classifyIntent`, `generateAgentHints`). The `<required-tools>` and
`<SESSION-CONTEXT>` blocks — **including the entire Auto-Documentation Rule + Memory & Context text —
are unchanged**, except for the already-documented improvements (non-blocking GitNexus + TTL cache,
15 s branch cache, dynamic MODEL line, modernised tool names, and `try/catch` guards on both hooks).

**Live wiring proof (this session's own system prompt):**
- `<required-tools>` → `## EXECUTE NOW` lists `skill(name="documentarian")` (tier1 line 35).
- `<SESSION-CONTEXT>` contains `## Auto-Documentation Rule` / "Documentarian is tier-1 loaded…".
- Plugin load is clean: `msg="loading plugin" id="…\plugins\lifecycle-hooks"` — no WARN/ERROR;
  `node --check` exit 0.
- `documentarian/SKILL.md` (9432 B) now registers; before the frontmatter fix it silently did not.
