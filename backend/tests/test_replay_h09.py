"""H-09 exploratory replay tests (D-78).

Covers the two-arm orchestration (shared signal stream, rejects, funnel), the
frozen v0.1 signal engine on the v0.2 path, the additive ledger migration, and
the verifier CLI against a real (temporary) replay ledger.

Network is never touched: OHLCV, regime frames and the screen mix are injected.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.app.domain.workflow import journal_store
from backend.app.domain.workflow import replay_store
from backend.app.infrastructure.backtest import replay as replay_mod
from backend.app.infrastructure.backtest import replay_rules as rules
from backend.app.infrastructure.backtest.replay import ReplayParams, run_replay
from backend.app.infrastructure.screener.configs import FilterRule, ScreenConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
_NOW = datetime(2026, 10, 30, 16, 0, tzinfo=UTC)
_WINDOW = {"window_start": "2026-08-20", "window_end": "2026-10-19"}


# ── Fixtures ────────────────────────────────────────────────────────────────


def _frame(
    *,
    peak: float | None,
    dip: bool,
    end: str = "2026-10-30",
    periods: int = 260,
    signal_index: int = 240,
) -> pd.DataFrame:
    """A gentle ramp with one prior swing high and (optionally) post-signal dips.

    ``periods=260`` clears ``replay_data.MIN_DAILY_BARS`` so the injected frame
    survives ``filter_usable``. ``signal_index`` lands inside the frozen
    window; the ramp reaches 104 about ten sessions earlier, so the engine has
    close-above-100 signals in-window. No swing lows are created on purpose, so
    the measured-move candidate never appears and the only structural level is
    the prior peak. ``dip=False`` holds 104.5 flat after the ramp, so the H-09
    limit is never touched.
    """
    closes = np.full(periods, 93.0)
    peak_index = 77
    if peak is not None:
        triangle = np.concatenate([
            np.linspace(93.0, peak, 8),
            np.linspace(peak, 93.0, 8)[1:],
        ])
        closes[70 : 70 + len(triangle)] = triangle
    # Ramp from the base to 104, ending at the signal bar. A one-bar pullback
    # just after the 100 crossing gives the H-09 limit something to touch
    # without breaking the engine's own (2xATR) stop.
    ramp = np.linspace(93.0, 104.0, 30)
    closes[signal_index - len(ramp) : signal_index] = ramp
    if dip:
        closes[signal_index - 10] = 99.0
    if not dip:
        closes[signal_index:] = 104.5
    else:
        # Alternate 103 / 104 so a signal at 104 is followed by a bar whose low
        # touches the 1.5%-wide limit while staying above the 2xATR stop.
        tail = periods - signal_index
        closes[signal_index:] = np.tile([104.0, 103.0], tail // 2 + 1)[:tail]
        closes[signal_index] = 104.0
        if signal_index + 5 < periods:
            closes[signal_index + 5] = 109.0  # clears T1 and arms the trail
        if signal_index + 6 < periods:
            closes[signal_index + 6] = 103.0

    idx = pd.bdate_range(end=end, periods=periods)
    close = pd.Series(closes, index=idx, dtype=float)
    prev = close.shift(1).fillna(close.iloc[0])
    high = np.maximum(prev, close) + 0.7
    if peak is not None:
        # Give the triangle a single-bar wick; otherwise the next bar inherits
        # the peak close and the highs tie, so no strict swing high exists.
        high.iloc[peak_index] = closes[peak_index] + 1.5
    return pd.DataFrame(
        {
            "Open": prev,
            "High": high,
            "Low": np.minimum(prev, close) - 0.7,
            "Close": close,
            "Volume": 1_000_000.0,
        },
        index=idx,
    )


def _screen() -> ScreenConfig:
    return ScreenConfig(
        name="Trend Follower",
        filters=[
            FilterRule(
                category="momentum",
                indicator="close_above",
                params={"threshold": 100.0},
                operator="gt",
            )
        ],
        timeframes=["1D"],
        direction="long",
    )


def _mix(screen: ScreenConfig) -> dict[str, list[dict]]:
    return {
        "strong_trend": [
            {
                "stem": "trend-follower",
                "config": screen,
                "weight": 95.0,
                "role": "",
                "rank": 1,
            }
        ]
    }


def _patch_regime(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_map(macro, sector, dates):  # noqa: ARG001
        return {
            pd.Timestamp(d).date().isoformat(): {
                "date": pd.Timestamp(d).date().isoformat(),
                "label": "Risk-On",
                "key": "strong_trend",
                "composite": 82.0,
            }
            for d in dates
        }

    monkeypatch.setattr(replay_mod, "historical_regime_map", fake_map)


def _candidate(frame: pd.DataFrame, symbol: str, index: int) -> dict:
    signal_date = frame.index[index].date().isoformat()
    return {
        "signal_date": signal_date,
        "symbol": symbol,
        "template": "trend-follower",
        "screen_name": "Trend Follower",
        "regime": "Risk-On",
        "regime_key": "strong_trend",
        "screen_rank": 1,
        "screen_total": 1,
        "screen_weight": 95.0,
        "trade": {},
        "rvol": 1.0,
        "also_signaled_by": "",
    }


# ── Guards ──────────────────────────────────────────────────────────────────


def test_v02_requires_an_explicit_window() -> None:
    with pytest.raises(ValueError, match="explicit window_start"):
        asyncio.run(
            run_replay(
                ReplayParams(rules_version="v0.2"),
                symbols=["AAA"],
                daily={"AAA": _frame(peak=108.0, dip=True)},
                hourly={},
                regime_frames={},
                screen_mix={},
                progress=False,
                now=_NOW,
            )
        )


def test_v02_requires_zero_day_cap() -> None:
    with pytest.raises(ValueError, match="max_per_day=0"):
        asyncio.run(
            run_replay(
                ReplayParams(rules_version="v0.2", max_per_day=1, **_WINDOW),
                symbols=["AAA"],
                daily={"AAA": _frame(peak=108.0, dip=True)},
                hourly={},
                regime_frames={},
                screen_mix={},
                progress=False,
                now=_NOW,
            )
        )


# ── Two-arm orchestration ───────────────────────────────────────────────────


def test_run_h09_shares_the_stream_and_reconciles_the_funnel() -> None:
    frames = {
        "AAA": _frame(peak=107.0, dip=True),   # v0.2 accepted
        "BBB": _frame(peak=104.0, dip=True),   # v0.2 rejected (target too close)
        "CCC": _frame(peak=107.0, dip=False),  # never fills (limit untouched)
    }
    candidates = [
        _candidate(frames["AAA"], "AAA", 240),
        _candidate(frames["BBB"], "BBB", 240),
        _candidate(frames["CCC"], "CCC", 240),
    ]
    params = ReplayParams(rules_version="v0.2", **_WINDOW)
    result = replay_mod._run_h09(  # noqa: SLF001 - the orchestration is the unit
        params,
        candidates,
        frames,
        templates={"trend-follower": _screen()},
        horizon_end="2026-10-30",
    )

    funnel = result["funnel"]
    assert funnel["deduped"] == 3
    assert funnel["orders"] == 3
    assert funnel["filled"] == 2
    assert funnel["expired"] == 1
    assert funnel["v02_accepted"] == 1
    assert funnel["v02_rejected"] == 1
    assert funnel["v02_rejected_reasons"] == {"target too close": 1}
    assert funnel["v01_accepted"] + funnel["v01_gated_out"] == funnel["filled"]

    assert {row["signal_key"] for row in result["arms"]["v01"]} == {
        row["signal_key"] for row in result["arms"]["v02"]
    }
    assert result["unknown_screens"] == []

    rows = result["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["symbol"] == "AAA"
    assert row["rules_version"] == "v0.2"
    assert row["setup_family"] == "trend"
    assert row["gate_verdict"] in ("PASS", "CONDITIONAL")
    assert row["accepted"] is True
    assert row["has_exit"] is True
    assert row["realized_r"] is not None
    assert row["pnl_usd"] is not None and row["costs_usd"] is not None
    assert row["exit_legs"]
    legs = json.loads(row["exit_legs"])
    assert sum(leg["size_pct"] for leg in legs) == pytest.approx(100.0, abs=0.01)
    assert row["plan_rr"] == pytest.approx(row["target_1_r"])
    assert row["risk_pct"] in (0.5, 1.0)

    # The v0.2-rejected plan still has a v0.1 counterfactual exit.
    rejected = [r for r in result["arms"]["v02"] if r["rejection"]]
    assert rejected[0]["symbol"] == "BBB"
    assert rejected[0]["rejection"] == "target too close"
    assert result["delta"]["rejection_quality"]["v02_rejected"]["n"] == 1


def test_run_h09_marks_censored_trades_and_excludes_them_from_primary() -> None:
    full = _frame(peak=107.0, dip=True)
    cut = full.index[242]
    frames = {"AAA": full.loc[:cut]}
    candidates = [_candidate(full, "AAA", 240)]

    result = replay_mod._run_h09(  # noqa: SLF001
        ReplayParams(rules_version="v0.2", **_WINDOW),
        candidates,
        frames,
        templates={"trend-follower": _screen()},
        horizon_end=cut.date().isoformat(),
    )
    assert result["funnel"]["v02_accepted"] == 1
    assert result["funnel"]["v02_eod"] == 1
    assert result["funnel"]["v02_closed"] == 0
    assert result["rows"][0]["censored"] is True
    assert result["rows"][0]["exit_reason"] == "eod"


# ── End-to-end run + ledger + verifier ──────────────────────────────────────


def test_run_replay_v02_end_to_end_with_ledger_and_verifier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_regime(monkeypatch)
    daily = {
        "AAA": _frame(peak=104.0, dip=True),
        "BBB": _frame(peak=107.0, dip=False),
    }
    idx = daily["AAA"].index
    spy = pd.DataFrame(
        {
            "Open": 100.0,
            "High": 101.0,
            "Low": 99.0,
            "Close": 100.0,
            "Volume": 1_000_000.0,
        },
        index=idx,
    )

    result = asyncio.run(
        run_replay(
            ReplayParams(rules_version="v0.2", **_WINDOW),
            symbols=["AAA", "BBB"],
            daily=daily,
            hourly={},
            regime_frames={"SPY": spy},
            screen_mix=_mix(_screen()),
            progress=False,
            now=_NOW,
        )
    )

    run = result.run
    assert run["rules_version"] == "v0.2"
    assert run["window_start"] == "2026-08-20"
    assert run["window_end"] == "2026-10-19"
    assert run["metadata"]["evidence_label"] == "exploratory_h09_not_evidence"
    assert run["metadata"]["data_horizon"] == {
        "as_of": "2026-10-30",
        "window_end": "2026-10-19",
        "days": 11,
        "required_days": 36,
        "ok": False,
    }
    assert run["metadata"]["h09"]["design"]["deviations"] == []
    assert run["metadata"]["h09"]["funnel"]["orders"] > 0
    assert "exploratory_h09_not_evidence" in run["metadata"]["caveats"][0]
    assert result.rows, "the synthetic frame should produce at least one fill"
    assert all(row["rules_version"] == "v0.2" for row in result.rows)
    assert set(result.artifacts) == {"arms"}

    run_id = replay_store.replace_run(run, result.rows)
    stored = replay_store.latest_run()
    assert stored is not None
    assert stored["run"]["id"] == run_id
    assert stored["run"]["rules_version"] == "v0.2"
    assert len(stored["rows"]) == len(result.rows)
    first = stored["rows"][0]
    assert first["setup_family"] in ("trend", "unknown")
    assert first["exit_legs"]
    assert first["plan_rr"] is not None

    # The verifier is the pass/fail gate. Horizon < 36d makes the write refusal
    # explicit, so give the stored run the recorded consent a real early write
    # would carry.
    run["metadata"]["write_consent"] = {
        "allow_censored": True,
        "horizon_days": 11,
        "required_days": 36,
        "note": "test",
    }
    # Re-store after adding consent (the CLI does this before replace_run).
    replay_store.replace_run(run, result.rows)

    artifact = tmp_path / "h09_artifact.json"
    artifact.write_text(
        json.dumps({"run": run, "rows": result.rows, **result.artifacts}, default=str),
        encoding="utf-8",
    )
    # The artifact must be the pre-consent copy for the metadata comparison; the
    # verifier compares the H-09 block only, so consent is invisible to it.
    script = REPO_ROOT / "backend" / "scripts" / "verify_replay.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--db",
            str(journal_store.get_db_path()),
            "--artifact",
            str(artifact),
            "--expected-paper-trades",
            "0",
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] == "PASS", report["failures"]
    assert report["rows"]["total"] == len(result.rows)


# ── Store migration ─────────────────────────────────────────────────────────


def test_replay_store_migrates_a_d71_ledger_additively(tmp_path: Path) -> None:
    db = tmp_path / "legacy_replay.db"
    journal_store.set_db_path(db)
    with sqlite3.connect(db) as con:
        con.executescript(
            """
            CREATE TABLE replay_runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              generated_at TEXT NOT NULL,
              window_start TEXT NOT NULL,
              window_end TEXT NOT NULL,
              universe_count INTEGER NOT NULL,
              templates_count INTEGER NOT NULL,
              params_json TEXT NOT NULL,
              summary_json TEXT NOT NULL,
              metadata_json TEXT
            );
            CREATE TABLE replay_trades (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              run_id INTEGER NOT NULL,
              date_entered TEXT NOT NULL,
              symbol TEXT NOT NULL,
              entry_price REAL,
              stop_loss REAL,
              pnl_usd REAL,
              created_at TEXT NOT NULL
            );
            INSERT INTO replay_runs
              (generated_at, window_start, window_end, universe_count,
               templates_count, params_json, summary_json, metadata_json)
            VALUES ('2026-10-19T20:00:00+00:00', '2026-08-20', '2026-10-19',
                    500, 14, '{}', '{}', '{}');
            INSERT INTO replay_trades
              (run_id, date_entered, symbol, entry_price, stop_loss, pnl_usd, created_at)
            VALUES (1, '2026-09-01', 'OLD', 100.0, 95.0, 42.0,
                    '2026-10-19T20:00:00+00:00');
            """
        )

    replay_store.ensure()

    with journal_store.session() as con:
        columns = {
            str(row[1]) for row in con.execute("PRAGMA table_info(replay_trades)")
        }
        assert {
            "rules_version",
            "setup_family",
            "entry_low",
            "entry_high",
            "target_2",
            "target_3",
            "plan_rr",
            "target_1_r",
            "stretch_rr",
            "atr_at_entry",
            "gate_verdict",
            "gate_note",
            "mfe_r",
            "mae_r",
            "plan_adherence",
            "exit_legs",
            "pnl_gross_usd",
            "costs_usd",
        } <= columns
        legacy = con.execute("SELECT * FROM replay_trades WHERE symbol = 'OLD'").fetchone()
        assert legacy is not None
        assert legacy["pnl_usd"] == 42.0
        assert legacy["rules_version"] is None

    # Existing rows are never rewritten and a new run can be stored beside them.
    payload = replay_store.latest_run()
    assert payload is not None
    assert payload["run"]["rules_version"] == "v0.1"
    replay_store.replace_run(
        {"window_start": "2026-08-20", "window_end": "2026-10-19", "rules_version": "v0.2"},
        [],
    )
    assert replay_store.latest_run()["run"]["rules_version"] == "v0.2"


# ── Rules parity beyond the pure module tests ───────────────────────────────


def test_signal_engine_constants_are_frozen() -> None:
    assert rules.SIGNAL_STOP_ATR_MULT == 2.0
    assert rules.SIGNAL_TARGET_ATR_MULT == 3.0
    assert rules.SIGNAL_MAX_HOLD_BARS == 15
    assert rules.STOP_ATR_MULT == 2.0
    assert rules.ENTRY_ZONE_ATR_MULT == 0.5
    assert rules.MIN_ZONE_PCT == 1.5
    assert rules.FILL_EXPIRY_SESSIONS == 3
    assert rules.V01_MAX_HOLD_DAYS == 30


def test_verify_replay_module_imports() -> None:
    """The verifier must stay importable (it is git-ignored but deployed)."""
    path = REPO_ROOT / "backend" / "scripts" / "verify_replay.py"
    spec = importlib.util.spec_from_file_location("verify_replay", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.EVIDENCE_LABEL == "exploratory_h09_not_evidence"
