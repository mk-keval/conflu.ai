"""Pure ETF momentum + trend filter research helpers (H-17 / F4).

No I/O except ``load_snapshot`` (local snapshot read + hash verification).
No network, no randomness except explicit RNG seeds passed to bootstrap.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

RISK_ASSETS: tuple[str, ...] = (
    "SPY",
    "QQQ",
    "IWM",
    "EFA",
    "EEM",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
    "TLT",
    "IEF",
    "LQD",
    "GLD",
    "VNQ",
)
CASH_ASSET = "SHY"
UNIVERSE: tuple[str, ...] = (*RISK_ASSETS, CASH_ASSET)
REQUIRED_MANIFEST_KEYS = {
    "symbol",
    "file_name",
    "sha256",
    "rows",
    "first_date",
    "last_date",
    "source",
    "auto_adjust",
    "yfinance_version",
    "created_utc",
}


@dataclass(frozen=True)
class SimulationResult:
    dates: pd.DatetimeIndex
    portfolio_returns: pd.Series
    weights: pd.DataFrame
    costs: pd.Series
    turnover: pd.Series
    cash_weights: pd.Series


def sha256_of_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_snapshot(
    snapshot_dir: str | Path,
) -> tuple[dict[str, pd.DataFrame], dict]:
    """Load a frozen ETF snapshot and verify file hashes against manifest.

    Raises ValueError on hash mismatch or manifest/schema problems.
    """
    snapshot_dir = Path(snapshot_dir)
    manifest_path = snapshot_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ValueError("manifest entries must be a list")

    data: dict[str, pd.DataFrame] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("manifest entry must be an object")
        missing = REQUIRED_MANIFEST_KEYS - set(entry.keys())
        if missing:
            raise ValueError(f"manifest entry missing keys: {sorted(missing)}")
        file_name = str(entry["file_name"])
        expected = str(entry["sha256"])
        file_path = snapshot_dir / file_name
        if not file_path.exists():
            raise ValueError(f"snapshot file missing: {file_path}")
        actual = sha256_of_file(file_path)
        if actual != expected:
            raise ValueError(
                f"sha256 mismatch for {file_name}: expected {expected}, got {actual}"
            )
        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        df.index = pd.DatetimeIndex(df.index).normalize()
        df = df.sort_index()
        data[str(entry["symbol"])] = df
    return data, manifest


def signal_dates(spy_index: pd.DatetimeIndex | pd.Series | pd.DataFrame) -> pd.DatetimeIndex:
    """Last trading day of each calendar month in SPY's calendar."""
    if isinstance(spy_index, pd.DataFrame):
        idx = pd.DatetimeIndex(spy_index.index)
    elif isinstance(spy_index, pd.Series):
        idx = pd.DatetimeIndex(spy_index.index)
    else:
        idx = pd.DatetimeIndex(spy_index)
    idx = pd.DatetimeIndex(idx).normalize().sort_values().unique()
    if len(idx) == 0:
        return pd.DatetimeIndex([])
    month_key = idx.to_period("M")
    # group by month, take last
    last = {}
    for d, m in zip(idx, month_key):
        last[m] = d
    out = pd.DatetimeIndex([last[m] for m in sorted(last.keys())])
    return out


def _bars_through(symbol_df: pd.DataFrame, s: pd.Timestamp) -> pd.Series | None:
    if s not in symbol_df.index:
        # allow exact timestamp match only by normalized value
        idx = pd.DatetimeIndex(symbol_df.index).normalize()
        matches = np.where(idx == pd.Timestamp(s).normalize())[0]
        if len(matches) == 0:
            return None
        loc = int(matches[-1])
    else:
        loc = int(symbol_df.index.get_loc(s))
        if isinstance(loc, (slice, np.ndarray)):
            # duplicate index shouldn't happen in clean snapshot; take last
            loc = int(np.flatnonzero(symbol_df.index == s)[-1])
    through = symbol_df.iloc[: loc + 1]
    return through["Adj Close"].astype(float)


def eligible_assets(
    data: dict[str, pd.DataFrame],
    s: pd.Timestamp,
    *,
    min_bars: int = 253,
    universe: tuple[str, ...] | list[str] = RISK_ASSETS,
) -> list[str]:
    """Assets with >= min_bars Adj Close bars up to and including s."""
    out: list[str] = []
    s = pd.Timestamp(s).normalize()
    for sym in universe:
        df = data.get(sym)
        if df is None or "Adj Close" not in df.columns:
            continue
        adj = _bars_through(df, s)
        if adj is None:
            continue
        if int(adj.notna().sum()) >= min_bars:
            out.append(sym)
    return out


def momentum_12_1(symbol_df: pd.DataFrame, s: pd.Timestamp) -> float | None:
    """12-1 momentum: AdjClose[s-21]/AdjClose[s-252]-1 in asset's own series."""
    s = pd.Timestamp(s).normalize()
    adj = _bars_through(symbol_df, s)
    if adj is None:
        return None
    adj = adj.dropna()
    # Need positions relative to s in this series; s must be present.
    if pd.Timestamp(s) not in pd.DatetimeIndex(adj.index).normalize():
        return None
    # Use integer positions in the asset's own series including s.
    idx = pd.DatetimeIndex(symbol_df.index).normalize()
    matches = np.where(idx == s)[0]
    if len(matches) == 0:
        return None
    loc = int(matches[-1])
    series = symbol_df["Adj Close"].astype(float)
    i_21 = loc - 21
    i_252 = loc - 252
    if i_252 < 0 or i_21 < 0:
        return None
    a = series.iloc[i_252]
    b = series.iloc[i_21]
    if pd.isna(a) or pd.isna(b) or a == 0:
        return None
    return float(b / a - 1.0)


def trend_pass(symbol_df: pd.DataFrame, s: pd.Timestamp, *, window: int = 200) -> bool:
    """AdjClose[s] > mean(last 200 Adj Close values through s)."""
    s = pd.Timestamp(s).normalize()
    idx = pd.DatetimeIndex(symbol_df.index).normalize()
    matches = np.where(idx == s)[0]
    if len(matches) == 0:
        return False
    loc = int(matches[-1])
    series = symbol_df["Adj Close"].astype(float)
    start = loc - window + 1
    if start < 0:
        return False
    window_vals = series.iloc[start : loc + 1]
    if window_vals.isna().any():
        return False
    cur = series.iloc[loc]
    if pd.isna(cur):
        return False
    return bool(float(cur) > float(window_vals.mean()))


def target_weights(
    selected: list[str] | tuple[str, ...],
    *,
    cash_asset: str = CASH_ASSET,
    universe: tuple[str, ...] | list[str] = UNIVERSE,
    n_slots: int = 5,
) -> dict[str, float]:
    """Equal-weight selected risk assets; unfilled slots in cash. Sums to 1."""
    selected = list(selected)
    weights = {sym: 0.0 for sym in universe}
    slot_w = 1.0 / float(n_slots)
    n_sel = min(len(selected), n_slots)
    for sym in selected[:n_slots]:
        if sym in weights:
            weights[sym] += slot_w
    cash_w = slot_w * (n_slots - n_sel)
    if cash_asset in weights:
        weights[cash_asset] += cash_w
    else:
        weights[cash_asset] = cash_w
    # Normalize tiny float drift.
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("target weights sum to zero")
    for k in weights:
        weights[k] = float(weights[k] / total)
    return weights


def _daily_returns(data: dict[str, pd.DataFrame], calendar: pd.DatetimeIndex) -> pd.DataFrame:
    rets: dict[str, pd.Series] = {}
    for sym, df in data.items():
        if "Adj Close" not in df.columns:
            continue
        s = df["Adj Close"].astype(float).reindex(calendar)
        rets[sym] = s.pct_change()
    return pd.DataFrame(rets, index=calendar)


def _execution_date(calendar: pd.DatetimeIndex, s: pd.Timestamp) -> pd.Timestamp | None:
    s = pd.Timestamp(s).normalize()
    locs = np.where(calendar == s)[0]
    if len(locs) == 0:
        return None
    i = int(locs[-1]) + 1
    if i >= len(calendar):
        return None
    return pd.Timestamp(calendar[i])


def simulate(
    data: dict[str, pd.DataFrame],
    calendar: pd.DatetimeIndex,
    *,
    cost_bps: float = 10.0,
    n_slots: int = 5,
    min_bars: int = 253,
    momentum_skip: int = 21,
    momentum_lookback: int = 252,
    trend_window: int = 200,
    risk_assets: tuple[str, ...] | list[str] = RISK_ASSETS,
    cash_asset: str = CASH_ASSET,
) -> SimulationResult:
    """Simulate frozen H-17 strategy on daily calendar.

    Execution is at close of s+1. On s+1 the PREVIOUS weights earn that day's
    close-to-close gross return and are drifted with gross return; then the
    portfolio trades to target at close of s+1. Cost
    (cost_bps/10000)*sum|w_target-w_drifted| is subtracted from the s+1
    portfolio return. Target weights earn returns from close of s+1 to s+2
    onward and drift on later days with each day's gross return.
    """
    calendar = pd.DatetimeIndex(pd.to_datetime(calendar)).normalize().sort_values().unique()
    universe = (*risk_assets, cash_asset) if cash_asset not in risk_assets else tuple(risk_assets)
    returns = _daily_returns(data, calendar)
    # Ensure all universe columns exist.
    for sym in universe:
        if sym not in returns.columns:
            returns[sym] = np.nan
    returns = returns[list(universe)]

    sig_dates = signal_dates(calendar)
    exec_to_target: dict[pd.Timestamp, dict[str, float]] = {}
    for s in sig_dates:
        ex = _execution_date(calendar, s)
        if ex is None:
            continue
        # Determine selection at s using only data up to and including s.
        eligible = eligible_assets(data, s, min_bars=min_bars, universe=tuple(risk_assets))
        scored: list[tuple[float, str]] = []
        for sym in eligible:
            df = data[sym]
            if not trend_pass(df, s, window=trend_window):
                continue
            m = momentum_12_1(df, s)
            # momentum_12_1 uses frozen 21/252; honor params by inline calc when different.
            if momentum_skip != 21 or momentum_lookback != 252:
                idx = pd.DatetimeIndex(df.index).normalize()
                matches = np.where(idx == pd.Timestamp(s).normalize())[0]
                if len(matches) == 0:
                    m = None
                else:
                    loc = int(matches[-1])
                    i_a = loc - momentum_lookback
                    i_b = loc - momentum_skip
                    if i_a < 0 or i_b < 0:
                        m = None
                    else:
                        a = float(df["Adj Close"].astype(float).iloc[i_a])
                        b = float(df["Adj Close"].astype(float).iloc[i_b])
                        m = None if (pd.isna(a) or pd.isna(b) or a == 0) else float(b / a - 1.0)
            if m is None or np.isnan(m):
                continue
            scored.append((float(m), sym))
        # sort by momentum desc, tie alphabetical by symbol
        scored.sort(key=lambda x: (-x[0], x[1]))
        selected = [sym for _, sym in scored[:n_slots]]
        exec_to_target[pd.Timestamp(ex).normalize()] = target_weights(
            selected, cash_asset=cash_asset, universe=universe, n_slots=n_slots
        )

    # Initial: 100% cash (SHY)
    cur_w = {sym: 0.0 for sym in universe}
    cur_w[cash_asset] = 1.0

    port_rets = []
    costs = []
    turnovers = []
    cash_ws = []
    weight_rows = []

    for dt in calendar:
        dt_n = pd.Timestamp(dt).normalize()
        row_ret = returns.loc[dt]
        cost = 0.0
        turnover = 0.0

        # Previous weights earn this day's gross close-to-close return.
        gross = 0.0
        for sym in universe:
            r = row_ret.get(sym)
            r_f = 0.0 if pd.isna(r) else float(r)
            gross += cur_w.get(sym, 0.0) * r_f

        # Drift previous weights to close using gross return.
        denom = 1.0 + gross
        if denom == 0.0:
            drifted = dict(cur_w)
        else:
            drifted = {}
            for sym in universe:
                r = row_ret.get(sym)
                r_f = 0.0 if pd.isna(r) else float(r)
                drifted[sym] = cur_w.get(sym, 0.0) * (1.0 + r_f) / denom

        net = gross
        if dt_n in exec_to_target:
            target = exec_to_target[dt_n]
            turnover = 0.5 * float(
                sum(abs(target.get(sym, 0.0) - drifted.get(sym, 0.0)) for sym in universe)
            )
            cost = (float(cost_bps) / 10000.0) * float(
                sum(abs(target.get(sym, 0.0) - drifted.get(sym, 0.0)) for sym in universe)
            )
            net = gross - cost
            cur_w = {sym: float(target.get(sym, 0.0)) for sym in universe}
        else:
            cur_w = drifted

        port_rets.append(net)
        costs.append(cost)
        turnovers.append(turnover)
        cash_ws.append(float(cur_w.get(cash_asset, 0.0)))
        weight_rows.append(dict(cur_w))

    out_index = calendar
    port_series = pd.Series(port_rets, index=out_index, dtype=float)
    weights_df = pd.DataFrame(weight_rows, index=out_index)
    return SimulationResult(
        dates=out_index,
        portfolio_returns=port_series,
        weights=weights_df,
        costs=pd.Series(costs, index=out_index, dtype=float),
        turnover=pd.Series(turnovers, index=out_index, dtype=float),
        cash_weights=pd.Series(cash_ws, index=out_index, dtype=float),
    )


def metrics(
    returns: pd.Series | np.ndarray | list[float],
    *,
    turnover: pd.Series | np.ndarray | list[float] | None = None,
    cash_weights: pd.Series | np.ndarray | list[float] | None = None,
    years: float | None = None,
) -> dict[str, float]:
    """Compute H-17 metrics on daily returns within a window.

    CAGR uses elapsed calendar years. Sharpe = mean/std(ddof=1)*sqrt(252).
    MaxDD is negative. Calmar = CAGR / abs(MaxDD). Annual turnover = sum(dw/2)
    per year. Share of days in SHY = fraction of days where cash weight >= 0.9999.
    """
    r = pd.Series(returns).astype(float)
    r = r.replace([np.inf, -np.inf], np.nan).dropna()
    if len(r) == 0:
        return {
            "cagr": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "calmar": 0.0,
            "annual_turnover": 0.0,
            "share_days_in_shy": 0.0,
            "n_days": 0,
        }
    equity = (1.0 + r).cumprod()
    start_val = 1.0
    end_val = float(equity.iloc[-1])
    if years is not None and float(years) > 0:
        years_val = float(years)
    elif isinstance(r.index, pd.DatetimeIndex) and len(r.index) >= 2:
        days = (pd.Timestamp(r.index[-1]) - pd.Timestamp(r.index[0])).days
        years_val = days / 365.25
    else:
        years_val = len(r) / 252.0
    if years_val > 0 and start_val > 0 and end_val > 0:
        cagr = float(end_val ** (1.0 / years_val) - 1.0)
    else:
        cagr = 0.0
    mu = float(r.mean())
    sigma = float(r.std(ddof=1)) if len(r) > 1 else 0.0
    sharpe = float(mu / sigma * np.sqrt(252.0)) if sigma > 0 else 0.0
    peak = equity.cummax()
    dd = equity / peak - 1.0
    max_dd = float(dd.min()) if len(dd) else 0.0
    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0

    ann_turnover = 0.0
    if turnover is not None:
        t = pd.Series(turnover).astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        if len(t) > 0:
            if isinstance(r.index, pd.DatetimeIndex) and len(r.index) >= 2:
                t_years = (pd.Timestamp(r.index[-1]) - pd.Timestamp(r.index[0])).days / 365.25
            else:
                t_years = len(t) / 252.0
            ann_turnover = float(t.sum() / t_years) if t_years > 0 else 0.0

    share_shy = 0.0
    if cash_weights is not None:
        cw = pd.Series(cash_weights).astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        if len(cw) > 0:
            share_shy = float((cw >= 0.9999).mean())

    return {
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "annual_turnover": ann_turnover,
        "share_days_in_shy": share_shy,
        "n_days": int(len(r)),
    }


def paired_month_bootstrap(
    strategy: pd.Series,
    benchmark: pd.Series,
    *,
    n: int = 2000,
    seed: int = 17000,
) -> dict[str, dict[str, float]]:
    """Month-block bootstrap CIs for paired strategy-benchmark differences.

    Whole calendar months of paired daily returns are resampled with replacement.
    Returns CIs for sharpe diff, CAGR diff, and MaxDD magnitude ratio
    abs(MaxDD_strategy)/abs(MaxDD_SPY).
    """
    s = pd.Series(strategy).astype(float)
    b = pd.Series(benchmark).astype(float)
    idx = s.index.intersection(b.index)
    s = s.loc[idx].dropna()
    b = b.loc[s.index].dropna()
    idx = s.index.intersection(b.index)
    s = s.loc[idx]
    b = b.loc[idx]
    if not isinstance(idx, pd.DatetimeIndex):
        raise ValueError("paired_month_bootstrap requires DatetimeIndex")
    if len(idx) == 0:
        raise ValueError("no paired returns")

    years = (pd.Timestamp(idx[-1]) - pd.Timestamp(idx[0])).days / 365.25
    months = idx.to_period("M")
    unique_months = list(dict.fromkeys(months))
    month_groups = {m: idx[months == m] for m in unique_months}

    def _stats(sv: pd.Series, bv: pd.Series) -> tuple[float, float, float]:
        sm = metrics(sv, years=years)
        bm = metrics(bv, years=years)
        sharpe_diff = sm["sharpe"] - bm["sharpe"]
        cagr_diff = sm["cagr"] - bm["cagr"]
        b_dd = abs(bm["max_drawdown"])
        ratio = (abs(sm["max_drawdown"]) / b_dd) if b_dd > 0 else np.nan
        return float(sharpe_diff), float(cagr_diff), float(ratio)

    point = _stats(s, b)
    rng = np.random.default_rng(seed)
    m_arr = np.array(unique_months, dtype=object)
    n_months = len(m_arr)
    sharpe_diffs = np.empty(n)
    cagr_diffs = np.empty(n)
    ratios = np.empty(n)
    for i in range(n):
        sample = rng.integers(0, n_months, size=n_months)
        sampled_idx = pd.DatetimeIndex(np.concatenate([month_groups[m_arr[j]].values for j in sample]))
        sb = s.loc[sampled_idx]
        bb = b.loc[sampled_idx]
        sd, cd, ra = _stats(sb, bb)
        sharpe_diffs[i] = sd
        cagr_diffs[i] = cd
        ratios[i] = ra

    def _ci(arr: np.ndarray, point_est: float) -> dict[str, float]:
        clean = arr[~np.isnan(arr)]
        if len(clean) == 0:
            lo, hi = np.nan, np.nan
        else:
            lo, hi = np.quantile(clean, [0.025, 0.975])
        return {"point": float(point_est), "ci_low": float(lo), "ci_high": float(hi)}

    return {
        "sharpe_diff": _ci(sharpe_diffs, point[0]),
        "cagr_diff": _ci(cagr_diffs, point[1]),
        "maxdd_ratio": _ci(ratios, point[2]),
    }


def tier_flags(
    strategy_metrics: dict[str, float],
    spy_metrics: dict[str, float],
) -> dict[str, bool | str]:
    """Compute Tier A/B flags and four-way label.

    Tier A: abs(MaxDD_strategy) < 0.6 * abs(MaxDD_SPY) AND Sharpe_strategy >= Sharpe_SPY.
    Tier B: CAGR_strategy > CAGR_SPY. Equal is NOT a Tier B pass.
    """
    s_dd = abs(float(strategy_metrics.get("max_drawdown", 0.0)))
    b_dd = abs(float(spy_metrics.get("max_drawdown", 0.0)))
    s_sharpe = float(strategy_metrics.get("sharpe", 0.0))
    b_sharpe = float(spy_metrics.get("sharpe", 0.0))
    s_cagr = float(strategy_metrics.get("cagr", 0.0))
    b_cagr = float(spy_metrics.get("cagr", 0.0))

    tier_a = (s_dd < 0.6 * b_dd) and (s_sharpe >= b_sharpe)
    tier_b = s_cagr > b_cagr  # strict: equal not pass

    if tier_a and tier_b:
        label = "both"
    elif tier_a:
        label = "A only"
    elif tier_b:
        label = "B only"
    else:
        label = "neither"

    return {
        "tier_a": bool(tier_a),
        "tier_b": bool(tier_b),
        "label": label,
    }
