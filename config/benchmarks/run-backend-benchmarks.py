"""Performance benchmark runner for CI gates.

Measures:
- Screen 5000 symbols < 30s (with warm DuckDB cache)
- 10-year backtest < 2s
- Indicator computation throughput
"""
from __future__ import annotations

import time
from pathlib import Path

import duckdb
import pandas as pd


def generate_test_data(n_symbols: int = 5000, n_days: int = 2520) -> pd.DataFrame:
    """Generate synthetic OHLCV data for benchmarking."""
    import numpy as np

    rng = np.random.default_rng(seed=42)
    dates = pd.date_range("2000-01-01", periods=n_days, freq="D", tz="UTC")

    rows = []
    for i in range(n_symbols):
        symbol = f"BENCH{i:04d}"
        base_price = 100.0 + rng.random() * 100
        close = base_price + np.cumsum(rng.normal(0, 0.5, n_days))
        open_ = close + rng.normal(0, 0.2, n_days)

        for d in range(n_days):
            rows.append({
                "symbol": symbol,
                "timestamp": dates[d],
                "open": float(open_[d]),
                "high": float(max(open_[d], close[d]) + abs(rng.normal(0, 0.2))),
                "low": float(min(open_[d], close[d]) - abs(rng.normal(0, 0.2))),
                "close": float(close[d]),
                "volume": float(rng.integers(1000, 10000)),
                "timeframe": "1D",
                "asset_class": "equity",
            })

    return pd.DataFrame(rows)


def benchmark_screen_performance(n_symbols: int = 5000) -> dict:
    """Benchmark screening performance."""
    import numpy as np

    print(f"Generating {n_symbols} symbols x 10 years of daily data...")
    df = generate_test_data(n_symbols)

    # Compute indicators
    print("Computing indicators...")
    import pandas_ta as ta

    start = time.perf_counter()
    closes = df.groupby("symbol")["close"]
    # RSI
    rsi = closes.apply(lambda x: ta.rsi(x, length=14))
    # SMA crossover
    sma_20 = closes.apply(lambda x: ta.sma(x, length=20))
    sma_50 = closes.apply(lambda x: ta.sma(x, length=50))

    elapsed = time.perf_counter() - start
    score = "PASS" if elapsed < 30 else "FAIL"

    print(f"Screen benchmark ({n_symbols} symbols): {elapsed:.2f}s [{score}]")
    return {"benchmark": "screen", "symbols": n_symbols, "elapsed_s": elapsed, "score": score}


def benchmark_backtest_performance() -> dict:
    """Benchmark backtest performance (10yr daily data < 2s)."""
    import numpy as np
    import vectorbt as vbt

    print("Benchmarking backtest performance (10yr daily)...")
    dates = pd.date_range("2014-01-01", "2024-01-01", freq="D", tz="UTC")
    n = len(dates)

    rng = np.random.default_rng(seed=42)
    price = 100.0 + np.cumsum(rng.normal(0, 0.5, n))

    start = time.perf_counter()
    entries = price % 2 < 1  # Simple signal
    exits = price % 2 > 1
    pf = vbt.Portfolio.from_signals(price, entries, exits, init_cash=100000.0)
    metrics = pf.stats()
    elapsed = time.perf_counter() - start

    score = "PASS" if elapsed < 2 else "FAIL"
    print(f"Backtest benchmark (10yr): {elapsed:.2f}s [{score}]")
    return {"benchmark": "backtest", "elapsed_s": elapsed, "score": score}


def main() -> None:
    """Run all benchmarks and report results."""
    results_dir = Path("benchmark-results")
    results_dir.mkdir(exist_ok=True)

    results = []
    results.append(benchmark_screen_performance())
    results.append(benchmark_backtest_performance())

    # Write results
    results_df = pd.DataFrame(results)
    results_df.to_json(results_dir / "benchmark-results.json", orient="records")
    results_df.to_csv(results_dir / "benchmark-results.csv", index=False)

    print("\n=== Benchmark Results ===")
    print(results_df.to_string(index=False))

    all_pass = all(r["score"] == "PASS" for r in results)
    exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
