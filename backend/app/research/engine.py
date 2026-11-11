"""Portfolio backtesting engine for research."""

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd


@dataclass
class ExitRules:
    stop_atr: float = 2.0
    target_atr: float = 3.0
    max_hold_bars: int = 15


@dataclass
class PortfolioRules:
    start_equity: float = 100_000.0
    risk_pct: float = 0.5  # percent of equity risked per trade
    max_positions: int = 8
    max_position_pct: float = 20.0  # max percent of equity in one position
    cost_bps_per_side: float = 15.0  # basis points per side


@dataclass
class Trade:
    symbol: str
    signal_date: pd.Timestamp
    entry_date: pd.Timestamp
    entry_price: float
    stop: float
    target: float
    shares: int
    exit_date: pd.Timestamp
    exit_price: float
    exit_reason: str
    bars_held: int
    r_gross: float
    r_net: float
    pnl_usd: float
    censored: bool


def _candidates_by_date(
    data: dict[str, pd.DataFrame],
    signals: dict[str, pd.Series],
) -> dict[pd.Timestamp, list[str]]:
    """Map each date to the symbols whose signal fired on their previous bar.

    Precomputed once. The original implementation rebuilt, for every date and
    every symbol, the full list of earlier bars, which made 150+ control runs
    per setup impractical. Order is the iteration order of ``signals`` and then
    ascending bar index, which keeps the per-date shuffle deterministic.
    """
    by_date: dict[pd.Timestamp, list[str]] = {}
    for symbol, signal_series in signals.items():
        if symbol in ("SPY", "VIX") or symbol not in data:
            continue
        df = data[symbol]
        if len(df) < 2:
            continue
        aligned = (
            signal_series.reindex(df.index, fill_value=False)
            .fillna(False)
            .to_numpy(dtype=bool)
        )
        fired = np.flatnonzero(aligned[:-1]) + 1
        if fired.size == 0:
            continue
        dates = df.index
        for i in fired:
            by_date.setdefault(dates[i], []).append(symbol)
    return by_date


def run_portfolio(
    data: dict[str, pd.DataFrame],
    signals: dict[str, pd.Series],
    exit_rules: ExitRules,
    rules: PortfolioRules,
    seed: int = 42
) -> tuple[list[Trade], pd.Series]:
    """Run portfolio backtest with given signals.

    Args:
        data: Dict of symbol -> DataFrame with OHLCV and indicators.
        signals: Dict of symbol -> boolean Series (True = signal at that day's CLOSE).
        exit_rules: Exit parameters.
        rules: Portfolio parameters.
        seed: Random seed for candidate shuffling.

    Returns:
        Tuple of (list of Trade objects, equity Series indexed by date).

    Every opened position is closed before the function returns, so
    ``equity.iloc[-1] == rules.start_equity + sum(t.pnl_usd for t in trades)``.
    Positions that outlive their symbol's data are closed at that symbol's last
    close with ``exit_reason="data_end"`` and ``censored=True``.
    """
    # Get all dates from all symbols (excluding SPY, VIX)
    all_dates = set()
    for sym, df in data.items():
        if sym not in ("SPY", "VIX"):
            all_dates.update(df.index)
    all_dates = sorted(all_dates)

    # Convert to Series for easier lookup
    date_to_ordinal = {d: i for i, d in enumerate(all_dates)}
    candidates_by_date = _candidates_by_date(data, signals)

    # Initialize state
    cash = rules.start_equity
    positions = {}  # symbol -> entry metadata
    trades = []
    equity_curve = []

    def mark_price(symbol: str, date: pd.Timestamp) -> float | None:
        """Last available close on or before ``date``."""
        idx = data[symbol].index
        i = idx.searchsorted(date, side="right") - 1
        if i < 0:
            return None
        return float(data[symbol]["close"].iloc[i])

    def close_position(
        symbol: str,
        pos: dict,
        exit_price: float,
        exit_reason: str,
        exit_date: pd.Timestamp,
        bars_held: int,
        censored: bool,
    ) -> None:
        nonlocal cash
        entry_price = pos["entry_price"]
        shares = pos["shares"]
        risk_per_share = entry_price - pos["stop"]
        cost = rules.cost_bps_per_side / 10000

        r_gross = (exit_price - entry_price) / risk_per_share if risk_per_share > 0 else 0
        r_net = ((exit_price * (1 - cost)) - (entry_price * (1 + cost))) / risk_per_share if risk_per_share > 0 else 0
        pnl_usd = shares * (exit_price - entry_price) - shares * (entry_price + exit_price) * cost

        trades.append(Trade(
            symbol=symbol,
            signal_date=pos["signal_date"],
            entry_date=pos["entry_date"],
            entry_price=entry_price,
            stop=pos["stop"],
            target=pos["target"],
            shares=shares,
            exit_date=exit_date,
            exit_price=exit_price,
            exit_reason=exit_reason,
            bars_held=bars_held,
            r_gross=r_gross,
            r_net=r_net,
            pnl_usd=pnl_usd,
            censored=censored,
        ))

        # Add proceeds to cash
        cash += shares * exit_price * (1 - cost)
        del positions[symbol]

    for d_idx, date in enumerate(all_dates):
        # ============ A) EXITS for existing positions ============
        positions_to_close = []

        for symbol, pos in positions.items():
            if symbol not in data:
                continue
            df = data[symbol]

            if date not in df.index:
                # No bar today. If this symbol's data has ended, the position
                # can never be exited by the strategy again: close it at the
                # symbol's last close so the cash is returned and the equity
                # curve does not record a permanent artificial loss (D-79).
                last_date = df.index[-1]
                if date > last_date:
                    positions_to_close.append((
                        symbol, pos, float(df["close"].iloc[-1]), "data_end",
                        last_date, date_to_ordinal[last_date] - pos["entry_bar_idx"], True,
                    ))
                continue  # Otherwise it is just a gap; leave the position open

            bar = df.loc[date]
            bars_held = d_idx - pos["entry_bar_idx"]

            # Check exit conditions in order
            exit_price = None
            exit_reason = None

            # Stop gap: open <= stop
            if bar["open"] <= pos["stop"]:
                exit_price = bar["open"]
                exit_reason = "stop_gap"
            # Stop hit: low <= stop (stop wins ties)
            elif bar["low"] <= pos["stop"]:
                exit_price = pos["stop"]
                exit_reason = "stop"
            # Target gap: open >= target
            elif bar["open"] >= pos["target"]:
                exit_price = bar["open"]
                exit_reason = "target_gap"
            # Target hit: high >= target
            elif bar["high"] >= pos["target"]:
                exit_price = pos["target"]
                exit_reason = "target"
            # Time stop
            elif bars_held >= exit_rules.max_hold_bars:
                exit_price = bar["close"]
                exit_reason = "time"

            if exit_price is not None:
                positions_to_close.append(
                    (symbol, pos, exit_price, exit_reason, date, bars_held, False)
                )

        # Process exits
        for symbol, pos, exit_price, exit_reason, exit_date, bars_held, censored in positions_to_close:
            close_position(symbol, pos, exit_price, exit_reason, exit_date, bars_held, censored)

        # ============ B) ENTRIES ============
        # Candidates fired their signal on their own previous bar.
        candidates = [
            symbol for symbol in candidates_by_date.get(date, ())
            if symbol in data and symbol not in positions and date in data[symbol].index
        ]

        free_slots = rules.max_positions - len(positions)
        if free_slots > 0 and candidates:
            # Shuffle with date-dependent seed
            date_seed = seed + date.toordinal()
            rng = np.random.default_rng(date_seed)
            rng.shuffle(candidates)
            chosen = candidates[:free_slots]

            for symbol in chosen:
                df = data[symbol]
                bar = df.loc[date]
                entry = bar["open"]

                # ATR from previous bar (signal day)
                bar_idx = df.index.searchsorted(date)
                if bar_idx == 0:
                    continue
                prev_bar = df.iloc[bar_idx - 1]
                atr = prev_bar.get("atr14", np.nan)

                if np.isnan(atr) or atr <= 0:
                    continue

                stop = entry - exit_rules.stop_atr * atr
                target = entry + exit_rules.target_atr * atr
                risk_per_share = entry - stop

                if risk_per_share <= 0:
                    continue

                # Equity at previous close (mark-to-market)
                equity_prev = cash
                for sym, pos in positions.items():
                    px = mark_price(sym, date)
                    if px is not None:
                        equity_prev += pos["shares"] * px

                # Position sizing
                shares = int(np.floor(equity_prev * (rules.risk_pct / 100) / risk_per_share))

                # Cap by max_position_pct
                max_shares_pct = int(np.floor(equity_prev * (rules.max_position_pct / 100) / entry))
                shares = min(shares, max_shares_pct)

                # Cap by available cash
                cost = rules.cost_bps_per_side / 10000
                max_shares_cash = int(np.floor(cash / (entry * (1 + cost))))
                shares = min(shares, max_shares_cash)

                if shares < 1:
                    continue

                # Deduct cost
                cash -= shares * entry * (1 + cost)

                # Add position
                positions[symbol] = {
                    "signal_date": df.index[bar_idx - 1],
                    "entry_date": date,
                    "entry_price": entry,
                    "stop": stop,
                    "target": target,
                    "shares": shares,
                    "entry_bar_idx": d_idx,
                }

        # ============ C) SAME-DAY EXIT CHECK for new positions ============
        positions_to_close = []

        for symbol, pos in positions.items():
            if pos["entry_bar_idx"] != d_idx:
                continue  # Only check same-day exits for positions opened today

            df = data[symbol]
            if date not in df.index:
                continue

            bar = df.loc[date]

            # Check only stop/target (not time stop)
            exit_price = None
            exit_reason = None

            if bar["open"] <= pos["stop"]:
                exit_price = bar["open"]
                exit_reason = "stop_gap"
            elif bar["low"] <= pos["stop"]:
                exit_price = pos["stop"]
                exit_reason = "stop"
            elif bar["open"] >= pos["target"]:
                exit_price = bar["open"]
                exit_reason = "target_gap"
            elif bar["high"] >= pos["target"]:
                exit_price = pos["target"]
                exit_reason = "target"

            if exit_price is not None:
                positions_to_close.append(
                    (symbol, pos, exit_price, exit_reason, date, 0, False)
                )

        for symbol, pos, exit_price, exit_reason, exit_date, bars_held, censored in positions_to_close:
            close_position(symbol, pos, exit_price, exit_reason, exit_date, bars_held, censored)

        # ============ D) FINAL BAR: close whatever is still open ============
        if d_idx == len(all_dates) - 1:
            for symbol, pos in list(positions.items()):
                df = data[symbol]
                exit_date = df.index[-1]
                close_position(
                    symbol, pos, float(df["close"].iloc[-1]), "eod_censored",
                    exit_date, date_to_ordinal.get(exit_date, d_idx) - pos["entry_bar_idx"], True,
                )

        # ============ E) MARK EQUITY AT CLOSE ============
        equity = cash
        for symbol, pos in positions.items():
            px = mark_price(symbol, date)
            if px is not None:
                equity += pos["shares"] * px

        equity_curve.append((date, equity))

    equity_series = pd.Series(
        [e for _, e in equity_curve],
        index=pd.DatetimeIndex([d for d, _ in equity_curve]),
        name="equity"
    )

    return trades, equity_series
