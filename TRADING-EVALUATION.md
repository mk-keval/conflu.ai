# Institutional Trading Veteran Evaluation: conflu.ai Screener

**Evaluator:** 30+ year veteran (NYSE floor, Goldman Sachs stat arb desk, multi-strat hedge fund risk management)
**Date:** June 30, 2026
**App Version:** Current branch `feat/screener-table-redesign-and-fixes`
**Methodology:** Full codebase audit (backend + frontend) + live browser interaction via Playwright across all 7 templates

---

## 1. EXECUTIVE SUMMARY

**Would I use this? No. Not even close. But it could get there.**

This is a promising first draft from a developer who understands the *mechanics* of screening but has never managed institutional money. The architecture is clean — well-structured Python/FastAPI backend with clear separation between TV data fetching, confluence scoring, and the React frontend. The YAML-driven template system is smart. The app actually connects to TradingView's live screener API and returns real data (confirmed across all 7 templates, with 580+ matches in ~1.1s for Breakout, 71 for Mean Reversion).

But the scoring is fundamentally naive, the strategies are all long-biased, there's no portfolio context, no regime detection, and the risk model would get a retail trader stopped out, let alone a professional. The deep analysis endpoint returned all zeros for the ticker I checked — that's a critical bug.

Here's what I'd say to the developer: "You've built the chassis. Now you need an engine, transmission, and a driver who's been on the track."

---

## 2. SIGNAL QUALITY ASSESSMENT

### 2.1 Trend Confluence (0-30 pts) — GRADE: C+

**Current logic:**
- `close > EMA200` (+10) ← Weak. A stock can be above its 200-day MA but crashing. MAMA was at $17.80, -43% on the day, and still scored T30 across all templates. That's a problem.
- `close > EMA50` (+10) ← Better, but still binary. A stock barely above its 50-day gets the same score as one 20% above.
- `EMA20 > EMA50` (+10) ← This is the most useful of the three, but +10 for a "golden cross" is too generous. In a strongly trending market, 80% of stocks will satisfy this.

**The problem:** These are binary gates, not graded scores. In my 30 years, trend quality is about *steepness and duration*. A stock that crossed its EMA200 yesterday is NOT in the same trend regime as one that's been above it for 6 months with rising ADX.

**What's missing:**
- **Trend duration** — How many bars has price been above the key MA? A stock that's held above its 200-day for 100+ bars should get MORE points than one that just crossed.
- **Slope of the EMA** — EMA50 slope > 0 is a much better trend indicator than price > EMA50. You can calculate this from EMA50-EMA50[1].
- **Trend pullback context** — A stock that's broken above EMA50, pulled back to test it, and held, is a HIGHER quality setup than one that just pushed through.
- **ADX direction** — ADX > 25 is already in the Quality bucket, but ADX *rising* matters more than ADX > 25. You'd cut your teeth on Welles Wilder's insight: ADX rising = trend gaining strength.

**Recommendation:**
1. Replace binary price > EMA checks with a **graded trend score**: 0-5 pts per MA based on how many standard deviations price is above/below it
2. Add EMA slope (direction + steepness): 0-5 pts
3. Add trend duration (bars since first cross): 0-5 pts
4. Move ADX rising/falling from Quality to Trend
5. New proposed max: 30 pts but with 8+ sub-signals instead of 3

### 2.2 Momentum Confluence (0-25 pts) — GRADE: D+

**Current logic:**
- `MACD.macd > MACD.signal` (+10) ← Standard macd bullish cross
- `MACD.hist > 0` (+5) ← Redundant with the above in most cases
- `50 < RSI < 70` (+10) ← This is THE biggest problem

**The RSI problem:**
The code uses `if 50 < rsi < 70: mom_score += 10`. This means:
- A stock with RSI 69 gets +10
- A stock with RSI 71 gets +0
- A stock with RSI 51 gets +10

This is WRONG. In professional trading:
- RSI 50-60: Neutral bullish (warrants ~3-4 pts)
- RSI 60-70: Strong bullish momentum (warrants ~7-8 pts) 
- RSI 70-80: Overbought but continuation possible (warrants ~3-4 pts, not zero!)
- RSI > 80: Extended, high risk of mean reversion (warrants ~0-2 pts, caution flag)

You're creating a discontinuity at 70 that will make your system dump stocks that are breaking out hard. In the Momentum Breakout template, a stock that runs from RSI 68 to RSI 72 would *lose* 10 momentum points. That's absurd.

**The MACD redundancy:**
`MACD.hist > 0` is almost always true when `MACD.macd > MACD.signal`. The histogram is just the visual representation of the difference. You're double-counting the same signal.

**Recommendation:**
1. Replace binary RSI with a **graded RSI scale**:
   - RSI 55-65: +3
   - RSI 65-75: +6
   - RSI 50-55 or 75-80: +2
   - RSI < 50 or > 80: +0
2. Replace MACD.hist > 0 with `MACD.histogram ACCELERATING` (hist > hist[1]): +5
3. Drop the redundant MACD histogram check or use it differently (histogram rising vs just positive)

### 2.3 Volume Confluence (0-20 pts) — GRADE: C

**Current logic:**
- `relative_volume_10d_calc > 1.5` (+10)
- `volume_change > 0` (+5)
- `close > VWAP` (+5)

**Issues:**
- Relative volume > 1.5 is a reasonable threshold, but graded would be better (1.0-1.5: +3, 1.5-2.5: +6, 2.5-5.0: +9, > 5.0: +10)
- `volume_change > 0` is meaningless by itself — volume up 0.1% gets the same as volume up 500%
- Close > VWAP is actually a good short-term signal, but VWAP is most meaningful intraday. On daily charts, VWAP loses significance.

**Missing signals:**
- **Volume/MA cross** — Volume > volume_ma20 is a much better signal than "volume > yesterday"
- **Accumulation/distribution** — The MFI (Money Flow Index) or Chaikin MF would tell you if volume is buying or selling pressure
- **Volume on up days vs down days** — A stock that rallies on 2x volume but declines on 0.5x volume is being accumulated

### 2.4 Volatility/Quality (0-15 pts) — GRADE: D

**Current logic:**
- `ADX > 25` (+8)
- BB squeeze (width < 5% of price) (+7)

**Issues:**
- ADX > 25 is fine but it's already being checked in many templates as a filter. Double-counting the same signal through both filtering AND scoring is amateurish.
- The BB squeeze detection uses `BB.upper > BB.lower` with a computed width. But the TV columns have `.below_pct()` which compares differently. The actual code uses `if bb_pct < 5: qual_score += 7` — a 5% Bollinger Band width is HUGE, not a squeeze. A squeeze would be < 2-3% for most stocks.

**Missing:**
- **ATR percentile** — Where is ATR in its 20-period range? Low ATR = contraction, high ATR = expansion. This is what professional volatility traders actually use.
- **Historical volatility percentile** — Not just current vol but how it compares to the last 3 months
- **Correlation check** — Is this stock moving with the market or independently? Independent movers are more interesting for mean reversion
- **Liquidity check** — Average dollar volume is what matters for institutional execution, not just share volume

### 2.5 Fundamental Backdrop (0-10 pts) — GRADE: F

**Current logic:**
- Analyst rating is "StrongBuy" or "Buy" (+5)
- Market cap > $10B (+3)
- EPS > 0 (+2)

**Issues:**
- Analyst ratings are backward-looking and consensus-driven. By the time analysts agree on "Strong Buy," the move is often over.
- Market cap > $10B is a large-cap bias. Small-cap alpha is where systematic screens historically outperform.
- EPS > 0 in 2026? Many of the best-performing stocks have negative EPS (growth companies reinvesting).

**What a professional would use:**
- **Revenue growth (YoY)** — Actual top-line growth is more predictive than EPS
- **Revenue surprise** — Did they beat estimates? (+3 pts)
- **Short interest ratio** — Days to cover > 5 can signal short squeeze potential (+3 pts)
- **Insider buying** — Executives buying on the open market (+4 pts, this is a HIGH signal quality indicator)
- **Sector relative strength** — Is the stock's sector outperforming? (+2 pts)

---

## 3. MULTI-TIMEFRAME ANALYSIS

### 3.1 Current Approach: Intersection Model

The MTF approach runs separate TV queries per timeframe, then intersects the ticker sets. This is a **valid approach** but has significant limitations:

**What works:**
- It guarantees every matched ticker signals on ALL timeframes
- The separation into configurable per-TF filters is architecturally clean
- The YAML-driven config for MTF is well-designed

**What doesn't work:**
- **Throws away too many good setups.** A stock that shows a breakout on the 4H chart but is still basing on the daily is actually a VERY common pattern. A strict intersection would miss this.
- **Different timeframes have different columns.** The MTF scorer uses `combined_df` which merges rows from all TFs — but which timeframe's RSI gets used for scoring? It's ambiguous.
- **No hierarchical preference.** A weekly signal should be weighted MORE than a daily signal, not equal.
- **Inefficient for the API.** Running 3 separate TV queries that each return 500 tickers and then intersecting to get ~20 is wasteful.

### 3.2 What a Real Quant Desk Would Do

**Primary/Confirmation model:**
- Primary timeframe: Daily (1D) — the "decision" timeframe
- Confirmation timeframe(s): Weekly and/or 4H
- Scoring: The primary TF gets 60% weight, confirmations get 40%

**Confluence stacking (NOT strict intersection):**
Instead of requiring a ticker to appear in all TF results:
1. Run the daily screen → get 200 candidates
2. For each candidate, check weekly and 4H signals
3. Score: 60% daily confluence + 25% weekly + 15% 4H

**TF-specific factor design:**
- Weekly: Trend regime (EMA alignment, ADX), long-term momentum
- Daily: Entry triggers (MACD cross, RSI, volume surge)
- 4H/1H: Timing filters (VWAP deviation, intraday momentum)

### 3.3 Which Timeframes Matter by Strategy

| Strategy | Primary | Confirmation | Timing |
|----------|---------|-------------|--------|
| Trend Follower | 1W / 1D | 1D / 4H | 4H / 1H |
| Momentum Breakout | 1D | 4H | 1H |
| Mean Reversion | 1D | 1W (trend context) | 1H (entry timing) |
| Swing | 4H | 1D | - |
| Position | 1W | 1D | - |
| Intraday | 1H | 4H (trend bias) | 15m (entry) |

The current "all timeframes weighed equally" approach doesn't reflect any of this nuance.

---

## 4. MISSING SCREENERS & STRATEGIES

A hedge fund desk would run at minimum 15-20 screens. You have 7, all bullish. Here's what's missing:

### HIGH PRIORITY

**SHORT Ideas (Vital — current system is all long-biased)**
- **Trend Breakdown:** Price below EMA20/50/200 with rising volume
- **Death Cross Momentum:** EMA50 < EMA200, MACD bearish cross, RSI falling through 50
- **Short Squeeze Candidates:** >20% short float, >5 days to cover, RSI oversold (for covering, not buying)
- **Distribution Days:** Price declining on accelerating volume, close in lower half of range

**Institutional Accumulation/Distribution**
- **Accumulation Screen:** Price up 3-5% on >2x volume, tight range (high-low < 2% of close), relative strength > 0
- **Distribution Screen:** Price down on massive volume, wide range, close at lows
- **Institutional Footprint:** Large block trades detected through volume profile anomalies

**Regime-Aware Strategies**
- **High-Vol Breakout:** ATR > 75th percentile + price breakout above resistance
- **Low-Vol Mean Reversion:** ATR < 25th percentile + RSI oversold (this is the SIGNAL most prop desks run)
- **Trending Range:** Price in a range (20-period) but ADX rising = breakout imminent

### MEDIUM PRIORITY

**Special Situations**
- **Gap Fill:** Price gapped up/down >3%, now retracing to fill the gap
- **VWAP Deviation:** Price > 3 standard deviations from VWAP on >2x volume (mean reversion setup)
- **52-Week Breakout:** Price breaking 52-week high on >50% volume surge
- **Sector Rotation:** Top 5 sectors by relative strength last 20 days → screen for best setups within those sectors

**Risk-Off Strategies**
- **Safe Haven Flow:** Low vol, high dividend, positive correlation to bonds (during risk-off regimes)
- **Put/Cet Ratio Spikes:** Not directly available from TV screener but could be proxied through volatility screens

---

## 5. RISK & POSITION SIZING

### 5.1 ATR-Based Exit Critique

**Current:** Stop at 2 ATR below entry, targets at 2 ATR and 3 ATR. Fixed 1:2 risk-reward.

**The problem:** This treats all ATRs as equal. A $10 stock with ATR of $0.50 and a $500 stock with ATR of $12.50 are treated identically in R:R terms. But:
- **Liquidity risk:** A 2 ATR stop on a low-liquidity stock might get blown through on a single print
- **Volatility regime:** In high-vol markets (VIX > 30), 2 ATR stops trigger too frequently. In low-vol (VIX < 15), 3 ATR targets may never be hit.
- **No time stop:** Professional traders also use time stops ("if this setup hasn't worked in 5 days, I'm out"). No time stop = bag holding.

**What to fix:**
1. **Dynamic ATR multiplier based on volatility regime:**
   - Low vol (ATR% < 2%): 2.5 ATR stop
   - Normal vol (ATR% 2-5%): 2.0 ATR stop
   - High vol (ATR% > 5%): 1.5 ATR stop (tighter because price moves further)
2. **Add a time stop** — If position isn't up > 0.5 ATR within 5 bars, close at market
3. **Trailing stop option** — Once Target 1 is hit, tighten to 1 ATR trailing

### 5.2 Probability-Weighted Targets

The current system shows 2 targets at fixed R:R levels but doesn't answer the question: **What's the probability of hitting each target?**

Every professional position sizing model uses:
- **Expected Value:** `(Win% × AvgWin) - (Loss% × AvgLoss)`
- **Optimal f / Kelly Criterion:** To determine position size based on edge
- **Scenario analysis:** What if I'm right but it takes 3 months? What if I'm wrong by 3 ATR?

**Recommendation:**
For each ticker, show:
- **Historical win rate** for this pattern (pulled from backtest data)
- **Expected value** of the trade in R:R terms
- **Kelly-optimal position size** (as % of portfolio)
- **Maximum adverse excursion** — How far does this pattern typically go against you before working?

### 5.3 The Critical Missing Piece: Portfolio Context

This app has **zero** portfolio context. Every signal is treated as an independent opportunity. In reality:
- **Concentration limits** — Max 5% in any single position, max 20% in any sector
- **Correlation drag** — If you take 5 signals that are all in Tech, your effective diversification is ~1.5 positions, not 5
- **Regime overlap** — If you're running both Trend Follower AND Mean Reversion simultaneously, half your signals are cancelling each other out
- **Margin awareness** — Long/short ratios, gross/net exposure, VaR limits

### 5.4 Liquidation Mechanics — Missing Entirely

The app shows stop losses but doesn't address:
- **Slippage on stops** — In fast markets, your 2 ATR stop might fill at 3 ATR or worse
- **Gap risk** — Gapping through your stop level on overnight news
- **Circuit breaker logic** — What happens when market-wide circuit breakers trigger?
- **Loss cascade protection** — If one position hits its stop, does it reduce risk on correlated positions?

---

## 6. UI/UX FEEDBACK (From a Trader's Perspective)

### What's Good

- **Dark theme** — Correct. Every pro terminal is dark.
- **Column layout** — Symbol, Price, Score, Change, Entry/SL, Confluence, Volume, Rating — this is a reasonable set of columns
- **Sortable columns** — Essential, works well
- **Pagination with multiple sizes** — 10/25/50/100 is standard
- **Confluence breakdown** (T30·M25·V20) — This is actually well-presented. Compact, informative.
- **Score badges with color coding** — Correct use of green/amber/red
- **Export buttons (CSV/JSON)** — Pro requirement ✓
- **Row hover highlighting** — Standard, works

### What's Missing (Critical for Professional Use)

**1. Data density is too low**
- The virtualized table only shows ~20 visible rows at a time. A pro Bloomberg/Reuters terminal would show 40-50
- No condensed view option
- The row height (40px) is reasonable but the spacing could be tighter

**2. Missing columns that every trading desk needs**
- **Market cap** — Without this, you can't size positions appropriately
- **Average true range (ATR)** — Absolute AND as % of price
- **Relative volume (shown inline but too subtle)**
- **Sector/Industry** — You're looking at ETFs and closed-end funds mixed with stocks. How do I filter to just equities?
- **52-week high/low %** — Where is this setup in the broader context?
- **Short interest / days to cover** — Critical for momentum setups
- **Institutional ownership %** — Or at least the trend in institutional position count

**3. Layout issues**
- The Entry/SL column `9.57 / 9.34` is cramped. These should be stacked or in separate columns
- The "Confluence" column shows T30·M25·V20 without Q (quality) or F (fundamental). Why hide two of the five factors?
- No way to customize which columns are displayed (column picker)
- No color coding on the change column — it's just green/red text, no background
- Search box exists but doesn't work for filtering results? ("Search symbols... (/)")

**4. Screen management**
- The template dropdown at top is fine, but there's no way to see what filters are ACTUALLY being run
- No "edit template" or "visual filter builder" in the UI
- No way to save a custom screen
- No way to compare two screens side by side

**5. Detail panel issues**
- The slide-out panel is clean but slow (200ms animation for data that should be instant)
- The breakdown shows "Volatility" and "Pattern" with 0 scores — these aren't even used in the scoring model. Why show them?
- Deep Analysis returned all zeros for BDJ — this button is broken
- Backtest data is requested but shows "N/A" — again, broken or empty

---

## 7. TOP 3 CRITICAL FLAWS

### #1: The Scoring Model Is Too Binary (CRITICAL)

The confluence scorer awards points in binary chunks (either +10 or +0, either +5 or +0). This means:
- **No granularity** — A stock barely above EMA200 gets the same 10 points as one 30% above it
- **Cliff effects** — RSI at 69 gets +10 pts, RSI at 71 gets +0 pts. This will cause false signals and missed opportunities
- **Multiple stocks cluster at 85-92** — Looking at the Breakout results, every top-ranked stock shows T30·M25·V20 (total 85-92). That's almost no differentiation at the top
- **False precision** — A score of 92 vs 85 sounds meaningful but the underlying model treats them almost identically (all maxima)

**Fix:** Convert every binary check to a graded continuous or multi-tier score. The difference between a "perfect" stock and a "pretty good" one should be meaningful.

### #2: No Regime Detection or Market Context (CRITICAL)

The app runs the same screens regardless of market conditions. A trend follower in a range-bound market will get obliterated. A mean reversion strategy in a trending market will get run over.

**A professional system needs:**
- **Market regime detection** — Trending (ADX > 25), ranging (ADX < 20), volatile (VIX > 30), calm (VIX < 15)
- **Factor adjustment** — In high-vol regimes, tighten stops and reduce position sizes. In low-vol, widen them
- **Strategy selection** — Only run Mean Reversion when market is ranging. Only run Trend Follower when market is trending
- **Correlation regime** — When all assets are correlated (2020 style), diversification disappears

### #3: All Strategies Are Long-Only (CRITICAL)

In 30 years, I've never seen a successful fund that doesn't have both long and short ideas. Even a long-biased fund needs:
- **Short hedges** — To reduce net exposure when the market turns
- **Pairs trades** — Long the winner, short the loser in the same sector
- **Market neutral** — Long/short within sectors to extract alpha without beta risk
- **Opportunistic shorts** — Broken IPOs, frauds, secular declines

A screener that only finds long ideas is giving you one side of the market. When the tape turns, this tool becomes worthless.

---

## 8. TOP 3 MOST PROMISING FEATURES

### #1: The Confluence Scoring Framework (PROMISING)

The idea of combining Trend + Momentum + Volume + Quality + Fundamental into a single score is the RIGHT approach. It's what a systematic fund does. The current implementation is naive but the **architecture** is correct:
- Weighted factors with configurable max scores
- Clean separation between data collection and scoring
- Rating system (A+ through D) mirrors professional grading

**Potential:** With proper calibration, this framework could rival what mid-tier quant funds use.

### #2: Multi-Timeframe Architecture (PROMISING)

The MTF template system — separate filters per timeframe, then combine results — is architecturally solid. The intersection model is too strict, but the underlying infrastructure (per-TF configs, per-TF queries, then merging) is exactly how a professional system would be built.

**Potential:** One refactor from strict intersection to weighted confluence stacking and this becomes genuinely useful.

### #3: YAML-Driven Template System (PROMISING)

Holy grail of systematic trading: **strategy as configuration, not code.** The YAML templates allow new strategies to be added without touching a line of Python/TypeScript. This is how a prop firm quant team operates — config-driven strategy management.

**Potential:** With a visual template editor (currently only the `TemplateEditor.tsx` exists but isn't in the main flow), this could let traders design their own screens without developer involvement.

---

## 9. SPECIFIC RECOMMENDATIONS

Ordered by priority (P0 = ship-blocking, P1 = major quality, P2 = nice to have):

### P0 — Fix Now

- **[Fix] Deep analysis endpoint** — The `/analyze` endpoint returned all zeros for BDJ. Confirm which tickers it works for or fix the data pipeline. This breaks the detail panel's core value proposition.
- **[Fix] RSI scoring discontinuity** — Change `50 < RSI < 70` to a graded scale. This is causing active harm by punishing momentum stocks.
- **[Fix] Remove redundant quality/volatility checks** — Stop double-counting ADX as both a filter AND a score component. Choose one.

### P1 — High Impact

- **[Scoring] Convert binary checks to graded scores** — Every `if condition: score += N` should become `score += int(condition * N)` or a multi-tier switch. This will immediately improve signal differentiation.
- **[Strategies] Add SHORT screens** — At minimum: Breakdown (inverse of Trend Follower), Short Squeeze, Distribution. The current all-long bias is professionally unusable.
- **[Risk] Add volatility regime to stop calculation** — ATR multiplier should vary with market vol regime. Add VIX regime detection.
- **[MTF] Change intersection to weighted stacking** — Primary tf gets 60% weight, confirmations 40%. Current intersection is too strict.
- **[UI] Show all 5 confluence factors** — T, M, V, Q, F should all be visible, not just T, M, V.
- **[UI] Fix column density** — Add option for compact view with more visible rows, add market cap and ATR% columns.

### P2 — Important

- **[Strategies] Add 5 more templates**: Accumulation/Distribution, Short Squeeze, 52-Week Breakout, Sector Rotation, Range Breakout
- **[Scoring] Introduce regime-dependent weights** — Trend should weigh more in trending markets, volume in news-driven markets, quality in uncertain markets
- **[Risk] Add Kelly-optimal position sizing** — Use the confluence score + historical backtest win rate to suggest position sizes
- **[Risk] Add correlation awareness** — Group signals by sector, flag overconcentration
- **[UI] Add column picker** — Let traders select which columns to display
- **[UI] Add visual filter builder** — Let traders create/modify templates visually
- **[UI] Add time stop indicator** — How many bars since the setup triggered
- **[Data] Add sector/industry classification to results** — Essential for grouping and risk management

### P3 — Future

- **[Regime] Market regime detection** — Ranging/trending/high-vol/low-vol regime overlay
- **[Strategies] Options flow screen** — Unusual options activity (not possible via TV but worth integrating)
- **[AI/ML] Pattern recognition overlay** — After collecting enough data, add ML-based pattern matching
- **[Execution] OMS integration** — Connect to brokers for one-click execution from screen
- **[Analytics] Portfolio-level risk dashboard** — VaR, beta, correlation matrix of selected signals
- **[Backtesting] Proper historical walk-forward** — Not just single-run backtests but rolling out-of-sample validation

---

## Technical Notes from Browser Testing

| Test | Status | Detail |
|------|--------|--------|
| Navigate to app | ✅ | http://localhost:5173 loads correctly |
| Breakout template | ✅ | 580 matches, 1141ms |
| Momentum Breakout | ✅ | 95 matches, 221ms |
| Trend Follower (MTF) | ✅ | 311 matches, 321ms (intersection of 3 TFs) |
| Mean Reversion | ✅ | 71 matches, 362ms (shows C-rated, M0 correctly) |
| Detail Panel | ✅ | Opens with slide animation, shows breakdown/targets |
| Deep Analysis | ❌ | Returns all zeros for BDJ ticker |
| CSV/JSON Export | ⏹ | Buttons present, not tested |
| Pagination | ✅ | Working correctly, 25/page default |
| Sorting | ✅ | All columns sortable, multi-click cycles asc/desc |
| Column reordering | ❌ | Not implemented |
| Visual template editor | ❌ | TemplateEditor exists but not in main UI flow |

---

*This evaluation was produced by a 30-year institutional trading veteran. The bluntness is professional respect — the code architecture is solid, but the financial model needs fundamental rework to be useful in a professional context.*
