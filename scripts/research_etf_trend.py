#!/usr/bin/env python
"""Run the frozen H-17 ETF momentum + trend filter study (F4/F5).

Reads a frozen snapshot only. No network. Refuses dirty tree unless
--allow-dirty is passed explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.research.etf_trend import (  # noqa: E402
    CASH_ASSET,
    RISK_ASSETS,
    UNIVERSE,
    _daily_returns,
    _execution_date,
    eligible_assets,
    load_snapshot,
    metrics,
    momentum_12_1,
    paired_month_bootstrap,
    signal_dates,
    simulate,
    target_weights,
    tier_flags,
    trend_pass,
)

DEFAULT_SNAPSHOT = "research_data/etf_20261124"
DEFAULT_PREREG = "docs/backtests/research/PREREGISTRATION-H-17-v1.md"
DEFAULT_REPORT = "docs/backtests/research/ETF_TREND_STUDY_H17.md"
DEFAULT_JSON_DIR = "docs/backtests/research/etf_trend"
DEV_START = "2005-01-01"
DEV_END = "2015-12-31"
HOLDOUT_START = "2016-01-01"


# --- dirty-tree guard (same approach as run_research_baseline.py) ---

def _repo_root() -> Path:
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
        return Path(root)
    except Exception:
        return Path(__file__).resolve().parent.parent


def _repo_relative_dir(output_dir: str | None, root: Path) -> str | None:
    if output_dir is None:
        return None
    try:
        p = Path(output_dir).resolve()
        rel = p.relative_to(root.resolve())
        return str(rel).replace("\\", "/")
    except Exception:
        return None


def _is_within(path: str, directory: str) -> bool:
    path = path.replace("\\", "/")
    directory = directory.strip("/")
    return path == directory or path.startswith(directory + "/")


def _status_has_dirt(status: str, output_dir: str | None, root: Path) -> bool:
    ignored = _repo_relative_dir(output_dir, root)
    entries = status.split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if code[0] in ("R", "C"):
            i += 1
        if code == "??" and ignored is not None and _is_within(path, ignored):
            continue
        return True
    return False


def _git_state(output_dir: str | None = None) -> tuple[str | None, bool | None]:
    try:
        root = _repo_root()
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
        return rev or None, _status_has_dirt(status, output_dir, root)
    except Exception:
        return None, None


def _require_clean_tree(allow_dirty: bool, output_dir: str | None = None) -> tuple[str | None, bool | None]:
    rev, dirty = _git_state(output_dir)
    if dirty is True and not allow_dirty:
        raise SystemExit(
            "Working tree is dirty (HEAD {rev}). Commit or stash your changes, "
            "or pass --allow-dirty to record code.dirty = true in the artifact.".format(
                rev=(rev or "unknown")[:7]
            )
        )
    return rev, dirty


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# --- helpers ---

def _window_slice(series: pd.Series, start: str, end: str) -> pd.Series:
    idx = series.index
    mask = (idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end))
    return series.loc[mask]


def _equity_dd_in_window(returns: pd.Series, start: str, end: str) -> float:
    r = _window_slice(returns, start, end)
    if len(r) == 0:
        return 0.0
    eq = (1.0 + r.astype(float)).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1.0
    return float(dd.min())


def _per_year_returns(returns: pd.Series) -> list[dict]:
    r = returns.dropna()
    if len(r) == 0:
        return []
    years = sorted(set(r.index.year))
    rows = []
    for y in years:
        yr = r[r.index.year == y]
        if len(yr) == 0:
            continue
        eq = float((1.0 + yr).prod() - 1.0)
        rows.append({"year": int(y), "return": eq, "n_days": int(len(yr))})
    return rows


def _window_metrics(sim, start: str, end: str) -> dict:
    r = _window_slice(sim.portfolio_returns, start, end)
    t = _window_slice(sim.turnover, start, end)
    c = _window_slice(sim.cash_weights, start, end)
    m = metrics(r, turnover=t, cash_weights=c)
    m["start"] = start
    m["end"] = end
    return m


def _spy_buy_hold(data: dict[str, pd.DataFrame], calendar: pd.DatetimeIndex) -> pd.Series:
    spy = data["SPY"]["Adj Close"].astype(float).reindex(calendar)
    return spy.pct_change().fillna(0.0)


def _simulate_equal_weight_19(data, calendar, cost_bps=0.0):
    # monthly rebalance equal weight 19 risk assets, no SHY except none.
    assets = list(RISK_ASSETS)
    universe = list(UNIVERSE)
    returns = _daily_returns(data, calendar)
    for sym in universe:
        if sym not in returns.columns:
            returns[sym] = np.nan
    returns = returns[universe]
    sigs = signal_dates(calendar)
    exec_targets = {}
    for s in sigs:
        ex = _execution_date(calendar, s)
        if ex is None:
            continue
        w = {sym: 0.0 for sym in universe}
        for a in assets:
            w[a] = 1.0 / len(assets)
        w[CASH_ASSET] = 0.0
        exec_targets[pd.Timestamp(ex).normalize()] = w
    return _run_weight_schedule(returns, calendar, exec_targets, cost_bps=cost_bps, universe=universe)


def _simulate_60_40_spy_ief(data, calendar, cost_bps=0.0):
    universe = list(UNIVERSE)
    returns = _daily_returns(data, calendar)
    for sym in universe:
        if sym not in returns.columns:
            returns[sym] = np.nan
    returns = returns[universe]
    sigs = signal_dates(calendar)
    exec_targets = {}
    for s in sigs:
        ex = _execution_date(calendar, s)
        if ex is None:
            continue
        w = {sym: 0.0 for sym in universe}
        w["SPY"] = 0.6
        w["IEF"] = 0.4
        exec_targets[pd.Timestamp(ex).normalize()] = w
    return _run_weight_schedule(returns, calendar, exec_targets, cost_bps=cost_bps, universe=universe)


def _simulate_trend_only(data, calendar, cost_bps=10.0):
    universe = list(UNIVERSE)
    returns = _daily_returns(data, calendar)
    for sym in universe:
        if sym not in returns.columns:
            returns[sym] = np.nan
    returns = returns[universe]
    sigs = signal_dates(calendar)
    exec_targets = {}
    for s in sigs:
        ex = _execution_date(calendar, s)
        if ex is None:
            continue
        elig = eligible_assets(data, s, min_bars=253, universe=RISK_ASSETS)
        passing = [sym for sym in elig if trend_pass(data[sym], s, window=200)]
        w = {sym: 0.0 for sym in universe}
        if passing:
            ew = 1.0 / len(passing)
            for sym in passing:
                w[sym] = ew
        else:
            w[CASH_ASSET] = 1.0
        exec_targets[pd.Timestamp(ex).normalize()] = w
    return _run_weight_schedule(returns, calendar, exec_targets, cost_bps=cost_bps, universe=universe)


def _simulate_momentum_no_trend(data, calendar, cost_bps=10.0, n_slots=5):
    universe = list(UNIVERSE)
    returns = _daily_returns(data, calendar)
    for sym in universe:
        if sym not in returns.columns:
            returns[sym] = np.nan
    returns = returns[universe]
    sigs = signal_dates(calendar)
    exec_targets = {}
    for s in sigs:
        ex = _execution_date(calendar, s)
        if ex is None:
            continue
        elig = eligible_assets(data, s, min_bars=253, universe=RISK_ASSETS)
        scored = []
        for sym in elig:
            m = momentum_12_1(data[sym], s)
            if m is None or np.isnan(m):
                continue
            scored.append((float(m), sym))
        scored.sort(key=lambda x: (-x[0], x[1]))
        selected = [sym for _, sym in scored[:n_slots]]
        exec_targets[pd.Timestamp(ex).normalize()] = target_weights(
            selected, cash_asset=CASH_ASSET, universe=tuple(universe), n_slots=n_slots
        )
    return _run_weight_schedule(returns, calendar, exec_targets, cost_bps=cost_bps, universe=universe)


class _Sim:
    def __init__(self, dates, portfolio_returns, weights, costs, turnover, cash_weights):
        self.dates = dates
        self.portfolio_returns = portfolio_returns
        self.weights = weights
        self.costs = costs
        self.turnover = turnover
        self.cash_weights = cash_weights


def _run_weight_schedule(returns, calendar, exec_targets, *, cost_bps, universe):
    cur_w = {sym: 0.0 for sym in universe}
    cur_w[CASH_ASSET] = 1.0
    port_rets, costs, turnovers, cash_ws, weight_rows = [], [], [], [], []
    for dt in calendar:
        dt_n = pd.Timestamp(dt).normalize()
        row_ret = returns.loc[dt]
        cost = 0.0
        turnover = 0.0

        gross = 0.0
        for sym in universe:
            r = row_ret.get(sym)
            r_f = 0.0 if pd.isna(r) else float(r)
            gross += cur_w.get(sym, 0.0) * r_f

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
        if dt_n in exec_targets:
            target = exec_targets[dt_n]
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
        cash_ws.append(float(cur_w.get(CASH_ASSET, 0.0)))
        weight_rows.append(dict(cur_w))
    return _Sim(
        dates=calendar,
        portfolio_returns=pd.Series(port_rets, index=calendar, dtype=float),
        weights=pd.DataFrame(weight_rows, index=calendar),
        costs=pd.Series(costs, index=calendar, dtype=float),
        turnover=pd.Series(turnovers, index=calendar, dtype=float),
        cash_weights=pd.Series(cash_ws, index=calendar, dtype=float),
    )


# --- report ---

def _fmt_pct(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "nan"
    return f"{100*x:.2f}%"


def _fmt_num(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "nan"
    return f"{x:.4f}"


def _ci_text(ci):
    return f"[{_fmt_num(ci['ci_low'])}, {_fmt_num(ci['ci_high'])}]"


def _write_report(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    p = payload
    lines = []
    run_label = p.get("run_label", "F5")
    lines.append(f"# ETF Trend Study H-17 ({run_label})")
    lines.append("")
    lines.append("> EXPLORATORY — never the scorecard, D-75 pass bar, kill rule or any forward verdict.")
    lines.append("")
    lines.append("## Run metadata")
    lines.append("")
    lines.append(f"- Run label: `{run_label}`")
    lines.append(f"- Generated UTC: {p['generated_utc']}")
    lines.append(f"- Code revision: `{p['code_revision']}`")
    lines.append(f"- Dirty: `{p['dirty']}`")
    lines.append(f"- Prereg: `{p['prereg_path']}`")
    lines.append(f"- Prereg sha256: `{p['prereg_sha256']}`")
    lines.append(f"- Snapshot dir: `{p['snapshot_dir']}`")
    lines.append(f"- Manifest sha256: `{p['manifest_sha256']}`")
    if p.get("correction_protocol_sha256"):
        lines.append(f"- Correction protocol: `{p.get('correction_protocol_path')}`")
        lines.append(f"- Correction protocol sha256: `{p['correction_protocol_sha256']}`")
    lines.append("")
    lines.append("## Frozen limits")
    lines.append("")
    lines.append(p["frozen_limits"])
    lines.append("")
    lines.append("## Primary strategy — Tier A/B (holdout)")
    lines.append("")
    tf = p["holdout_tier_flags"]
    lines.append(f"- Tier A: **{tf['tier_a']}**")
    lines.append(f"- Tier B: **{tf['tier_b']}**")
    lines.append(f"- Four-way label: **{tf['label']}**")
    lines.append("")
    lines.append("## Holdout point estimates and CIs (primary vs SPY)")
    lines.append("")
    ci = p["holdout_bootstrap_ci"]
    lines.append("| Metric | Point | 95% month-block CI | CI includes zero/1? |")
    lines.append("|---|---:|---:|---:|")
    for k, label, zero in [
        ("sharpe_diff", "Sharpe diff (strategy-SPY)", 0.0),
        ("cagr_diff", "CAGR diff (strategy-SPY)", 0.0),
        ("maxdd_ratio", "MaxDD magnitude ratio (strategy/SPY)", 1.0),
    ]:
        c = ci[k]
        includes = (c["ci_low"] <= zero <= c["ci_high"]) if not (np.isnan(c["ci_low"]) or np.isnan(c["ci_high"])) else True
        lines.append(f"| {label} | {_fmt_num(c['point'])} | {_ci_text(c)} | {includes} |")
    lines.append("")
    lines.append("If a CI includes zero (or 1 for the ratio) the report must say the bar was met on point estimates and that the difference is not statistically distinguishable.")
    lines.append("")

    def _metrics_table(rows, title):
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| Strategy | CAGR | Sharpe | MaxDD | Calmar | Ann turnover | Share days SHY |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for r in rows:
            m = r["metrics"]
            lines.append(
                f"| {r['name']} | {_fmt_pct(m['cagr'])} | {_fmt_num(m['sharpe'])} | {_fmt_pct(m['max_drawdown'])} | {_fmt_num(m['calmar'])} | {_fmt_num(m['annual_turnover'])} | {_fmt_pct(m['share_days_in_shy'])} |"
            )
        lines.append("")

    _metrics_table(p["dev_comparators"], "Development window (2005-01-01..2015-12-31) — reported only")
    _metrics_table(p["holdout_comparators"], "Holdout window (2016-01-01..latest) — primary")

    lines.append("## Primary strategy per-calendar-year returns")
    lines.append("")
    lines.append("| Year | Return | Days |")
    lines.append("|---:|---:|---:|")
    for row in p["primary_per_year"]:
        lines.append(f"| {row['year']} | {_fmt_pct(row['return'])} | {row['n_days']} |")
    lines.append("")

    lines.append("## Primary strategy drawdowns in 2008/2020/2022")
    lines.append("")
    lines.append("| Period | Max drawdown (window equity restarts at 1.0) |")
    lines.append("|---|---:|")
    for k, v in p["primary_stress_drawdowns"].items():
        lines.append(f"| {k} | {_fmt_pct(v)} |")
    lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", default=DEFAULT_SNAPSHOT, required=True)
    parser.add_argument("--prereg", default=DEFAULT_PREREG)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--json-dir", default=DEFAULT_JSON_DIR)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--run-label", default="F5")
    args = parser.parse_args()

    rev, dirty = _require_clean_tree(args.allow_dirty)

    snapshot_dir = Path(args.snapshot_dir)
    prereg_path = Path(args.prereg)
    report_path = Path(args.report)
    json_dir = Path(args.json_dir)

    data, manifest = load_snapshot(snapshot_dir)
    manifest_path = snapshot_dir / "manifest.json"
    manifest_sha = _sha256_file(manifest_path)
    prereg_sha = _sha256_file(prereg_path) if prereg_path.exists() else "missing"
    protocol_path = Path("docs/backtests/research/H17_CORRECTION_PROTOCOL.md")
    protocol_sha = _sha256_file(protocol_path) if protocol_path.exists() else None

    spy = data["SPY"]
    calendar = pd.DatetimeIndex(spy.index).normalize().sort_values().unique()
    holdout_end = str(calendar.max().date())

    # primary
    primary = simulate(data, calendar, cost_bps=10.0)
    spy_ret = _spy_buy_hold(data, calendar)

    comparators = {}

    def _add(name, sim):
        comparators[name] = sim

    _add("primary_cost_10", primary)
    _add("top3", simulate(data, calendar, cost_bps=10.0, n_slots=3))
    _add("top8", simulate(data, calendar, cost_bps=10.0, n_slots=8))
    _add("trend_only", _simulate_trend_only(data, calendar, cost_bps=10.0))
    _add("momentum_no_trend", _simulate_momentum_no_trend(data, calendar, cost_bps=10.0, n_slots=5))
    _add("primary_cost_0", simulate(data, calendar, cost_bps=0.0))
    _add("primary_cost_25", simulate(data, calendar, cost_bps=25.0))
    _add("spy_ief_60_40", _simulate_60_40_spy_ief(data, calendar, cost_bps=0.0))
    _add("equal_weight_19", _simulate_equal_weight_19(data, calendar, cost_bps=0.0))
    _add("spy_buy_hold", _Sim(calendar, spy_ret, pd.DataFrame(index=calendar), pd.Series(0.0, index=calendar), pd.Series(0.0, index=calendar), pd.Series(0.0, index=calendar)))

    dev_rows = []
    hold_rows = []
    for name, sim in comparators.items():
        dev_rows.append({"name": name, "metrics": _window_metrics(sim, DEV_START, DEV_END)})
        hold_rows.append({"name": name, "metrics": _window_metrics(sim, HOLDOUT_START, holdout_end)})

    primary_hold = _window_metrics(primary, HOLDOUT_START, holdout_end)
    spy_hold = _window_metrics(comparators["spy_buy_hold"], HOLDOUT_START, holdout_end)
    tf = tier_flags(primary_hold, spy_hold)

    strat_hold_ret = _window_slice(primary.portfolio_returns, HOLDOUT_START, holdout_end)
    spy_hold_ret = _window_slice(spy_ret, HOLDOUT_START, holdout_end)
    ci = paired_month_bootstrap(strat_hold_ret, spy_hold_ret, n=2000, seed=17000)

    primary_per_year = _per_year_returns(primary.portfolio_returns)
    stress = {
        "2008": _equity_dd_in_window(primary.portfolio_returns, "2008-01-01", "2008-12-31"),
        "2020": _equity_dd_in_window(primary.portfolio_returns, "2020-01-01", "2020-12-31"),
        "2022": _equity_dd_in_window(primary.portfolio_returns, "2022-01-01", "2022-12-31"),
    }

    frozen_limits = (
        "the 19 ETFs were chosen in 2026 from survivors (ETF survivorship is mild but not zero); "
        "2005-2015 includes 2008; one universe, one sample path, ~21 years; yfinance data; "
        "costs are a flat assumption; no taxes; in-sample for the strategy family (12-1 momentum "
        "and a 200-day trend filter are literature defaults, not fitted here, but the author has "
        "seen general market history); EXPLORATORY, never the scorecard, D-75 pass bar, kill rule "
        "or any forward verdict. In-sample, survivorship-biased universe; no walk-forward."
    )

    payload = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "code_revision": rev,
        "dirty": dirty,
        "run_label": args.run_label,
        "prereg_path": str(prereg_path).replace("\\", "/"),
        "prereg_sha256": prereg_sha,
        "snapshot_dir": str(snapshot_dir).replace("\\", "/"),
        "manifest_sha256": manifest_sha,
        "correction_protocol_path": str(protocol_path).replace("\\", "/") if protocol_sha else None,
        "correction_protocol_sha256": protocol_sha,
        "holdout_tier_flags": tf,
        "holdout_bootstrap_ci": ci,
        "dev_comparators": dev_rows,
        "holdout_comparators": hold_rows,
        "primary_per_year": primary_per_year,
        "primary_stress_drawdowns": stress,
        "frozen_limits": frozen_limits,
    }

    json_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    json_path = json_dir / f"etf_trend_{ts}.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(report_path, payload)

    print(f"report={report_path}")
    print(f"json={json_path}")
    print(f"tier={tf['label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
