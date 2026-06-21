# ADR-002: vectorbt for Backtesting

**Status:** Accepted
**Date:** 2026-06-18

## Context
Need a backtesting library that supports vectorized operations for speed and portfolio-level simulation.

## Decision
Use vectorbt Portfolio API for all backtesting — signal generation, position sizing, portfolio simulation, and metrics.

## Consequences
- **Positive**: Fully vectorized, portfolio-level simulation, extensive metrics
- **Negative**: Large dependency, learning curve for advanced features
- **Mitigation**: Abstract vectorbt behind engine interfaces for testability
