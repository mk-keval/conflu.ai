# Phase 5: Risk Management Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-19
**Phase:** 5-risk-engine
**Areas discussed:** ATR Position Sizing, Beta Hedging, Correlation Matrix, VaR/CVaR, Kelly Optimization, Risk Dashboard, Configuration

---

## ATR Position Sizing

| Option | Description | Selected |
|--------|-------------|----------|
| Formula: risk% × equity / (ATR × mult) | Standard ATR position sizing | ✓ |
| Fixed fractional | Fixed % of equity per trade | |
| Volatility targeting | Target portfolio volatility | |

**User's choice:** Standard ATR formula with configurable risk% and ATR multiplier
**Notes:** Reuses ATR(14) from Phase 1 indicators. Configurable risk% (default 1-2%) and ATR multiplier (default 2.0).

---

## Beta Hedging

| Option | Description | Selected |
|--------|-------------|----------|
| Rolling 60-day OLS beta | Standard beta calculation | ✓ |
| EWMA beta | Exponentially weighted beta | |
| GARCH beta | Time-varying volatility beta | |

**User's choice:** Rolling 60-day OLS beta vs benchmark
**Notes:** Benchmarks: SPY (equities), BTC (crypto), major indices for forex/commodities. Hedge ratio = beta × position / benchmark. R² tracking.

---

## Correlation Matrix

| Option | Description | Selected |
|--------|-------------|----------|
| 30-day rolling Pearson | Standard rolling correlation | ✓ |
| EWMA correlation | Exponentially weighted | |
| Dynamic conditional correlation | GARCH-DCC | |

**User's choice:** 30-day rolling Pearson correlation
**Notes:** Sector/asset class grouping from Phase 3 screener metadata. Output: N×N matrix + sector aggregated.

---

## VaR / CVaR

| Option | Description | Selected |
|--------|-------------|----------|
| Historical + Parametric + MC | Three methods for robustness | ✓ |
| Historical only | Empirical percentile only | |
| Parametric only | Gaussian assumption | |

**User's choice:** Three methods (Historical, Parametric, Monte Carlo)
**Notes:** Confidence: 95%/99%. Horizons: 1-day, 10-day (√10 scaling). CVaR = Expected Shortfall. Component VaR for portfolio decomposition.

---

## Kelly Optimization

| Option | Description | Selected |
|--------|-------------|----------|
| Full Kelly | f = (p×b - q) / b | |
| Half-Kelly (default) | 0.5 × Kelly for risk aversion | ✓ |
| Fractional Kelly | Configurable fraction | |

**User's choice:** Half-Kelly default, Full Kelly available
**Notes:** Kelly from Phase 4 backtest: f = (p×b - q) / b. Validated against max DD constraint.

---

## Risk Dashboard & API

| Option | Description | Selected |
|--------|-------------|----------|
| REST + WebSocket | Real-time + query endpoints | ✓ |
| REST only | Polling-based | |
| WebSocket only | Push-only | |

**User's choice:** REST + WebSocket
**Notes:** Endpoints: position-size, beta, correlation, var, kelly. WebSocket for real-time risk updates. Report generation: PDF/HTML.

---

## Configuration

| Option | Description | Selected |
|--------|-------------|----------|
| RiskSettings in config.py + config.yaml | Follows Phase 3 ScreenSettings pattern | ✓ |
| Separate risk config file | Separate YAML | |
| Environment variables only | No YAML | |

**User's choice:** RiskSettings in config.py + config.yaml
**Notes:** Follows Phase 3 ScreenSettings pattern. Section: `risk:` in config.yaml.

---

## OpenCode's Discretion

- Exact module structure for risk package
- Statistical library choice: NumPy/SciPy for VaR/beta, pandas for correlation
- Caching strategy for rolling calculations (DuckDB materialized views vs recomputation)

---

## Deferred Ideas

- Stress testing (historical scenarios, Monte Carlo scenarios)
- Factor model risk decomposition (Fama-French, PCA)
- Options-based hedging (delta, gamma, vega)
- Real-time portfolio margin monitoring
- Regime-dependent risk parameters (volatility regimes)