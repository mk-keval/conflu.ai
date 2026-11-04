# Session Log — Gate Enforcement Spine: Planning

**Date:** 2026-09-16 · **Branch:** `fix/technical-tab-empty` · **Type:** Planning only (no application source modified)

**Related:** `docs/SESSIONS/2026-09-16_paper-trade-evidence-audit.md`, `docs/DECISIONS/D-50-paper-trade-exit-capture-schema.md`

---

## Context

Immediately following the paper-trade evidence audit (31 rows, 0 exits — a candidate dump, not trades), the user asked to plan all three corrective slices before any implementation:

1. Enforce the 7-step gate in the path that actually writes trades
2. Position tracking + Portfolio Fit
3. Collapse the daily process to 1-2 touchpoints

## Action taken

Full codebase recon, then a plan document. **No application source was edited.**

### Recon performed

| Area | Result |
|---|---|
| `backend/scripts/paper_trade_from_brief.py` | Read in full. Confirmed: no gate, no rejection path, no exit path. Found 3 latent bugs + dead code (see below) |
| `frontend/src/workflow/gate.ts` | Read in full. 5-step gate; thresholds already correct (2.5:1, $10M ADV); designed to degrade missing data to `CONDITIONAL` |
| `frontend/src/store/workflowStore.ts` | **Key finding** — already holds `paperTrades` + `openPaperTrade`/`closePaperTrade` + `validationGates`, localStorage-persisted, invisible to the backend |
| `backend/app/domain/ticker_analysis/models.py` | `TradePlan` geometry already complete (scale_in/out, trail, max_hold_days, `max_position_pct=10.0`). `AnalysisVerdict` uses `extra="forbid"` |
| `backend/app/domain/ticker_analysis/technical.py:410-415` | Only a volume *ratio* — no dollar ADV |
| `backend/app/domain/ticker_analysis/synthesis.py:1586,1622` | Single verdict construction site; D-44 caps conviction at 5 **after** the trade plan is built |
| `backend/app/api/routers/__init__.py`, `main.py:197-208` | Router registration pattern confirmed |
| `ELITE_SWING_TRADING_BLUEPRINT.md:228-307` | 7-step taxonomy + the T1/T2 R:R distinction |
| GitNexus impact | `_generate_trade_plan` = **LOW** (1 caller). `AnalysisVerdict` = **HIGH** (26 impacted / 15 direct) but all `IMPORTS` — additive field, no breakage. `build_row` **not in graph** (script dir unindexed) |
| grep `*.py` for `paper_trades` | **No matches** — the journal is currently write-only; Slice 2 creates its first reader |

### Newly found defects (not in the audit)

1. **`confluence_count` is lossy** — `brief_section["confluence_score"] // 20` collapses a 0-100 score to 0-5 (`paper_trade_from_brief.py:92`).
2. **Blank stop can be written** — `v.get("stop_loss") or ""` writes an empty string instead of refusing the trade (the VZ case, `:88`).
3. **`--regime-only` is dead code** — the filter mutates `section["tickers"]` *after* candidates are already collected (`:133-135`).
4. **`max_position_pct=10.0` is never enforced** — audit max was 16.5% (`models.py:212`).
5. **`pnl_usd` is uncomputable** — no account size is recorded anywhere in the journal schema.
6. **Target-basis ambiguity** — the blueprint's 2.5:1 floor is specified *at Target 2*; it is unverified whether `synthesis.py`'s `rr` uses T1 or T2. If it uses T1, the gate and the metric disagree (flagged as the highest-value open question).

## Deliverable

`.sisyphus/plans/gate-enforcement-spine.md` — 14 sections covering all three slices, grounded in file:line evidence.

Notable contents:
- **Sec.3 Expectations** — enforcing 2.5:1-to-T2 rejects **~93%** of current output (2/30 in the sample). ~1-2 trades/week. Reaching n=30 takes months. This is the single most likely reason the project gets abandoned, so the plan requires that a *quiet day read as success*.
- **Sec.4 Deltas** — 5 explicit reversals of `phase1-elite-guided-workflow.md` v2.1 (5-step → 7-step gate; frontend → backend decider; adherence → expectancy north-star; localStorage → CSV-as-state; 4-stage → 2 touchpoints).
- **Sec.2E Flagship idea** — **self-closing exits**: infer fills from daily OHLCV (gap/stop/target/time-stop), conservative on intrabar ambiguity, `--dry-run` mandatory, no broker integration, no scheduler. This is what makes n=30 reachable.
- **Sec.6 Schema v2** — amend D-50 to 25 columns (`+entry_type`, `+account_value`, `+gate_verdict`, `+gate_failed_step`, `shares` moved to the entry block). D-50 has zero rows written against it, so amending beats versioning.
- **Sec.12** — 7 decisions required from the user (gate strictness, R:R target basis, cap semantics, TS gate deletion, schema amendment, auto-exit default, localStorage reconciliation).

## Plan review

**Momus did not run** — `bg_caa36517` failed with `429 free-models-per-day` (openrouter/poolside/laguna-s-2.1:free). Per the user's standing instruction ("if a sub task does not work please stop calling using that model, you can finish the task yourself"), **no retry was attempted**; the critique was performed directly in the main session.

### Self-review findings — 4 substantive problems in the draft

| # | Problem | Resolution |
|---|---|---|
| **S1** | **R:R is gameable by widening the stop (R15).** Nothing constrained stop *distance*, so a 30.6% stop can clear 2.5:1 with a 76% target. **BULL (R:R 3.99, stop 22.8%) would have PASSED Gate Step 5** — the single best-looking row in the cohort is also one of the worst risk profiles | New phase **1E**: `MAX_STOP_DISTANCE_PCT` ceiling (~10%), plus a reward-ladder shape test. New decision **D8**. New acceptance criterion: BULL must fail |
| **S2** | **Scale-out collides with single-R accounting (R16).** `scale_out` is 30/30/40 + trail, so `realized_r` is a tranche blend — the Sec.2E formula would silently mis-report every scaled trade | New phase **1G** + decision **D9**: single target/stop for v1; `scale_out` marked advisory |
| **S3** | **The journal's epistemic boundary was unstated.** Auto-inferred exits measure the *strategy's* outcome, not the *user's* execution — every trade resolves, forgotten brackets vanish. Reporting that as "your performance" would be false | New phase **1F**: journal measures **edge**, not execution; the review surface must be labelled "strategy outcome" |
| **S4** | **Sequencing error in my own critical path.** The draft ran enforcement (1D) *before* sizing (2D), so the first weeks of the new sample would have recorded the old `position_size_pct or 5.0` fallback — contaminating the exact data the plan exists to collect, with a defect the plan had already identified (R4/R7) | Sec.8 rewritten: **2A → 2D now precede 1D**. Sizing is small and independent |

### Improvement adopted

**R17 → Phase 0A: the historical control study.** The 31 voided rows are the only ungated sample that will ever exist, and their exits are inferable by the same OHLCV logic as Sec.2E. Replaying them (read-only) yields the counterfactual the rest of the plan cannot produce: *would the gate have improved outcomes, or only reduced trade count?* It also gate-tags each row, validating the gate's **logic** before it refuses a single live trade — and gives a first read on `MAX_STOP_DISTANCE_PCT` without tuning against live results. Caveat written into the plan: n=30 is directionally informative only.

**Still explicitly forbidden:** using those 31 rows to fit *thresholds*. Sec.9 tightened to say so, with "if Phase 0A tempts a threshold change, that is a red flag, not a result."

### Also verified

- All cross-references consistent: R1-R17, D1-D10, phases 0A-2E all defined and used; no dangling `Sec.` refs (453 lines)
- Fixed one broken cross-ref (`D2 in Sec.6` → `D1 in Sec.12`) and one duplicated clause in the 1D frontend note

## Verification

- Planning-only: no `lsp_diagnostics` / test run applicable.
- All recon claims carry file:line references and were read directly, not inferred.
- Plan is internally consistent with the audit's numbers and D-50's decisions.
- Cross-reference lint passed (script-checked, not eyeballed).
- Awaiting: user decisions in Sec.12 (now **D1-D10**).

## Pre-code recon V1-V5 — resolved (and V4 broke the plan's premise)

All five open items from Sec.13 were answered by direct reading, with file:line. **Four resolved cleanly; one invalidated part of the plan.**

| Item | Answer |
|---|---|
| V1 | **Partial.** No daily/weekly trend label on `TechnicalAnalysis` (`models.py:28-53`). Per-timeframe labels live in `ChartReadingAnalysis.daily/.weekly` → `structure_label` (`models.py:105-106`), **populated only when chart reading ran (needs OHLCV)**. Step 2 must degrade to CONDITIONAL on a missing label |
| V2 | Deferred to the D-46 surface; no new blocker. Step 3 remains buildable |
| V3 | **Answered, populated.** `orchestrator._analyze_catalyst_bias` (`orchestrator.py:243`) → `tv_data["catalyst_bias"]` (`:671-672`) → read at `synthesis.py:944-949`. **Step 3 needs no new data source** |
| V4 | **Answered — the question was wrong.** See below |
| V5 | **Safe.** Only 4 construction sites; adding an *optional* `gate` field cannot trip `extra="forbid"` (rejects *unknown* kwargs only). **No test breakage from Sec.1C** |

### V4 — the R:R contract is broken at the source

I asked "which target does `rr` use?" — assuming `rr` was *derived* from a target. It isn't. The direction is inverted:

```python
rr = _calculate_dynamic_rr(technical, risk, fundamental, action)   # :1460
#   base 1.5; +0.5 strong trend; ±vol; +fundamentals;
#   capped 3.0 for BUY, floored 1.0  -> a DESIRED ratio
t1 = round((entry_high or close) + risk_per_share * 1.0, 2)        # :1465  always exactly 1.0R
t2 = round((entry_high or close) + risk_per_share * rr,  2)        # :1466  manufactured to satisfy rr
```

**The engine decides the ratio it wants, then places the target wherever that ratio falls.** Nothing checks whether price can reach it. So the reported `risk_reward` is not a measurement of the chart — it is a **declaration**.

**Consequence for the plan: Gate Step 5 as drafted would have validated a number authored by the same subsystem it exists to police.** The 2.5 floor would compare against a self-declared aspiration with a known 1.0-3.0 range — close to tautological.

Four further findings fell out of this (plan Sec.13b, R18-R22):

- **R19** — `verdict.risk_reward` is **two different quantities under one name**. `_enforce_plan_geometry_invariants` recomputes it *geometrically* (`_geometric_rr_long`, `:183-198`) and **overwrites** the field (`:334`, `:344`) when the heuristic was below 2.0; on total failure it nulls `rr` and downgrades to WATCH (`:348-357`). Nothing records which path produced the number. **A consumer cannot tell an aspiration from a measurement.**
- **R20** — `target_1` is hardcoded at exactly **1.0R** (`:1465`). It carries **zero chart information**. The audit, the Sec.1E reward ladder, and D2 all treated it as a real price objective. It is not. The scale-out schedule (30% at 1.0R), `move_to_breakeven_at_r = 1.0`, and `trail_activation_r = 1.0` are anchored to the same manufactured number.
- **R21** — **R4 was understated.** `plan.max_position_pct = min(10.0, position_size * 1.5)` (`:1748`) is *derived from* the size — it reports, it does not cap. The binding limit is `conviction_caps` (`:1487-1495`): **up to 25%**. Four caps exist and the README's "5%" matches none. Sec.2D is not "enforce the existing cap" — **there is no cap to enforce.**
- **R22** — Target construction uses `entry_high` (`:1464`); geometric measurement uses zone **midpoint** (`:194`). One plan, two honest R:R values.

### Actions taken

- Plan corrected: **BUILD HOLD banner** for Step 5; Sec.13 rewritten as resolved with the V1-V5 answers; **new Sec.13b** carrying R18-R22; **D2 withdrawn and reframed** (it was based on a false premise); **D3 rewritten** (no cap exists); Sec.14 flagged that a source fix in `synthesis.py` is a far larger blast radius than "attach a field".
- **Phases blocked**: 1D, 1E, 2E, 0A. **Phases not blocked**: 1A, 1B, 1C, 2A, 2B, 2C.
- **Oracle consulted** (`bg_70634165`) on the design question — gate-on-recomputed-geometry vs fix-the-engine-at-source vs both — plus whether midpoint is the trader-correct entry basis, whether a 2.5 floor is meaningful against a 1.0-3.0-bounded field, and whether the gate should be built before or after the source fix.

**No code written.** No application source modified.

---

## Follow-up pass — the plan's own headline statistic was re-verified and found WRONG

The plan's central justifying number was **"only 2/30 (7%) of emitted setups reach the blueprint's 2.5:1 floor"** — used in Sec.2, Sec.3, D1 and the risk register to predict ~93% rejection and therefore 1-2 trades/week.

**It measured the wrong target.** Re-derived read-only from the archive via `C:\Users\keval\AppData\Local\Temp\opencode\verify_rr_basis.py`:

| basis | n | min | median | mean | max | **≥ 2.5** | ≥ 2.0 | ≥ 1.5 |
|---|---|---|---|---|---|---|---|---|
| `rr1 = (t1 - e)/(e - s)` — what was reported | 30 | 0.43 | 1.53 | 1.61 | 3.99 | **2/30 = 7%** | 8/30 | 15/30 |
| `rr2 = (t2 - e)/(e - s)` — what the blueprint means | 30 | 0.60 | 2.20 | 2.39 | 4.60 | **11/30 = 37%** | 23/30 | 25/30 |

The blueprint's 2.5 floor is **at Target 2**. The audit had computed Target 1.

**Corroborating fingerprint:** exactly **4/30** rows show `rr1 == 1.00` to the cent — PAGP, LNG, CVX, CVX — which is the mechanical signature of `t1 = entry + risk_per_share * 1.0` (`synthesis.py:1465`). The other 26 are inconsistent with *either* construction rule, meaning the structural-replacement path fired.

### The larger conclusion — selectivity is not measurable from this cohort at all (R24)

The cohort's targets were **engineered** to clear R:R ≥ 2.0: `_enforce_plan_geometry_invariants` aims at exactly that bar, and `_get_structural_targets_long` keeps the **farthest** three structural levels (`sorted(set(...))[-3:]`, `:178`, justified in-comment as "extension exists to reach R/R via the far liquidity pool").

So `rr2`'s 77%-clear-2.0 measures **the repair mechanism's success rate at the bar it was built to hit** — not the quality of the setups. **Neither 7% nor 37% answers "how selective is this system."** The throughput estimate is **withdrawn as unknowable pre-fix**.

Also established: the CSV records neither `entry_low`/`entry_high` nor the derived `rr`, so **the R:R basis is not reconstructible from the recorded ledger** (R25) — which is why the plan now argues for three schema additions, and why the T1/T2 question was unanswerable until a script re-derived it.

### Design resolution written as Sec.15 (Oracle substituted, not retried)

Oracle (`bg_70634165`) failed with the **same 429** (`openrouter/poolside/laguna-s-2.1:free`, free-models-per-day) as Momus. Per the user's instruction — *"if a sub task does not work please stop calling using that model, you can finish the task yourself"* — **no retry**. Design answered in-session instead, written into the plan as **new Sec.15** with an explicit caveat that it substitutes for missing external review:

- **Q1 (the fix):** make the **existing conditional repair unconditional** — targets from structure, R:R *measured*; delete `_calculate_dynamic_rr` from target construction. **The gate performs a one-multiply consistency assertion** (`|(target - entry_basis)/(entry_basis - stop) - rr| ≤ tol`), **not** a recomputation — a second calculator would diverge silently, which is the disease being cured. Rejected gating-alone, which leaves every other consumer reading a dishonest number.
- **Q2 (entry basis):** the asymmetry is the bug, not the choice. The plan's own scale-in schedule (50% @ `entry_high`, 30% @ `low+0.3·range`, 20% @ `low`) implies `fill ≈ mid + 0.09·range`, so **midpoint is a good but slightly flattering approximation**; one explicit basis must be chosen and recorded. Flagged separately: weighting 50% of the position at the *worst* price deserves its own review.
- **Q3 (2.5 floor):** near-tautological against the heuristic field (bounded 1.0-3.0, floored at 1.0 — it restates inputs); meaningful only against a geometric field; **uncalibratable from this cohort** (R24). Adopt from the blueprint, accept it is unvalidated.
- **Q4 (`target_1` / scale-out):** `target_1` has **two meanings** (mechanical 1.0R, or nearest structural level) → untrustworthy. The scale-out is **doubly defective**: 30/30/40 tranche-blend breaks the `realized_r` formula *and* it exits at "1R" while `target_1` may sit elsewhere — **the exit plan can contradict the plan's own levels**. **Single exit for v1 (D9) now recommended with higher confidence.**
- **Q5 (sequencing):** build the R:R-independent work now. **Wave 1** = 1A, 1B, 1C, 2A, 2B, 2C, **0A-i**. **Wave 2** = **1H** (the blocker). **Wave 3** = 1E, 2D, 1D, 2E, 0A-ii, Slice 3.
- **Phase 0A unblocked by splitting it:** 0A-i (exit backfill + **manufacture detector** over 30 rows) needs only *internal consistency*, not an honest R:R — so it is **unblocked and is the strongest available action**, converting R18/R19/R20 from a code-reading into a measurement.
- **New recon V6:** does `_get_structural_targets_long` actually find structural levels in practice, or quietly fall back? The fallback is **silent** (`structural_targets = list(current_targets)`, `:146`) so "found" and "not found" are indistinguishable in output. **Must be answered before 1H.**

### Plan edits applied in this pass

- Corrected **Sec.2/Sec.3** — rr1 vs rr2 table, withdrawal of the forecast, reframed expectation-setting.
- **Sec.3b corrected by measurement**: the stop-distance ceiling is **cheaper than originally claimed** — of the six highest-T2-R:R rows only **BULL (22.8%) fails a 10% ceiling**; PSX (4.6%), DOCU (6.5%), LRCX (5.7%), MU (6.5%) all have tight stops *and* high R:R. So it is a **targeted outlier guard, not a mass filter** (~5 rows). Earlier framing overstated its footprint; both the guard and its low cost are now argued from measurement.
- **New R23-R26** formally added to Sec.13b.
- **Sec.8 rewritten** into three waves with 1H as the critical path; **Phase 0A split** into 0A-i / 0A-ii.
- **Sec.9 bullet REVERSED**: "No target-derivation rework" → now explicitly reversed, with **REV6** added to Sec.4's reversal table.
- **D1** justification replaced (no fake number); **D5** extended to **28 cols** (`+entry_low`, `+entry_high`, `+risk_reward_planned`); **D9** strengthened.
- **Sec.14** updated: `+test_rr_contract.py`, `+fixtures/rr_contract_vectors.json`, **D-51 for the 1H source fix**, D-52 for the gate.
- **Banner** rewritten: design resolved, R18-R26, corrected table, Wave 1 buildable now.
- **Cross-ref lint passed (as of that pass)**: 608 lines; R1-R26 all defined, D1-D10 all defined, all 15 sections present, no unresolved citations. (Superseded by Pass 4 below: now 630 lines / 16 sections.)

**No code written. No application source modified. Nothing committed.**

## Next steps

1. User decisions on Sec.12 (**D1-D10**) — notably **D5** (now 28 cols) and **D9** (single exit).
2. **Phase 0A-i first** — cheap, read-only, now unblocked, and it *measures* the R:R defect over 30 real rows.
3. Answer **V6** (structural-level coverage) before committing to 1H.
4. Wave 1 build at **1A**, per the three-wave ordering in Sec.8 — **not** the old linear path.

## Pass 4 — Unicode normalization + anti-hallucination verification (2026-09-16)

User flagged "weird signs like Sec. / REV" and asked to confirm we are **not pushing hallucinated plan/text**. Treated as two separate questions: (a) are the characters corrupted, (b) is the content fabricated.

**Verification findings — no corruption, no fabrication:**

- **Character audit** (`char_inventory.py`): **0 mojibake** across all touched files; every file decodes as valid UTF-8; every non-ASCII char resolves to a real Unicode name. The flagged `Sec.` sign was U+00A7 (40 uses = section references); the flagged delta was U+0394 (14 uses = the reversal table index). **Not corruption, not invented.**
- **Citation audit** (`verify_citations.py`): **29 file:line claims checked against live source -> 0 unresolvable.** The load-bearing ones are **exact**:
  - `synthesis.py:1465` `t1 = round((entry_high or close) + risk_per_share * 1.0, 2)` — the 1.0R hardcode (R20)
  - `synthesis.py:1466` `t2 = round((entry_high or close) + risk_per_share * rr, 2)` — target manufacture (R18)
  - `synthesis.py:82` `return round(max(1.0, base_rr), 2)` — the 1.0 floor
  - `synthesis.py:178` `structural_targets = sorted(set(structural_targets))[-3:]` — farthest-3 levels (R24)
  - `synthesis.py:194` `mid = (entry_low + entry_high) / 2` — midpoint basis (R22)
  - `synthesis.py:307` `if action in long_actions and rr is not None and rr < 2.0:` — repair is conditional (R26)
  - `synthesis.py:1748` `plan.max_position_pct = min(10.0, position_size * 1.5)` — derived, not capped (R21)
  - `paper_trading_validator.py:139` `= 0.20` and `professional/models.py:217` `= 0.05` — two of the four conflicting caps (R21)
  - => the core findings R18-R26 are **verified against live source, not inferred.**

**Hardening applied — decoration removed, meaning kept:**

- Normalized decorative Unicode to ASCII (`normalize_ascii.py`): box drawing -> `-`/`|`/`+`; emoji status -> `[OK]` / `[WARN]` / `[DEFERRED]` / `[BLOCKED]`; `=>` and `>` for the double/right arrows; U+2212 MINUS SIGN -> ASCII hyphen (invisible but grep-hostile); section sign -> `Sec.`; reversal table retitled and its index renamed to `REV1..REV7`.
- **Deliberately KEPT repo-native typography** (em-dash, rightwards arrow, `>=`, `<=`, multiplication sign, middle dot, approx) because `INDEX.md` and `docs/index.md` already use it heavily — only what *this session* introduced as decoration was stripped. Em-dash count in `INDEX.md` is unchanged (84).
- Non-ASCII counts: plan **892 -> 308**, session log 127 -> 84, `INDEX.md` 175 -> 161, `docs/index.md` 134 -> 125.
- **R19 citation corrected** to describe the actual recompute -> validate -> return chain (`:329-334`, `:341-344`) rather than calling a `return` statement an "overwrite".
- Rationale for treating this as more than cosmetic: this repo has **already been burned twice** by exactly this class of bug — **D-42** (UTF-8 double-encoding across 5 files) and **D-43** (CP1252 round-trip that silently broke the API) — and the bypass script itself still has live cp1252 `UnicodeEncodeError` bugs at `paper_trade_from_brief.py:144/157`.

**Verifier bug fixed — a false FAIL is itself a false signal:**

- `final_check.py` had been reporting **FAIL** due to two bugs of its own:
  1. its mojibake regex included `a-circumflex + en-dash`, which **literally matches the intentional quote at `INDEX.md:62`** — the 2026-08-30 entry that deliberately quotes the corrupted arrow bytes while documenting their fix. Fixed: the pattern now covers only real accidental-mojibake signatures, and intentional historical quotes are **reported separately** instead of failing the check.
  2. its R-definition regex only matched the bullet form `**R18` (9 findings) and **missed the table form `| R1 |`**, so it falsely declared R1-R17 unresolved. Fixed: the regex now accepts **both** shapes.
- Re-run result: **PASS** — mojibake 0, R **26/26** defined, D **10/10** defined, 16 sections, all 4 `~93%` hits confirmed inside retractions.
- Principle recorded: **never tolerate a checker that emits a false FAIL** — it trains you to ignore the check.

**Post-normalization verification:** `lint_plan.py` 630 lines / R1-R26 / D1-D10 / 16 sections; `fence_check.py` 16 fences balanced; `final_check.py` PASS; `char_inventory.py` mojibake 0.

**No code written. No application source modified. Nothing committed.**

---

## Pass 5 — Schema grows 29→(narration wiring verified); learning slice scoped (mentor voice currently dropped)

**Context (handoff after compaction):** continuing the gate-enforcement spine planning. The 29-col TEMPLATE + D-51 schema v2 are already recorded (Pass 4). This pass answers the user's standing, repeated requirement — *"our system must explain so that anyone can understand and learn"* — by verifying the teaching layer's true state and scoping the one additive wiring fix. Two parallel `explore` recon agents returned (both DONE, sessions `ses_f52a6c1e2ffe5F3QblrAr7rRKr` + `ses_f52a6c1d0ffeVGWBBMOyBocPku`).

**Defect 1 — the mentor voice is generated, then silently dropped (THE learning gap):**
- Backend builds the full mentor narration — `narration.py`/`synthesis.py` `build_narration()` → `why_this`, `why_now`, `what_kills_it`, `thesis_one_liner` — and attaches it to `AnalysisVerdict.narration`.
- **Frontend `AnalysisVerdict` type OMITS `narration` entirely** (`frontend/src/types/tickerAnalysis.ts:95-117`). Grep for `narration|\.narration\b|verdict\.narration` across all of `frontend/src` → **0 matches**. The narration is serialized on the wire but never read by any component; nothing renders it.
- This is the **same "produced but not consumed" class as D-51's schema finding** — and it is exactly what the user means by "our system is not easy, user cannot learn." The richest explanation surface in the system is dead weight.

**Defect 2 — LLM education is key-gated:** `EducationService._maybe_enhance_with_llm` is fully built but silent without `llm_education_enabled` + `llm_api_key`; template fallback is the only path for a zero-key user. Acceptable as designed (fallback), but worth noting.

**What ALREADY exists and is beginner-grade (NOT a gap — do not rebuild):**
- 165-term live glossary (`education.json`, D-35 SSOT) → `TermLink` auto-glossing + `EducationTooltip` + `LearnPage` guided paths.
- Per-metric `MetricLesson` (what / whyMatters / scoringImpact / commonMistakes / example) + `verdictWalkthrough()` step-by-step verdict reasoning on the ticker page (`education.ts`, 668 lines).
- 5-step `ValidationGate` with per-step plain-English `GATE_WHY` teaching copy, surfaced as a modal walkthrough at rejection time (`gate.ts`, `ValidationGate.tsx`).
- `MentorNarration` backend (`why_this`, `why_now`, `what_kills_it`, thesis one-liner) + `planSteps.ts` 13-step plan taxonomy.
- Progressive disclosure: 8 features unlock over 90 days (`professional.ts:163-179`) — the beginner is never shown everything at once.

**Recommendation (additive, no new machinery):** wire the ALREADY-BUILT narration through to the user — (a) add `narration` to the frontend `AnalysisVerdict` type, (b) render `why_this`/`why_now`/`what_kills_it`/`thesis_one_liner` on the ticker page Where the verdict shows, (c) on gate REJECT, render `gate_failed_step` → its `GATE_WHY` teaching copy → plain-English "what would let it pass," reusing existing gate/education copy. This is a wiring+render fix, not a new system. Decision to be recorded as **D-54** pending user confirmation of the mechanism.

**Plan impact:** additive learning slice — folds into the existing enforcement spine wave list (Wave-1 slices unchanged: 1A→1B→1C→1D; learning slice rides alongside as an additive wiring wave). No renumbering of R1-R26 / D1-D10. Proposed D-54.

**Post-normalization verification:** plan still 655 lines / R1-R26 / D1-D10 / 16 sections; `lint_plan.py` + `final_check.py` PASS (re-lint after any further plan edit).

**No code written. No application source modified. Nothing committed. Scheme doc D-54 pending user confirmation; no CRUD edits this pass.**

## 2026-09-17 continuation — liquidity correction verified; verdict gate not implemented

This continuation modified application code, unlike the planning passes above. Removed the duplicate `technical.avg_daily_volume_usd` check from `synthesis.synthesise`, retaining the `tv_data["avg_daily_volume_usd_calc"]` check and correcting its nullable annotation. Existing orchestrator computation and merge were verified, not newly implemented in this continuation.

Verification:
- `test_synthesis_momentum_regime.py`: 28 passed, including four new mentor-liquidity boundary/missing-data cases. Populating both the model field and calc value produces only one mentor dealbreaker.
- `test_technical_orchestrator_integration.py`: 7 passed, including mocked mean-of-products computation and capture of the merged value reaching synthesis.
- Related synthesis/orchestration/data-quality/narration run before the final merge test was added: 61 passed, 3 skipped.
- No LSP errors in changed Python files. Four existing E701 warnings remain in the thesis-generation section of synthesis.
- Full backend run stopped at `test_insider_cluster.py::TestDetectInsiderCluster::test_cluster_of_three_in_same_week`: `assert cluster is not None` failed after 282 passes. That path was not modified; its baseline was not independently established.
- No pre-fix red-to-green run was performed. Passing current tests is not claimed as that evidence.

Limitations and next work:
- The compute helper retains its existing 50-row minimum even though this metric uses ten rows.
- Follow-up resolved the computed-zero merge gap: the new zero case first failed with `KeyError: 'avg_daily_volume_usd_calc'`. A liquidity-specific `is None` merge now preserves zero without changing the other indicator merges. Final related suite: **63 passed, 3 skipped**; final explicit LSP checks for orchestrator and its integration tests returned no errors. This is a demonstrated red-to-green merge regression, not a retroactive claim about the duplicate-gate removal.
- This $100K critical-illiquidity dealbreaker is NOT the planned $10M workflow liquidity gate.
- Plan section 1C requires `gate: GateResult | None` and evaluation after final conviction mutations. Its prerequisite `backend/app/domain/workflow/gate.py` and trading `evaluate_gate` do not exist. The similarly named validation-pipeline enum is unrelated. No false-PASS stub or alternate scalar contract was added; Wave-1C remains blocked.
- Plan/deep delegations timed out; independent multi-agent review did not complete. Changes were locally inspected and tested only. Nothing committed.

