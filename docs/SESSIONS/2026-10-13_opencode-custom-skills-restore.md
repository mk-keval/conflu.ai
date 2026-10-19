# Session Log: 2026-10-13 — Fixed/Recovered Three Custom OpenCode Skills (`documentarian`, `ai-slop-remover`, `tvscreener-specialist`)

> Environment/tooling work (not conflu.ai application code). Companion to the OpenCode V1→V2
> migration + `claude-mem` restore sessions.

**Date:** 2026-10-13
**Branch:** fix/technical-tab-empty (no repo source touched)
**Scope:** `%USERPROFILE%\.config\opencode\skills\` (global skills)

## Prompt

After an earlier session noted the injected `<required-tools>` block referenced `documentarian` and
`ai-slop-remover` (neither of which appeared in the loaded skills list), the user corrected:
"documentarian was a custom skill built, it should be already there!"

## Findings

`lifecycle-hooks` has a **tier-1 auto-load list** (`plugins/lifecycle-hooks/index.js`):

```js
// Tier 1: Auto-load (always inject skill content)
tier1: [
  ...
  'documentarian',            // Keep docs updated (auto-documentation enforcement below)
  'ai-slop-remover',          // Code quality safety net - always loaded
]
```

…so on every prompt it injects `EXECUTE NOW: skill(name="documentarian")` and
`skill(name="ai-slop-remover")` — but **neither skill was actually loadable**:

1. **`documentarian` existed but was inert.** `~/.config/opencode/skills/documentarian/SKILL.md`
   was a prose document with **no YAML frontmatter** (it began with `# Documentarian Skill`; first
   bytes `23 20 44 6F 63…`). Every skill OpenCode registers starts with `---\nname: …\ndescription:
   …\n---`; without frontmatter the loader silently skips the file.
2. **`ai-slop-remover` did not exist at all** — no file or directory matching `*slop*` in
   `.config/opencode`, `.claude`, or the project. Its complete body was **recovered from session
   transcripts** (`~/.claude/transcripts/*.jsonl`), which contained the loaded skill output from
   July 2026 sessions (`## Skill: ai-slop-remover … You are an expert code refactorer specializing
   in removing AI-generated "slop" patterns while STRICTLY preserving functionality.`).
3. **`tvscreener-specialist` existed but was inert** — the project-level
   `.claude/skills/tvscreener-specialist/SKILL.md` (a detailed `tradingview-screener` domain
   specialist) also had **no frontmatter**; it used a prose `**Description:**` line instead. Found
   by sweeping every `SKILL.md` under the project + config + `~/.claude/skills`.

> Note: OpenCode scans **both** the global config skills dirs (`~/.config/opencode/skills/` and
> `~/.config/opencode/skill/`) **and** the project's `.claude/skills/`.

## Fix

- Added frontmatter to `skills/documentarian/SKILL.md` (`name`, `description`, `trigger`) — kept the
  original body untouched.
- Recreated `skills/ai-slop-remover/SKILL.md` (frontmatter + recovered body: detection criteria for
  obvious comments / over-defensive code / spaghetti nesting, safety rules, report format).
- Added frontmatter to `.claude/skills/tvscreener-specialist/SKILL.md` (project skill).
- Copied `tvscreener-specialist` to the **global Claude skills dir** (`~/.claude/skills/`) so it is
  available across projects (user request). The project copy is retained; OpenCode watches both
  `~/.claude/skills/` and `~/.config/opencode/skills/`, so either location is picked up.

## Verification

All three skills registered **live — no restart required**. OpenCode rescans the skills directories
and the harness confirmed each with a "New skills are available in addition to those previously
listed" update; `skill(id="documentarian")` returned its content.

## Lesson

A custom skill silently fails to load when its `SKILL.md` lacks `name` + `description` frontmatter,
so a tier-1 `EXECUTE NOW: skill(name=…)` line can point at nothing. Worth keeping in mind when
authoring custom skills (see the built-in `writing-skills` guidance).
