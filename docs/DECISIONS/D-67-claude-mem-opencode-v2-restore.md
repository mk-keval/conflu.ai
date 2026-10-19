# D-67: `claude-mem` OpenCode V2 Plugin Restore — Install Upgraded 13.3.0 → 13.37.0

**Status:** Accepted — fully operational (provider auth resolved via local OmniRoute, no Claude login needed)
**Date:** 2026-10-13
**Scope:** Environment/tooling (user's machine-wide `claude-mem` + global OpenCode config).
Not conflu.ai application code.

## Context

The user's global OpenCode plugins were deleted during the V1→V2 migration. `lifecycle-hooks`
was reconstructed first. The second plugin, `claude-mem`, was found to be **unrecoverable as-is**:
the deleted `~/.config/opencode/plugins/claude-mem.js` was the claude-mem **13.3.0** OpenCode
bundle, which uses the **legacy V1 plugin shape** `(ctx) => ({ hooks, event, tool })`. OpenCode
**v2.0.28** requires the V2 contract `{ id, setup(ctx) | effect }` and rejects the legacy shape:

```
Plugin must export a default definition with an id and an effect or setup function.
```

`claude-mem` publishes **official OpenCode support** and, since 13.37.0, a genuine V2 bundle
(`{ id: "claude-mem", server, setup }`; uses `ctx.location`, `ctx.tool.hook`, `ctx.session.hook`,
`ctx.event.subscribe`). The installed version was 13.3.0 — three minor lines behind — so the
matching OpenCode plugin and the worker were **version-skewed**.

## Decision

Restore `claude-mem` in OpenCode V2 by **aligning the whole install to 13.37.0** rather than
hand-porting the legacy bundle or running an orphaned plugin against a stale worker.

1. Install the **13.37.0** V2 bundle to `~/.config/opencode/plugins/claude-mem.js` (auto-loaded by
   V2; no `plugins` entry needed).
2. Run the official installer (`npx --yes claude-mem@13.37.0 install --ide opencode`) to update
   the marketplace + cache + worker and to register the `mcp.claude-mem` MCP server in the global
   `opencode.json`. The installer also **removes** the legacy static `<claude-mem-context>` block
   from `AGENTS.md` (memory is now injected dynamically).
3. Satisfy the worker's new `claude_cli` dependency by pointing `CLAUDE_CODE_PATH` at the Claude
   Code CLI bundled with OpenCode's Agent SDK
   (`…\config\opencode\sdk\node_modules\@anthropic-ai\claude-agent-sdk-win32-x64\claude.exe`,
   v`2.1.132`), since no `claude` is on `PATH`.

### Alternatives considered

- **Keep 13.3.0 and hand-port the legacy bundle to V2** — rejected: large surface, and the 13.3.0
  worker rejects the 13.37.0 plugin's context-inject call (`/api/context/inject` → HTTP 400).
- **Run a 13.37.0 worker from a temp/parallel location without touching the install** — rejected:
  fragile (temp cleanup), and leaves two divergent installs.

## Consequences

- **Works:** plugin loads cleanly; MCP connects (19 tools); worker `13.37.0` `degraded=false`;
  `/api/context/inject` returns **HTTP 200**; observations are captured (`ENQUEUED`) and the DB
  grows; `claude_mem_search` + MCP tools respond.
- **Blast radius (accepted):** the upgrade is machine-wide and shared with the user's Claude Code
  install (marketplace + cache + the same `~/.claude-mem` DB). Intended — it removes the skew.
- **Provider auth — RESOLVED (no Claude login needed):** the generator initially failed with
  `Not logged in · Please run /login` because the machine has no Claude Code credentials or API
  keys anywhere. Rather than logging in, the provider was pointed at the user's **existing local
  OmniRoute gateway** via claude-mem's `openai-compatible` provider (which explicitly supports
  local endpoints):
  ```json
  "CLAUDE_MEM_PROVIDER": "openai-compatible",
  "CLAUDE_MEM_OPENAI_COMPAT_BASE_URL": "http://localhost:20128/v1",
  "CLAUDE_MEM_OPENAI_COMPAT_MODEL": "openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
  "CLAUDE_MEM_OPENAI_COMPAT_API_KEY": "sk-…"
  ```
  The model is the user's own `title`-agent model (small/fast; verified to return **non-streaming
  JSON** from OmniRoute — claude-mem requires `stream:false`, and OmniRoute honours it). The worker
  **picked the change up live — no restart required**. Verified end-to-end:
  `Custom OpenAI-compatible endpoint API usage {model=…, totalTokens=5850}` →
  `DB STORED … obsIds=[1]` → `claude_mem_search` returns the observation.
- **Trade-off:** memory summarization now depends on OmniRoute (`http://localhost:20128`) being up,
  and on the nano model's free-tier availability. `CLAUDE_CODE_PATH` and
  `CLAUDE_MEM_CLAUDE_AUTH_METHOD` are left in place, so switching back to the Claude provider is a
  two-line change. The model can be swapped for any of the ~841 OmniRoute models.
- Considered alternatives to claude-mem (kept it anyway — purpose-built, already integrated, and
  now verified): `open-mem` (native OpenCode plugin, MIT), `total-agent-memory`, `agentmemory`,
  `Cipher`, `projectmem`, `remem`.
- **Fragility:** `CLAUDE_CODE_PATH` points inside OpenCode's SDK node_modules; a future SDK
  change may require repointing (or a proper global Claude Code CLI install).
- Backups of all pre-change files are at `%TEMP%\opencode\cm\bak\`.

## References

- Session log: [`docs/SESSIONS/2026-10-13_claude-mem-opencode-v2-plugin-restore.md`](../SESSIONS/2026-10-13_claude-mem-opencode-v2-plugin-restore.md)
- Companion: `docs/SESSIONS/2026-10-13_opencode-v2-migration-lifecycle-hooks.md` (first plugin)
