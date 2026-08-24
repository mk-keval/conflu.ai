"""Sector Focus scoring tests — synthetic golden cases, no network."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from backend.app.domain.sector_focus.service import (
    METHOD_VERSION,
    absolute_gate_passed,
    build_sector_focus_snapshot,
    compute_focus_score,
    improvement_bonus,
    percentile_scores,
    weekly_return_ranks,
)
from backend.app.api.routers.sector_rotation import SECTOR_SYMBOLS

NOW = datetime(2026, 8, 24, 21, 0, tzinfo=timezone.utc)


def _make_price_df(row_returns: dict[str, list[float]], base: float = 100.0) -> pd.DataFrame:
    """Build a close-price matrix from per-symbol per-row percent returns."""
    n_rows = max(len(v) for v in row_returns.values())
    timestamps = pd.date_range("2026-08-01", periods=n_rows, freq="D")
    data: dict[str, object] = {"timestamp": timestamps}
    for sym, rets in row_returns.items():
        prices = []
        p = base
        for r in rets:
            p *= 1 + r / 100
            prices.append(p)
        data[sym] = prices
    return pd.DataFrame(data)


def _flat(rets: list[float]) -> list[float]:
    return list(rets)


def _base_matrix(last_day: list[float], week: float, n: int = 15) -> dict[str, list[float]]:
    """n symbols; each gets `week`% spread evenly over the prior-week bars and
    `last_day`% on the final bar; earlier bars drift 0.05%/bar."""
    out: dict[str, list[float]] = {}
    syms = SECTOR_SYMBOLS[:n]
    for i, sym in enumerate(syms):
        ld = last_day[i % len(last_day)]
        rows = [0.05] * n
        # prior week window: bars [-12..-7]; recent week: bars [-7..-1]
        for idx in range(n - 12, n - 6):
            rows[idx] = week / 6
        for idx in range(n - 6, n):
            rows[idx] = 0.0
        rows[-1] = ld
        out[sym] = _flat(rows)
    return out


class TestPercentileScores:
    def test_ordering_and_none(self):
        scores = percentile_scores({"A": 1.0, "B": 2.0, "C": 3.0, "D": None})
        assert scores["C"] == 100.0
        assert scores["A"] == pytest.approx(100 / 3, abs=0.1)
        assert scores["D"] is None

    def test_ties_share_score(self):
        scores = percentile_scores({"A": 1.0, "B": 2.0, "C": 2.0})
        assert scores["B"] == scores["C"]

    def test_all_none(self):
        assert percentile_scores({"A": None}) == {"A": None}


class TestFocusScore:
    def test_full_components(self):
        score, used = compute_focus_score(100.0, 80.0, 70.0, 60.0)
        expected = 0.4 * 100 + 0.25 * 80 + 0.2 * 70 + 0.15 * 60
        assert score == pytest.approx(expected, abs=0.1)
        assert used == ["flow", "mom", "rs", "vol"]

    def test_renormalization_on_missing(self):
        s_full, _ = compute_focus_score(100.0, 80.0, 70.0, 60.0)
        s_no_vol, used = compute_focus_score(100.0, 80.0, 70.0, None)
        assert "vol" not in used
        assert s_full is not None and s_no_vol is not None
        # dropping the LOWEST component must raise the composite
        assert s_no_vol > s_full

    def test_insufficient_components_returns_none(self):
        score, used = compute_focus_score(90.0, None, None, None)
        assert score is None
        assert used == ["rs"]

    def test_bonus_applied_and_clamped(self):
        s, _ = compute_focus_score(100.0, 100.0, 100.0, 100.0, bonus=10.0)
        assert s == 100.0


class TestImprovementBonus:
    def test_improved(self):
        assert improvement_bonus(2, 5) == 10.0

    def test_holding_top3(self):
        assert improvement_bonus(3, 3) == 5.0

    def test_worse_or_unknown(self):
        assert improvement_bonus(5, 2) == 0.0
        assert improvement_bonus(1, None) == 0.0


class TestAbsoluteGate:
    def test_beats_spy(self):
        ok, reason = absolute_gate_passed(1.5, 0.4)
        assert ok and reason == ""

    def test_trails_spy(self):
        ok, reason = absolute_gate_passed(-0.5, 0.4)
        assert not ok and "trailing market" in reason

    def test_unknown_benchmark_conservative(self):
        ok, reason = absolute_gate_passed(2.0, None)
        assert not ok and "benchmark" in reason


def _golden_inputs(strong_syms: list[str], weak_last_day: bool = False):
    """Build inputs where `strong_syms` are clear weekly winners beating SPY."""
    n = len(SECTOR_SYMBOLS)
    last_day: list[float] = []
    if weak_last_day:
        last_day = [2.0, 1.5, 1.2, 0.8, 0.5, 0.3, 0.1, -0.1, -0.3, -0.6, -1.0][:n]
        while len(last_day) < n:
            last_day.append(0.2)
    else:
        last_day = [0.6] * n

    rows = _base_matrix(last_day, week=0.3)
    for sym in SECTOR_SYMBOLS:
        rows[sym] = _flat(rows[sym])

    for k, sym in enumerate(SECTOR_SYMBOLS):
        if sym in strong_syms:
            for idx in range(8, 15):
                rows[sym][idx] = 0.7 + 0.1 * k  # compounding into a strong week

    vol_1w = {s: (1.8 if s in strong_syms else 0.9) for s in SECTOR_SYMBOLS}
    flow = {s: (78.0 if s in strong_syms else 35.0) for s in SECTOR_SYMBOLS}
    return rows, vol_1w, flow


class TestSnapshotGolden:
    def test_winner_is_focus_with_reasons(self):
        rows, vol, flow = _golden_inputs(["XLV", "XLF"])
        df = _make_price_df(rows)
        snap = build_sector_focus_snapshot(
            df=df, volume_ratios_1w=vol, flow_strength_1w_by_symbol=flow,
            spy_change_1w=0.2, now=NOW,
        )
        focus_syms = [e.symbol for e in snap.focus]
        assert "XLV" in focus_syms
        top = next(e for e in snap.focus if e.symbol == "XLV")
        assert top.score is not None and top.score >= 70
        assert any("weekly relative strength" in r for r in top.reasons)
        assert any("Institutions accumulating" in r for r in top.reasons)

    def test_snapshot_id_stable_and_sensitive(self):
        rows, vol, flow = _golden_inputs(["XLV"])
        df = _make_price_df(rows)
        s1 = build_sector_focus_snapshot(
            df=df, volume_ratios_1w=vol, flow_strength_1w_by_symbol=flow,
            spy_change_1w=0.2, now=NOW,
        )
        s2 = build_sector_focus_snapshot(
            df=df, volume_ratios_1w=vol, flow_strength_1w_by_symbol=flow,
            spy_change_1w=0.2, now=NOW,
        )
        assert s1.snapshot_id == s2.snapshot_id
        assert s1.snapshot_id.startswith("sha1:")
        vol2 = {**vol, "XLV": 2.5}
        s3 = build_sector_focus_snapshot(
            df=df, volume_ratios_1w=vol2, flow_strength_1w_by_symbol=flow,
            spy_change_1w=0.2, now=NOW,
        )
        assert s3.snapshot_id != s1.snapshot_id

    def test_bearish_regime_no_hunt(self):
        # Bimodal tape: 7 of 11 sectors hard-down on the final day ⇒ the
        # breadth detector must classify broad_market_weakness ⇒ no-hunt mode.
        rows, vol, flow = _golden_inputs(["XLV"])
        losers = [s for s in SECTOR_SYMBOLS if s != "XLV"][:7]
        winners = [s for s in SECTOR_SYMBOLS if s not in losers][:4]
        for sym in losers:
            for idx in range(8, 15):
                rows[sym][idx] = -0.35          # negative week...
            rows[sym][-1] = -0.6                # ...with a hard-down final day
        for i, sym in enumerate(winners):
            if sym == "XLV":
                continue                        # XLV keeps its golden uptrend
            for idx in range(8, 15):
                rows[sym][idx] = 0.3
            rows[sym][-1] = 0.4
        df = _make_price_df(rows)
        snap = build_sector_focus_snapshot(
            df=df, volume_ratios_1w=vol, flow_strength_1w_by_symbol=flow,
            spy_change_1w=-0.5, now=NOW,
        )
        assert snap.market_regime == "broad_market_weakness"
        assert snap.no_hunt_mode is True
        assert snap.focus == []

    def test_cap_enforced_in_mixed_regime(self):
        strong = ["XLV", "XLF", "XLK"]  # 3 qualifiers, mixed regime caps at 2
        rows, vol, flow = _golden_inputs(strong, weak_last_day=True)
        df = _make_price_df(rows)
        snap = build_sector_focus_snapshot(
            df=df, volume_ratios_1w=vol, flow_strength_1w_by_symbol=flow,
            spy_change_1w=0.1, now=NOW,
        )
        assert snap.market_regime == "mixed"
        assert len(snap.focus) <= 2
        demoted = [e for e in snap.watch if e.symbol in strong and e.verdict == "WATCH"]
        if len(snap.focus) == 2:
            assert demoted, "cut candidate should sit in WATCH"

    def test_avoid_list_has_bottom_names_with_plain_language(self):
        rows, vol, flow = _golden_inputs(["XLV"])
        # sink XLE decisively
        for idx in range(8, 15):
            rows["XLE"][idx] = -0.8
        df = _make_price_df(rows)
        snap = build_sector_focus_snapshot(
            df=df, volume_ratios_1w=vol, flow_strength_1w_by_symbol=flow,
            spy_change_1w=0.2, now=NOW,
        )
        assert len(snap.avoid) >= 3
        assert "XLE" in [e.symbol for e in snap.avoid]
        xle = next(e for e in snap.avoid if e.symbol == "XLE")
        assert xle.reasons, "avoid entries must explain themselves"

    def test_missing_signals_degrade_to_watch(self):
        rows, _vol, _flow = _golden_inputs(["XLV"])
        df = _make_price_df(rows)
        snap = build_sector_focus_snapshot(
            df=df, volume_ratios_1w={},  # vol component gone
            flow_strength_1w_by_symbol={},  # flow component gone
            spy_change_1w=0.2, now=NOW,
        )
        # rs + momentum remain ⇒ scores still computed, but weaker tiers
        for e in snap.entries:
            assert e.score is None or e.score >= 0
            assert e.verdict != "FOCUS_CANDIDATE"


class TestWeeklyReturnRanks:
    def test_current_and_previous_windows(self):
        rows = _base_matrix([0.5] * 11, week=0.3)
        # make XLV accelerate late, XLE fade late
        rows["XLV"][-1] = 1.2
        rows["XLE"][-1] = -1.0
        df = _make_price_df(rows)
        cur, prev = weekly_return_ranks(df, SECTOR_SYMBOLS)
        assert cur["XLV"] == 1
        assert cur["XLE"] == len(cur)
        assert prev is not None and set(prev) == set(cur)
