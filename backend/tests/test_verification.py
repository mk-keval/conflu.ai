"""Forward-sample expectancy filtering (audit F4)."""

from __future__ import annotations

from backend.app.domain.workflow import journal as journal_mod
from backend.app.domain.workflow import verification


def _closed(symbol: str, r: float, *, excluded: bool = False) -> None:
    day = "2026-10-05"
    journal_mod.upsert_entry({
        "date_entered": day, "symbol": symbol, "sector": "Technology",
        "entry_price": 100.0, "stop_loss": 95.0, "position_size_pct": 10.0,
        "template": "trend-pullback", "regime": "neutral", "gate_verdict": "PASS",
    })
    assert journal_mod.update_exit(day, symbol, {
        "date_closed": "2026-10-09", "exit_price": 100.0 + 5.0 * r,
        "exit_reason": "target_1", "realized_r": r,
    })
    if excluded:
        assert journal_mod.set_exclude_from_stats(day, symbol, True)


def test_excluded_rows_do_not_enter_template_expectancy() -> None:
    _closed("KEEP", 1.0)
    _closed("LEGACY", -3.0, excluded=True)

    metrics = verification.compute_expectancy_per_template_regime()
    item = metrics["trend-pullback|neutral"]
    assert item.n_trades == 1
    assert item.total_r == 1.0
    assert item.expectancy_r == 1.0


def test_excluded_rows_do_not_enter_rolling_expectancy() -> None:
    _closed("KEEP", 1.0)
    _closed("LEGACY", -3.0, excluded=True)

    rolling = verification.compute_rolling_expectancy(template="trend-pullback")
    assert rolling is not None
    assert rolling["window"] == 1
    assert rolling["total_r"] == 1.0
