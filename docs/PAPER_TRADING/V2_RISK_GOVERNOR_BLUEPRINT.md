# V2 Blueprint — The Risk Governor ("four dials")

**Status:** DESIGN PROPOSAL — **not implemented**. Input for the review after ~30 closed
forward trades (see `FORWARD_TEST_REVIEW.md`). Nothing here changes the live system.
**Created:** 2026-10-19 (after the D-71 replay + user Q&A)

## Why this exists

Today the regime only rotates the screen menu (three setups). It does **not** control:

- whether we trade at all (there is no "sit out" state),
- how much we risk (same ~1% every trade in every regime),
- how we exit (static stop/T1/T2 + time stop in every regime),
- and even the menu is half-wired: "Cautious"/choppy serves continuation breakouts
  while the mean-reversion "ranging" menu can never be selected by the detector.

The replay showed why that matters: on choppy days (21 of 42 sessions, 242 of 371
trades) every deployed continuation screen lost ≈ −0.35R. The follow-up what-ifs
(2026-10-19) refined the picture: statistical-mean-reversion is positive on neutral
days but ≈ −0.30R on choppy days, while `mean-reversion` is the only chop screen that
is ≈ flat. Screen edges are regime-specific.

**V2 = one policy object derived from the regime, controlling four dials.**
Live and replay must both consume the *same* policy object so simulation and live
behavior never drift apart again.

## Evidence snapshot (2026-10-19, in-sample)

What-if runs on the same 2-month window (`run_replay_experiments.py`):

- baseline: 371 trades, gross −0.203R, net −$99.8k, 30.7% net win rate (needs 44.6%).
- choppy → full ranging menu: −0.123R gross but −$100k net (67% more choppy trades).
- choppy → mean-reversion only: −0.015R gross, −$26.4k net, 39.8% net win rate — the
  best in-sample result, still below the ≈44% break-even.
- wider target (4.5 ATR): net avg win +1.21R; neutral net +0.031R — helps trend/neutral,
  does nothing in chop.
- halving chop risk: −$99.8k → −$52.9k (damage control; R unchanged).

Read: menu routing and wider targets each help, but **none creates a positive edge in
chop**; permission/selectivity (trade less, trade only the screen that works) is the
largest missing lever, followed by dynamic exits in trend/neutral.

## Dial 1 — Permission: should we trade today?

| Regime | Permission (proposal) |
|---|---|
| strong_trend | normal — all new signals allowed |
| neutral | normal |
| choppy | **reduced** — mean-reversion setups only; skip breakout/continuation signals |
| ranging | normal/reduced — mean-reversion playbook (see Dial 2) |
| high_vol | **minimal/no new entries** — capital preservation; exits still managed |

Also a daily budget: max new entries per day (e.g. 5 normal / 2 choppy / 0 high_vol)
instead of the replay's unconstrained 28/day.

## Dial 2 — Playbook: what do we buy?

- **choppy / ranging → mean reversion primaries.** The config already defines this
  menu (`statistical-mean-reversion` #1, `mean-reversion` #2, `low-vol-setup` #3);
  the fix is routing, not new screens.
- **strong_trend / neutral → momentum/breakout primaries** (current menus).
- Decide the fate of the unreachable "ranging" key: either (a) make it reachable from
  the detector (e.g. composite mid-range + low ADX / narrow breadth), or (b) fold its
  menu into choppy and delete the dead key. Option (b) is simpler; option (a) keeps
  the vocabulary but needs a reliable classifier for it.
- Keep the parity guard: one `config/regime_screens.yaml`, one selector, shared by
  live and replay (already parity-tested — extend the test to the V2 policy).

## Dial 3 — Size: how much risk per trade?

Proposal (starting points, to be tuned only with forward evidence):

| Regime | Risk per trade |
|---|---|
| strong_trend | 1.0% |
| neutral | 1.0% |
| choppy | 0.5% |
| high_vol | 0 – 0.25% |

Honesty note from the what-if runs: halving choppy risk **reduces damage but does not
create edge** — with a negative choppy expectancy it only loses slower. Sizing is
damage control; Dials 1–2 fix the edge, Dial 3 protects the account.

Add a portfolio cap: max concurrent open positions and max total open risk (the
replay assumed *every* signal is takeable — 28 entries on the busiest day).

## Dial 4 — Exit style: how do we get out?

Current: static stop + T1/T2 + time stop; there is **no trailing** in any execution
path (the analysis layer builds a trail plan that nothing consumes — review item A).

Options to evaluate at the review, using the forward journal's `mfe_r`/`mae_r`:

1. **Wire the existing trail plan** (trail after +1R). Biggest structural fix to the
   ~1.5R winner ceiling.
2. **Scale out**: partial profit at T1, runner managed by trail.
3. **Regime-dependent exits**: wider targets in strong_trend, tighter/faster in
   choppy and high_vol.
4. Keep static exits but change the ATR multiple (what-if variant measured how much
   this alone moves the window).

Rule: **one change at a time**, measured against the forward baseline.

## Where it lives (implementation sketch, for later)

```
regime (as-of today)
  → policy = RiskPolicy(
        can_trade: bool,
        allowed_screens: [...],       # Dial 2 — reuses regime_screens.yaml
        max_new_per_day: int,         # Dial 1
        risk_pct_mult: float,         # Dial 3
        exit_style: "static" | "trail" | "scaled" | "regime",  # Dial 4
    )
  → live:   Daily Routine gate/sizing/brief consume `policy`
  → replay: run_replay(..., policy=policy) — same object, so sim stays honest
```

The morning brief shows the regime **and what the policy decided** ("today: choppy —
mean-reversion only, half size, trailing exits"), so the user never has to interpret
the regime manually.

## Pre-registered success criteria (V2)

- Forward expectancy **> 0** over ≥ 30 closed trades after the change, with choppy
  expectancy not worse than −0.1R — vs the current baseline.
- No single change without a measured baseline before/after.
- VISION.md kill rule stays in force (expectancy ≤ 0 after 30+ closed trades → stop).

## What we will NOT do

- No changes before the review trigger (30 closed trades or ≈ 2026-11-30).
- No tuning on a single 2-month window; the what-if runs only size hypotheses.
- Replay numbers never count as evidence.
