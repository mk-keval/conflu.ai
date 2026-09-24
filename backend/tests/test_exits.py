"""Exit inference tests (plan Sec.2E).

Bar series: [{'date','open','high','low','close'}] ascending; bar 0 = entry
day (never fills). Conservative rule: stop beats target when both touch.
"""

from __future__ import annotations

from backend.app.domain.workflow import exits


def _bars(rows: list[tuple[str, float, float, float, float]]) -> list[dict]:
    return [
        {"date": d, "open": o, "high": h, "low": lo, "close": c}
        for d, o, h, lo, c in rows
    ]


ENTRY = 100.0
STOP = 95.0          # risk = 5.0 → 1R
T1 = 106.0           # 1.2R
T2 = 112.0           # 2.4R


def test_no_exit_within_data() -> None:
    bars = _bars([
        ("2026-09-01", 100.0, 102.0, 99.0, 101.0),   # entry day
        ("2026-09-02", 101.0, 103.0, 100.0, 102.0),  # nothing hit
    ])
    fill = exits.infer_exit(bars, entry=ENTRY, stop=STOP, targets=[T1, T2])
    assert fill.exit_date is None
    assert fill.exit_reason is None


def test_stop_hit_fills_at_stop() -> None:
    bars = _bars([
        ("2026-09-01", 100.0, 102.0, 99.0, 101.0),
        ("2026-09-02", 97.0, 98.0, 94.0, 95.0),      # low 94 ≤ 95 → stop
    ])
    fill = exits.infer_exit(bars, entry=ENTRY, stop=STOP, targets=[T1, T2])
    assert fill.exit_price == STOP
    assert fill.exit_reason == exits.EXIT_STOP
    assert fill.bars_held == 2
    assert fill.ambiguous is False
    assert fill.mae_r == (94.0 - ENTRY) / 5.0  # low 94 → -1.2R


def test_gap_through_stop_fills_at_open() -> None:
    bars = _bars([
        ("2026-09-01", 100.0, 102.0, 99.0, 101.0),
        ("2026-09-02", 92.0, 93.0, 91.0, 92.0),      # open 92 ≤ 95 → gap fill
    ])
    fill = exits.infer_exit(bars, entry=ENTRY, stop=STOP, targets=[T1, T2])
    assert fill.exit_price == 92.0  # worse than stop
    assert fill.exit_reason == exits.EXIT_STOP


def test_gap_mfe_mae_measured_over_hold() -> None:
    bars = _bars([
        ("2026-09-01", 100.0, 102.0, 99.0, 101.0),
        ("2026-09-02", 92.0, 93.0, 91.0, 92.0),
    ])
    fill = exits.infer_exit(bars, entry=ENTRY, stop=STOP, targets=[T1, T2])
    assert fill.mfe_r == (102.0 - ENTRY) / 5.0   # high 102
    assert fill.mae_r == (91.0 - ENTRY) / 5.0    # low 91


def test_target_2_hit_fills_at_target_2() -> None:
    bars = _bars([
        ("2026-09-01", 100.0, 102.0, 99.0, 101.0),
        ("2026-09-02", 101.0, 113.0, 100.0, 112.0),  # high 113 ≥ 112
    ])
    fill = exits.infer_exit(bars, entry=ENTRY, stop=STOP, targets=[T1, T2])
    assert fill.exit_price == T2
    assert fill.exit_reason == exits.EXIT_TARGET_2
    assert fill.ambiguous is False


def test_target_1_hit_not_target_2() -> None:
    bars = _bars([
        ("2026-09-01", 100.0, 102.0, 99.0, 101.0),
        ("2026-09-02", 101.0, 107.0, 100.0, 106.0),  # high 107 ≥ 106, < 112
    ])
    fill = exits.infer_exit(bars, entry=ENTRY, stop=STOP, targets=[T1, T2])
    assert fill.exit_price == T1
    assert fill.exit_reason == exits.EXIT_TARGET_1


def test_stop_and_target_same_bar_stop_wins_and_flagged() -> None:
    bars = _bars([
        ("2026-09-01", 100.0, 102.0, 99.0, 101.0),
        ("2026-09-02", 96.0, 113.0, 94.0, 112.0),  # low 94 ≤ 95 AND high 113 ≥ 112
    ])
    fill = exits.infer_exit(bars, entry=ENTRY, stop=STOP, targets=[T1, T2])
    assert fill.exit_price == STOP
    assert fill.exit_reason == exits.EXIT_STOP
    assert fill.ambiguous is True


def test_time_stop_fills_at_close() -> None:
    bars = _bars([
        ("2026-09-01", 100.0, 102.0, 99.0, 101.0),
        ("2026-09-02", 101.0, 103.0, 100.0, 102.0),
        ("2026-09-03", 102.0, 104.0, 101.0, 103.0),  # day 3 = max_hold_days 3
    ])
    fill = exits.infer_exit(bars, entry=ENTRY, stop=STOP, targets=[T1, T2], max_hold_days=3)
    assert fill.exit_price == 103.0
    assert fill.exit_reason == exits.EXIT_TIME


def test_invalid_bars_skipped() -> None:
    bars = [
        {"date": "2026-09-01", "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0},
        {"date": "2026-09-02", "open": "bad", "high": 98.0, "low": 94.0, "close": 95.0},
        {"date": "2026-09-03", "open": 95.0, "high": 96.0, "low": 93.0, "close": 94.0},
    ]
    fill = exits.infer_exit(bars, entry=ENTRY, stop=STOP, targets=[T1, T2])
    # Entry day never fills; bar 2 invalid skipped; bar 3 low 93 ≤ 95 → stop.
    assert fill.exit_reason == exits.EXIT_STOP
    assert fill.exit_price == STOP


def test_as_bars_normalizes_tuples_and_dicts() -> None:
    rows = [
        ("2026-09-01", 100.0, 102.0, 99.0, 101.0),
        {"date": "2026-09-02", "open": 101.0, "high": 103.0, "low": 100.0, "close": 102.0},
    ]
    bars = exits.as_bars(rows)  # type: ignore[arg-type]
    assert bars[0]["date"] == "2026-09-01" and bars[0]["open"] == 100.0
    assert bars[1]["date"] == "2026-09-02" and bars[1]["high"] == 103.0


def test_single_target_never_mislabeled_t2() -> None:
    bars = _bars([
        ("2026-09-01", 100.0, 102.0, 99.0, 101.0),
        ("2026-09-02", 101.0, 107.0, 100.0, 106.0),
    ])
    fill = exits.infer_exit(bars, entry=ENTRY, stop=STOP, targets=[T1])  # type: ignore[list-item]
    assert fill.exit_reason == exits.EXIT_TARGET_1
    assert fill.exit_price == T1


def test_empty_or_degenerate_returns_no_exit() -> None:
    assert exits.infer_exit([], entry=ENTRY, stop=STOP, targets=[T1]).exit_date is None
    assert exits.infer_exit(_bars([("2026-09-01", 100.0, 102.0, 99.0, 101.0)]),
                            entry=0.0, stop=STOP).exit_date is None
    assert exits.infer_exit(_bars([("2026-09-01", 100.0, 102.0, 99.0, 101.0)]),
                            entry=ENTRY, stop=101.0).exit_date is None