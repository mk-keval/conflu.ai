# Session Log: 2026-10-13 — `claude-mem` OpenCode V2 Plugin Restored + Install Aligned 13.3.0 → 13.37.0

> Environment/tooling work (not conflu.ai application code) — same Migration effort as the
> `lifecycle-hooks` session. Recorded here per the project's auto-documentation rule.

**Date:** 2026-10-13
**Branch:** fix/technical-tab-empty (unchanged — no repo source touched)
**Scope:** User's global OpenCode config (`%USERPROFILE%\.config\opencode\`), the machine-wide
`claude-mem` install (`%USERPROFILE%\.claude\plugins\…`, `%USERPROFILE%\.claude-mem\`), and the
global `AGENTS.md`.

## Prompt

Continue the V1→V2 OpenCode plugin restore. The first plugin, `lifecycle-hooks`, was already
recreated (see `2026-10-13_opencode-v2-migration-lifecycle-hooks.md`). The user asked to also
restore the second deleted global plugin: **`claude-mem`**.

## Problem

The original global file `~/.config/opencode/plugins/claude-mem.js` was **330,360 bytes** — the
claude-mem **13.3.0** OpenCode bundle, byte-identical to
`~/.claude/plugins/marketplaces/thedotmack/dist/opencode-plugin/index.js`. It used the **legacy V1
plugin shape** `(ctx) => ({ hooks, event, tool })`, which OpenCode **v2.0.28** rejects:

```
WARN message="failed to load plugin" target="…\plugins\claude-mem.js"
  cause="PluginModule.LoadError: Plugin must export a default definition with an id and an
  effect or setup function. (cause: SchemaError(Expected object at [\"default\"]))"
```

So the deleted file could not simply be copied back — it was itself one of the "broken" plugins.

## Research (ground truth)

- V2 plugin contract (`@opencode/plugin@2.0.28`): default export
  `{ id: string, setup(ctx) | effect }`.
- claude-mem ships **official OpenCode support**. The current release **13.37.0** publishes a
  genuine V2 bundle whose default export is `{ id: "claude-mem", server, setup }` and which uses
  real V2 APIs: `ctx.location`, `ctx.tool.hook("execute.after")`, `ctx.session.hook(...)`,
  `ctx.event.subscribe(...)`.
- The installer (`dist/npx-cli/index.js`) for OpenCode:
  - `findBuiltPluginPath` prefers `~/.claude/plugins/marketplaces/thedotmack/dist/opencode-plugin/index.js`,
    then falls back to the package's own `dist/`.
  - Copies the built bundle to `~/.config/opencode/plugins/claude-mem.js`.
  - For **OpenCode 2** it *removes* any `plugins` entry from `opencode.json` (V2 auto-loads the
    plugins directory) and registers the **`mcp.claude-mem` MCP server** instead.
  - Removes the legacy static `<claude-mem-context>` block from `AGENTS.md` (memory is now
    injected dynamically by the plugin, not the static file).

## What was done

1. **Instantiated the V2 bundle** at `%USERPROFILE%\.config\opencode\plugins\claude-mem.js`
   (485,090 bytes) from the npm `claude-mem@13.37.0` tarball — verified it loads cleanly and
   matches the npm bundle byte-for-byte (SHA-256 `51D00CE9…`).
2. **Ran the official installer** to align the whole install (plugin + worker + marketplace +
   cache) instead of leaving a plugin/worker version skew:
   ```
   npx --yes claude-mem@13.37.0 install --ide opencode
   ```
   Output: `claude-mem v13.37.0 · installed v13.3.0` → marketplace copied, cached v13.37.0,
   plugin registered/enabled, Bun + uv verified, worker configuration cut over.
3. **Satisfied the `claude_cli` dependency.** 13.37.0's worker requires a `claude` executable.
   None is on `PATH` and no `@anthropic-ai/claude-code` is installed globally — but OpenCode ships
   one with its Claude Agent SDK:
   `C:\Users\keval\.config\opencode\sdk\node_modules\@anthropic-ai\claude-agent-sdk-win32-x64\claude.exe`
   (`2.1.132 (Claude Code)`). Set in `~/.claude-mem/settings.json`:
   ```json
   "CLAUDE_CODE_PATH": "C:\\Users\\keval\\.config\\opencode\\sdk\\node_modules\\@anthropic-ai\\claude-agent-sdk-win32-x64\\claude.exe"
   ```
4. **Started the worker** (`npx claude-mem start`) and verified.

## Verification

| Check | Result |
|-------|--------|
| Plugin file | 485,090 B, SHA-256 matches npm 13.37.0 bundle ✓ |
| OpenCode log | `loading plugin …claude-mem.js` — no load error ✓ |
| MCP server | `mcp connected server=claude-mem tools=19` ✓ |
| Worker | `version=13.37.0`, `mcpReady=true`, `dependencies.degraded=false` ✓ |
| `GET /api/context/inject?cwd=…&platformSource=opencode` | **HTTP 200** (was HTTP 400 on the 13.3.0 worker — skew resolved) ✓ |
| Capture | log shows `ENQUEUED … type=observation`; DB grew 241 KB → 499 KB ✓ |
| MCP tools | `list_corpora`, `important_workflow`, `claude_mem_search` all respond ✓ |
| `AGENTS.md` | legacy static `<claude-mem-context>` block removed ✓ |

## Provider auth — resolved via the local OmniRoute gateway (no login needed)

The generator initially failed (`Not logged in · Please run /login`) because the machine has **no**
Claude Code credentials or API keys. Rather than logging in, the AI provider was pointed at the
user's **existing local OmniRoute gateway** using claude-mem's `openai-compatible` provider:

```json
{
  "CLAUDE_MEM_PROVIDER": "openai-compatible",
  "CLAUDE_MEM_OPENAI_COMPAT_BASE_URL": "http://localhost:20128/v1",
  "CLAUDE_MEM_OPENAI_COMPAT_MODEL": "openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
  "CLAUDE_MEM_OPENAI_COMPAT_API_KEY": "sk-…"
}
```

- OmniRoute is OpenAI-compatible and (verified) returns **non-streaming JSON** when sent
  `stream:false` — which is what claude-mem needs. The model is the user's own `title`-agent model
  (small/fast).
- The worker **re-read the settings live — no restart needed** (log: `Generator auto-starting …
  using OpenAI-compatible` immediately after the edit).
- **Verified end-to-end:**
  ```
  [SDK] Custom OpenAI-compatible endpoint API usage {model=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free,
        inputTokens=4984, outputTokens=866, totalTokens=5850}
  [DB ] STORED | memorySessionId=27233d02-… | obsCount=1 | obsIds=[1]
  ```
  and `claude_mem_search("claude-mem OpenCode plugin restore OmniRoute")` returns the observation.

### Residual notes

- Memory summarization now depends on OmniRoute (`http://localhost:20128`) being up and on the
  nano model's free-tier availability. Swap `CLAUDE_MEM_OPENAI_COMPAT_MODEL` for any of the ~841
  OmniRoute models if desired.
- `CLAUDE_CODE_PATH` / `CLAUDE_MEM_CLAUDE_AUTH_METHOD` are left in place so switching back to the
  Claude provider is a two-line change. (The bundled `claude.exe` lives inside OpenCode's SDK
  `node_modules`; if that SDK is pruned/updated, repoint it or install the Claude Code CLI normally.)
- Alternatives to claude-mem were surveyed and **not** adopted (claude-mem is purpose-built, already
  integrated, and now verified): `open-mem`, `total-agent-memory`, `agentmemory`, `Cipher`,
  `projectmem`, `remem`.

## Files touched (all outside the repo)

- `%USERPROFILE%\.config\opencode\plugins\claude-mem.js` — V2 plugin, 13.37.0.
- `%USERPROFILE%\.config\opencode\opencode.json` — added `mcp.claude-mem` server entry.
- `%USERPROFILE%\.config\opencode\AGENTS.md` — removed legacy static `<claude-mem-context>` block.
- `%USERPROFILE%\.claude-mem\settings.json` — provider/auth keys + `CLAUDE_CODE_PATH`.
- `%USERPROFILE%\.claude\plugins\marketplaces\thedotmack\…` — marketplace updated to 13.37.0.
- `%USERPROFILE%\.claude\plugins\cache\thedotmack\claude-mem\13.37.0\…` — new cache.
- Backups of the pre-change `settings.json`, `opencode.json`, `AGENTS.md`, plugin bundle:
  `%TEMP%\opencode\cm\bak\`.
