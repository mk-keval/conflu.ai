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
    """
    # Get all dates from all symbols (excluding SPY, VIX)
    all_dates = set()
    for sym, df in data.items():
        if sym not in ("SPY", "VIX"):
            all_dates.update(df.index)
    all_dates = sorted(all_dates)
    
    # Convert to Series for easier lookup
    date_to_ordinal = {d: i for i, d in enumerate(all_dates)}
    
    # Initialize state
    cash = rules.start_equity
    positions = {}  # symbol -> {entry_date, entry_price, stop, target, shares, signal_date, entry_bar_idx}
    trades = []
    equity_curve = []
    
    rng = np.random.default_rng(seed)
    
    for d_idx, date in enumerate(all_dates):
        # ============ A) EXITS for existing positions ============
        positions_to_close = []
        
        for symbol, pos in positions.items():
            if symbol not in data:
                continue
            df = data[symbol]
            if date not in df.index:
                continue  # No bar for this symbol today
            
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
                positions_to_close.append((symbol, pos, exit_price, exit_reason, bars_held))
        
        # Process exits
        for symbol, pos, exit_price, exit_reason, bars_held in positions_to_close:
            # Calculate P&L
            entry_price = pos["entry_price"]
            shares = pos["shares"]
            risk_per_share = entry_price - pos["stop"]
            
            r_gross = (exit_price - entry_price) / risk_per_share if risk_per_share > 0 else 0
            cost = rules.cost_bps_per_side / 10000
            r_net = ((exit_price * (1 - cost)) - (entry_price * (1 + cost))) / risk_per_share if risk_per_share > 0 else 0
            pnl_usd = shares * (exit_price - entry_price) - shares * (entry_price + exit_price) * cost
            
            trade = Trade(
                symbol=symbol,
                signal_date=pos["signal_date"],
                entry_date=pos["entry_date"],
                entry_price=entry_price,
                stop=pos["stop"],
                target=pos["target"],
                shares=shares,
                exit_date=date,
                exit_price=exit_price,
                exit_reason=exit_reason,
                bars_held=bars_held,
                r_gross=r_gross,
                r_net=r_net,
                pnl_usd=pnl_usd,
                censored=False
            )
            trades.append(trade)
            
            # Add proceeds to cash
            cash += shares * exit_price * (1 - cost)
            
            # Remove position
            del positions[symbol]
        
        # ============ B) ENTRIES ============
        # Find candidates: signal was True on PREVIOUS trading date of that symbol
        candidates = []
        for symbol, signal_series in signals.items():
            if symbol in ("SPY", "VIX"):
                continue
            if symbol in positions:
                continue  # Already holding
            if symbol not in data:
                continue
            df = data[symbol]
            if date not in df.index:
                continue  # No bar today
            
            # Find previous trading date for this symbol
            symbol_dates = df.index
            prev_dates = symbol_dates[symbol_dates < date]
            if len(prev_dates) == 0:
                continue
            prev_date = prev_dates[-1]
            
            if signal_series.loc[prev_date]:
                candidates.append(symbol)
        
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
                prev_dates = df.index[df.index < date]
                if len(prev_dates) == 0:
                    continue
                prev_date = prev_dates[-1]
                prev_bar = df.loc[prev_date]
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
                    if sym in data and date in data[sym].index:
                        equity_prev += pos["shares"] * data[sym].loc[date, "close"]
                
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
                    "signal_date": prev_date,
                    "entry_date": date,
                    "entry_price": entry,
                    "stop": stop,
                    "target": target,
                    "shares": shares,
                    "entry_bar_idx": d_idx
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
                positions_to_close.append((symbol, pos, exit_price, exit_reason, 0))
        
        for symbol, pos, exit_price, exit_reason, bars_held in positions_to_close:
            entry_price = pos["entry_price"]
            shares = pos["shares"]
            risk_per_share = entry_price - pos["stop"]
            
            r_gross = (exit_price - entry_price) / risk_per_share if risk_per_share > 0 else 0
            cost = rules.cost_bps_per_side / 10000
            r_net = ((exit_price * (1 - cost)) - (entry_price * (1 + cost))) / risk_per_share if risk_per_share > 0 else 0
            pnl_usd = shares * (exit_price - entry_price) - shares * (entry_price + exit_price) * cost
            
            trade = Trade(
                symbol=symbol,
                signal_date=pos["signal_date"],
                entry_date=pos["entry_date"],
                entry_price=entry_price,
                stop=pos["stop"],
                target=pos["target"],
                shares=shares,
                exit_date=date,
                exit_price=exit_price,
                exit_reason=exit_reason,
                bars_held=bars_held,
                r_gross=r_gross,
                r_net=r_net,
                pnl_usd=pnl_usd,
                censored=False
            )
            trades.append(trade)
            
            cash += shares * exit_price * (1 - cost)
            del positions[symbol]
        
        # ============ D) MARK EQUITY AT CLOSE ============
        equity = cash
        for symbol, pos in positions.items():
            if symbol in data and date in data[symbol].index:
                equity += pos["shares"] * data[symbol].loc[date, "close"]
        
        equity_curve.append((date, equity))
    
    # Force close remaining positions at last date (EOD)
    if all_dates:
        last_date = all_dates[-1]
        for symbol, pos in list(positions.items()):
            if symbol not in data or last_date not in data[symbol].index:
                continue
            
            last_bar = data[symbol].loc[last_date]
            exit_price = last_bar["close"]
            exit_reason = "eod_censored"
            bars_held = date_to_ordinal[last_date] - pos["entry_bar_idx"]
            
            entry_price = pos["entry_price"]
            shares = pos["shares"]
            risk_per_share = entry_price - pos["stop"]
            
            r_gross = (exit_price - entry_price) / risk_per_share if risk_per_share > 0 else 0
            cost = rules.cost_bps_per_side / 10000
            r_net = ((exit_price * (1 - cost)) - (entry_price * (1 + cost))) / risk_per_share if risk_per_share > 0 else 0
            pnl_usd = shares * (exit_price - entry_price) - shares * (entry_price + exit_price) * cost
            
            trade = Trade(
                symbol=symbol,
                signal_date=pos["signal_date"],
                entry_date=pos["entry_date"],
                entry_price=entry_price,
                stop=pos["stop"],
                target=pos["target"],
                shares=shares,
                exit_date=last_date,
                exit_price=exit_price,
                exit_reason=exit_reason,
                bars_held=bars_held,
                r_gross=r_gross,
                r_net=r_net,
                pnl_usd=pnl_usd,
                censored=True
            )
            trades.append(trade)
            
            cash += shares * exit_price * (1 - cost)
            del positions[symbol]
    
    equity_series = pd.Series(
        [e for _, e in equity_curve],
        index=pd.DatetimeIndex([d for d, _ in equity_curve]),
        name="equity"
    )
    
    return trades, equity_series