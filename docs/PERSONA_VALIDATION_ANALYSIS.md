# Beginner Working-Professional Persona Validation

**Date**: 2026-08-28
**Branch**: `feat/swing-parity-upgrade`
**Session log**: [SESSIONS/2026-08-28_beginner-persona-validation.md](SESSIONS/2026-08-28_beginner-persona-validation.md)

## Purpose

Validate whether conflu.ai genuinely serves a **working-professional beginner** who knows nothing about markets. Per ADR-003/yfinance-only constraint, this is a **swing-trading** (couple-days-to-couple-weeks hold) validation — NOT day trading.

The goal is to answer three questions the user asked:

> "Let's see how our system serves, is it helpful to him? what would he want to swing trade and learn about swing trading? Let's analyze that!"

## Persona

- **Name**: Alex
- **Age**: 35
- **Job**: Software engineer, 50 hrs/week
- **Time available**: ~30 min/day
- **Knowledge**: Zero trading knowledge (doesn't know what a candlestick, moving average, or stop loss is)
- **Goal**: Find 1-2 swing setups in ~30 min/day and learn to swing trade profitably over time

## Method

Live Playwright walkthrough (headless Chromium, 1440x1000/1800) against the running local stack:

- Frontend: `http://127.0.0.1:5173` (Vite dev server, bind-mounted `src`)
- API: `http://127.0.0.1:8000` (conflu-api container, bind-mounted repo)

The walkthrough mirrors a realistic beginner journey:

1. **Onboarding / Home** → what does Alex first see?
2. **Morning Brief** → the daily "here's what's happening" digest
3. **Screener** → find tickers (the "find a setup" path)
4. **Ticker Analysis** → read the signal/plan for a candidate
5. **Swing Desk** → the guided workflow (screen → analyze → portfolio)
6. **Learn** → can Alex actually *learn* swing trading here?

Each page was scanned for a curated **jargon list** — institutional terms a complete novice wouldn't understand without an inline explanation — and for **teaching affordances** (info icons, learn tooltips, Explain toggles, plain-English glosses).

## What We Found (Per Page)

### 1. Home / Dashboard

- Regime badge: **NEUTRAL 62/100** (clear, but "NEUTRAL" itself is unexplained to a novice)
- Sector focus: **Financials XLF 85/100**
- Embedding "Guided 62" indicator
- Jargon detected: `swing`, `MA`, `breakout`, `stop`, `VWAP`, `momentum`
- **Assessment**: Numbers are abundant, but context ("what should I *do* with this?") is thin.

### 2. Morning Brief

- Regime + sector focus summarized
- Sector rotation legs (Leading/Lagging, per-sector %)
- Jargon detected: `swing`, `MA`, `breakout`, `conviction`, `target`, `liquidity`, `earnings`
- **Assessment**: A good daily digest *for someone who knows the terms*, but `conviction`, `liquidity`, `MA` appear without inline definition.

### 3. Screener

- "Trend Follower" preset with a **plain-English description**:
  > "Stocks that are steadily going up — they're above their key moving averages with good volume. Use this in strong markets when you want to ride the wave."
- Every filter has a human-readable reason (e.g., "Price > $5 (Quality Gates, 1D)")
- **Results surfaced 2 tickers** in a NEUTRAL regime:
  - **ESTC** (Elastic, Technology Services): $100.73, Scr 65, +25.22%, Entry/SL $100.73/$85.31, Confluence `T26·M14·V10·Q8·F7`, Conviction 7.2M, Inst Q "high", RSI 78, ADX 40
  - **BWT** (Finance): $24.74, Scr 62, -4.62%, Entry/SL $24.74/$22.27, RSI 50, ADX 27
- Column headers: Symbol, Price, Scr, Change, Entry/SL, Confluence, Volume, RS Rtg, Inst Q, Conv, Mkt Cap, P/E, EPS, RSI, ADX, ATR%, Sector, Rtg
- **Assessment**: The uppercase/power columns (`Confluence T26·M14...`, `Conv`, `RS Rtg`, `Inst Q`, `ADX`, `ATR%`) are **cryptic** to a beginner. `T26·M14·V10·Q8·F7` is unreadable without explanation. **Critically, the top result (ESTC) is RSI 78 (overbought) and the second (BWT) is -4.62% (down)** — a beginner cannot judge *"is this actually a good swing entry right now?"* without the system telling him.

### 4. Ticker Analysis (AAPL)

- Full swing trade plan rendered:
  - Verdict: **ACCUMULATE**
  - Entry Zone: **$314.78 – $321.97**
  - Stop Loss: **$304.13**
  - Risk/Reward: **2.5:1**
- Jargon detected: `pullback`, `support`, `breakout`, `confluence`, `conviction`, `liquidity`, `ACCUMULATE`
- **Teaching affordances present and working** (this is the app's strongest teaching surface):
  - `Learn about Scale In`
  - `Learn about Scale Out`
  - `Learn about Trailing Stop`
  - `Learn about Time Stop`
  - `Learn about Risk Limits`
  - an **Explain** toggle, and 3 `info` markers
- The chart-reading fix (D-36) means this plan is now backed by real BOS/CHoCH, MTF confluence, volume profile, etc.
- **Assessment**: The plan is concrete and actionable, and the trade-execution terms are teachable in place. But the *narrative* (why ACCUMULATE? which pullback? is it buying a breakout or a dip?) still assumes the reader understands `pullback`, `breakout`, `confluence`.

### 5. Swing Desk

- 4-step guided workflow: **Screen → Analyze → Portfolio**
- "Ticker Watchlist 0/10 — Add 2-10 tickers to analyze as a portfolio"
- Jargon detected: `conviction`, `MA`
- **Assessment**: Good *process* scaffolding (tells you what to do next), but doesn't yet teach *why* the process exists or what each step means to a novice.

### 6. Learn

- **165 entries** plain-English glossary
- Guided learning paths
- **Assessment**: The best *reference* resource in the app. Good for self-serve lookup. But it is **reactive** — Alex must know to go there and know what to search.

## Helpfulness Verdict

| Question | Verdict | Evidence |
|---|---|---|
| Can a beginner **find** swing setups? | **Partial — yes, with gaps** | Screener surfaces real tickers w/ plain-English filter descriptions, but result columns are cryptic and top results uninterpretable (overbought / down) without guidance |
| Can a beginner **understand** the trade plan? | **Strong on execution, weak on narrative** | Entry/Stop/Target + Learn-tooltips excellent; but *why* ACCUMULATE, and terms like pullback/breakout/confluence, are unexplained in the plan narrative |
| Can a beginner **learn** swing trading? | **Partial — strong reference, weak guided learning** | 165-entry glossary is deep but reactive; no in-flow "first lesson then practice" apprenticeship |
| Can a beginner complete the **workflow**? | **Partial** | Swing Desk gives process steps, but no hand-holding when a step's output is ambiguous (e.g., ESTC overbought) |

**Overall**: The platform is **excellent for an informed trader**, and the D-36 chart-reading fix means the underlying signal is now institutional-grade. But for a **zero-knowledge working professional**, the biggest friction is:

1. **Cryptic screener columns** (Confluence `T26·M14`, Conv, RS Rtg, Inst Q, ADX, ATR%) with no plain-English key.
2. **"No second opinion" on candidates** — a beginner can't tell ESTC (RSI 78) is overbought or BWT (-4.6%) is broken; the screener needs to flag "not a clean setup right now / why".
3. **Trade-plan narrative assumes knowledge** — `pullback`, `breakout`, `confluence` appear without inline gloss the way Scale In/Out do.
4. **Learning is reactive, not guided** — no in-flow teaching or "validate my understanding" for a first-time swing trader.

## What a Beginner Would Want (Prioritized)

These map 1:1 to `ELITE_SWING_TRADING_BLUEPRINT.md` Phase 1 (Daily Mission wizard + Validation Gate + Execution Engine + Apprenticeship Mode). The persona test confirms *why* those blueprint items matter:

1. **Plain-English screen-key / column legend** (teaching layer on Screener + Ticker) — so the *output* isn't a wall of institutional codes. *(Blueprint: Education layer)*
2. **Candidate quality "second opinion"** — every screened ticker gets a plain-English read: *"ESTC is trending but overbought (RSI 78) — not a clean entry. Wait for a pullback."* *(Blueprint: Validation Gate)*
3. **Trade-plan narrative in plain English** — "ACCUMULATE" backed by a sentence a novice reads: *"Price is pulling back toward support in an uptrend — a good place to buy with a stop below that support."* *(Blueprint: Daily Mission wizard explanation step)*
4. **Endpoint-to-endpoint guidance on the workflow** — Swing Desk should tell Alex *"now pick a ticker whose setup you understand; once you pick one, we'll walk you through the plan line by line."* *(Blueprint: Daily Mission wizard)*
5. **First-trade apprenticeship** — a "learn one setup, then paper-trade it" path, because the 165-entry glossary is broad but a beginner needs a *sequence*.

## Recommended Next Step

Per the user's earlier decision ("Let's see #2 first, cause it will have some UI changes/explanation improvements"), and per `ELITE_SWING_TRADING_BLUEPRINT.md`, the findings above **confirm the blueprint's Phase 1 is the right investment**. The persona test turned the blueprint's abstract "Daily Mission wizard / Validation Gate / Execution Engine" into concrete, evidence-backed UI/teaching gaps.

The natural continuation is to plot Phase 1 of the blueprint (Daily Mission wizard + Validation Gate + Execution Engine + Apprenticeship Mode) against these five gaps and implement, in priority order, the highest-leverage teaching improvements first.
