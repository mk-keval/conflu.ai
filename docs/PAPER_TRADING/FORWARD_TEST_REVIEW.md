# Forward Test — Review Backlog (after ~30 closed paper trades)

**Created:** 2026-10-19
**Decision:** Option 1 — no rule changes now; run the live paper loop forward and decide
with real evidence (user decision after the 2-month replay, D-71).
**Trigger:** 30 closed forward trades **or** 6 weeks (≈ 2026-11-30), whichever first.
**Status:** OPEN — awaiting trigger

## Why this file exists

The 2-month replay (371 trades, 114 W / 257 L, −0.203R, PF 0.63) flagged two structural
concerns the user raised. We do NOT act on a single 2-month simulation; these are
hypotheses to check against forward (real, gated) data at the review.

## A. Exit design caps the winners (reward:risk ceiling)

- Design: ATR stop 2.0 / target 3.0 → best-case win ≈ **+1.5R**. Replay avg win +1.05R,
  avg loss −0.83R; only 67/371 (18%) of trades reached target — most winners exit early
  (15-bar time cap or end-of-window).
- Break-even win rate implied by those numbers: **~40% (design cap, −1R losses) to
  ~44% (observed avg win/loss)**. The replay delivered 30.7% overall, 26.4% in choppy.
- Forward check on the first 30 closed trades: win rate, avg win R, avg loss R, and
  **MFE** (`mfe_r` is already captured by the exit sync):
  - MFE ≫ realized R → exits leave money on the table → consider trailing stop, partial
    scale-out at target, wider target in trend regimes.
  - MFE ≈ realized R → entries are the constraint → raise selectivity instead.

## B. Regime response gap — "choppy" serves continuation screens; "ranging" is unreachable

Verified in code, 2026-10-19 (`morning_brief._REGIME_LABEL_MAP`,
`regime._composite_to_label`, `regime_selector`):

- The detector can only emit labels mapping to **strong_trend / neutral / choppy /
  high_vol**. The **"ranging" menu (statistical-mean-reversion #1, mean-reversion #2)
  can never be selected automatically** — it is configured but dead except for a
  manual `regime_override`.
- "Cautious" (composite 35–50) → key **choppy** → menu = bull-flag-continuation (85),
  trend-pullback-v2 (80), low-vol-setup (65, defensive). All three are
  continuation/breakout setups — deliberate per the P1.1 comment in `morning_brief.py`
  ("a mid-range composite is NOT a reason to serve only defensive screens").
- Replay result on the 21 choppy sessions: **242 trades (65% of all trades), and every
  screen in the menu lost ≈ −0.35R** (low-vol-setup 97 trades −0.357R; bull-flag 88
  −0.346R; trend-pullback 57 −0.226R).
- The only consistently positive screen, statistical-mean-reversion (+0.162R, PF 1.52,
  WR 44.8%, 67 trades), traded **only via the neutral menu's defensive slot** — i.e.
  the system profited from mean reversion almost by accident, never because the regime
  asked for it.
- Review questions (no changes yet):
  1. Should the choppy menu include mean-reversion primaries (fix the playbook/mood
     mismatch)?
  2. Should "ranging" become reachable from the detector (e.g. composite mid-range +
     low ADX / narrow breadth), or should the choppy menu simply be rebuilt?
  3. Should choppy add a **behavior change** (trade fewer signals, smaller size,
     stronger confirmation) instead of merely swapping a long-only menu?

## C. Per-screen forward confirmation

Replay worst → best (expectancy R / trades):

| Screen | Exp R | Trades |
|---|---|---|
| low-vol-setup | −0.357 | 97 |
| bull-flag-continuation | −0.346 | 88 |
| volume-trend-accumulation | −0.253 | 23 |
| trend-pullback-v2 | −0.226 | 57 |
| 52week-breakout | −0.150 | 24 |
| trend-follower-v2 | +0.021 | 9 |
| statistical-mean-reversion | +0.162 | 67 |
| institutional-trend-follower-mtf | +0.183 | 6 |

Forward: build the same table from real journal trades before re-weighting / retiring
any screen.

## D. Gate effectiveness

The replay has no gate (it entered every signal). Forward, measure the rejection rate
and whether rejected candidates would actually have won or lost. If the gate adds no
edge, improve it rather than trusting it.

## Guardrails

- No changes to screens, weights, exits or the gate before the trigger.
- The replay ledger stays simulation-only; the forward journal + VISION.md kill rule
  (expectancy ≤ 0 after 30+ closed trades → stop) remains the decider.
