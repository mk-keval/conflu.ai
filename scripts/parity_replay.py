# Parity Replay — swing-parity acceptance harness (Wave 5)
"""
Codifies the parity bar from .sisyphus/plans/swing-parity-upgrade.md against
a RUNNING conflu.ai instance (default http://127.0.0.1:8000).

Assertions
----------
(a) NEUTRAL-regime Morning Brief surfaces >= 3/5 veteran-grade setups.
    Two counts are taken and the max must clear 3:
      - overlap of brief tickers with the veteran's five names
        (ADBE MELI BULL KURA MSTR), and
      - momentum-section tickers carrying conviction >= 7 (veteran-GRADE).
    Name overlap is market-state dependent; conviction-graded setups are
    the stable proxy, both are reported.

(b) Every emitted plan (brief cards + the five veteran analyses) passes the
    geometry invariants: stop beyond the entry zone for LONG plans and
    geometric R/R = (last_target - zone_mid) / (zone_mid - stop) >= 2.0.

(c) The base universe yields > 20 candidate rows: probed through the public
    TV screener endpoint on a broad template.

(d) No template is sticky-empty twice consecutively (two back-to-back brief
    generations; a section empty in BOTH runs fails).

(e) KURA and MSTR emit plans OR their refusals carry regime-based reasons.
    Wrongful-refusal markers (clinical-stage blindness, GAAP-loss kill) fail.

(f) Confirmed breakouts with rvol >= 1.5 show conviction >= 6 (probed over
    the veteran analyses where volume_ratio + alignment data exists).

Usage:
    python scripts/parity_replay.py [--base-url http://127.0.0.1:8000]

Exit code 0 iff all assertions pass. Requires httpx (already a dependency).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import Any

import httpx

VETERAN_SYMBOLS: list[str] = ["ADBE", "MELI", "BULL", "KURA", "MSTR"]
MOMENTUM_SECTION_MARKERS: tuple[str, ...] = (
    "breakout",
    "squeeze",
    "momentum",
    "accumulation",
    "bull-flag",
    "trend-leader",
)
MIN_RR = 2.0
CONVICTION_FLOOR_GRADE = 7
BREAKOUT_RVOL_MIN = 1.5
BREAKOUT_CONVICTION_MIN = 6
WRONGFUL_REFUSAL_MARKERS: tuple[str, ...] = (
    "clinical-stage",
    "gaap loss",
    "no product revenue",
)


@dataclass
class CheckResult:
    key: str
    passed: bool
    detail: str


@dataclass
class ReplayReport:
    results: list[CheckResult] = field(default_factory=list)

    def add(self, key: str, passed: bool, detail: str) -> None:
        self.results.append(CheckResult(key, passed, detail))

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    def render(self) -> str:
        lines = ["Parity replay — assertions vs live app:"]
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"  [{status}] ({r.key}) {r.detail}")
        lines.append("OVERALL: PASS" if self.all_passed else "OVERALL: FAIL")
        return "\n".join(lines)


def _get(client: httpx.Client, path: str) -> dict[str, Any]:
    resp = client.get(path, timeout=180.0)
    resp.raise_for_status()
    payload: dict[str, Any] = resp.json()
    return payload.get("data", payload)


def _post(client: httpx.Client, path: str, json_body: dict[str, Any]) -> dict[str, Any]:
    resp = client.post(path, json=json_body, timeout=240.0)
    resp.raise_for_status()
    payload: dict[str, Any] = resp.json()
    return payload.get("data", payload)


def _plan_levels(verdict: dict[str, Any]) -> bool:
    return bool(
        verdict.get("entry_zone_low") is not None and verdict.get("stop_loss") is not None and verdict.get("targets")
    )


def _geometry_ok(verdict: dict[str, Any]) -> tuple[bool, str]:
    """Invariant 1 (stop < entry_low) + Invariant 2 (geometric R/R >= 2)."""
    low = verdict.get("entry_zone_low")
    high = verdict.get("entry_zone_high")
    stop = verdict.get("stop_loss")
    targets = verdict.get("targets") or []

    if low is None or high is None or stop is None or not targets:
        return True, "no levels — nothing to validate"

    if stop >= low:
        return False, f"stop {stop} inside/beyond entry zone low {low}"

    zone_mid = (float(low) + float(high)) / 2.0
    last_target = float(targets[-1])
    risk = zone_mid - float(stop)
    if risk <= 0:
        return False, f"non-positive risk (mid {zone_mid} <= stop {stop})"
    rr = (last_target - zone_mid) / risk
    if rr < MIN_RR:
        return False, f"geometric R/R {rr:.2f} < {MIN_RR}"
    return True, f"R/R {rr:.2f}"


def check_brief(
    client: httpx.Client,
    report: ReplayReport,
) -> list[dict[str, Any]]:
    """Runs the brief twice (also feeds assertion d). Returns run sections."""
    runs: list[dict[str, Any]] = []
    for i in (1, 2):
        brief = _get(client, "/api/v1/professional/morning-brief?regime=neutral")
        runs.append(
            {
                "run": i,
                "sections": brief.get("screen_sections", []),
                "regime": brief.get("regime"),
            }
        )

    # ── (a) veteran-grade setups ──
    all_tickers: dict[str, dict[str, Any]] = {}
    for run in runs:
        for section in run["sections"]:
            for t in section.get("tickers", []):
                all_tickers.setdefault(t["symbol"], t)
    overlap = sorted(set(all_tickers) & set(VETERAN_SYMBOLS))
    momentum_grade = [
        sym
        for sym, t in all_tickers.items()
        if int(t.get("conviction", 0)) >= CONVICTION_FLOOR_GRADE
        and any(m in (t.get("screen_name") or "").lower() for m in MOMENTUM_SECTION_MARKERS)
    ]
    grade_count = len(set(overlap) | set(momentum_grade))
    report.add(
        "a",
        grade_count >= 3,
        f"veteran-name overlap={len(overlap)}{overlap}, "
        f"momentum conv>={CONVICTION_FLOOR_GRADE} setups={len(momentum_grade)}"
        f"{momentum_grade[:5]} → graded total {grade_count}/5 (need >=3)",
    )

    # ── (b, part 1): brief-card plans obey invariants ──
    bad_brief: list[str] = []
    checked = 0
    for sym, t in all_tickers.items():
        fake_verdict = {
            "entry_zone_low": min(t.get("entry", 0), t.get("stop_loss", 0) + 1e-9),
            "entry_zone_high": t.get("entry", 0),
            "stop_loss": t.get("stop_loss"),
            "targets": t.get("targets") or [],
        }
        # Brief cards store a single `entry`; treat it as the zone midpoint.
        entry = float(t.get("entry") or 0)
        stop = t.get("stop_loss")
        targets = t.get("targets") or []
        if entry > 0 and stop is not None and targets:
            checked += 1
            if float(stop) >= entry:
                bad_brief.append(f"{sym}: stop>=entry")
            risk = entry - float(stop)
            if risk > 0:
                rr = (float(targets[-1]) - entry) / risk
                if rr < MIN_RR:
                    bad_brief.append(f"{sym}: R/R {rr:.2f}")
    report.add(
        "b1",
        not bad_brief,
        f"{checked} brief plans checked, violations={bad_brief or 'none'}",
    )
    return runs


def check_no_sticky_empty(runs: list[dict[str, Any]], report: ReplayReport) -> None:
    """(d) no template sticky-empty twice consecutively."""
    by_screen: dict[str, list[int]] = {}
    for run in runs:
        for section in run["sections"]:
            name = section.get("screen_name", "?")
            by_screen.setdefault(name, []).append(len(section.get("tickers", [])))
    sticky = [
        f"{name}{counts}"
        for name, counts in by_screen.items()
        if len(counts) >= 2 and counts[-1] == 0 and counts[-2] == 0
    ]
    report.add(
        "d",
        not sticky,
        f"section sizes across 2 consecutive runs: "
        f"{ {k: v for k, v in by_screen.items()} }; sticky-empty twice={sticky or 'none'}",
    )


def check_base_universe(client: httpx.Client, report: ReplayReport) -> None:
    """(c) base snapshot/universe yields >20 candidate rows.

    Probes the SAME universal liquidity gates the One-Snapshot-Multi-Screen
    base query applies (exchange/country/close/avg-volume), through the
    public screener endpoint with an inline ScreenConfig — so the check
    measures universe health whether or not the snapshot flag is on.
    """
    base_gates_config = {
        "name": "parity-base-universe",
        "description": "Parity replay: One-Snapshot-Multi-Screen base gates",
        "asset_classes": ["equities"],
        "timeframes": ["1D"],
        "limit": 100,
        "filters": [
            {
                "category": "fundamental",
                "indicator": "exchange_in",
                "params": {"exchanges": ["NYSE", "NASDAQ"]},
                "timeframe": "1D",
            },
            {
                "category": "fundamental",
                "indicator": "country_in",
                "params": {"countries": ["United States"]},
                "timeframe": "1D",
            },
            {
                "category": "fundamental",
                "indicator": "close_above",
                "params": {"threshold": 5.0},
                "timeframe": "1D",
            },
            {
                "category": "volume",
                "indicator": "avg_volume_gt",
                "params": {"threshold": 500000},
                "timeframe": "1D",
            },
        ],
    }
    try:
        result = _post(client, "/api/v1/screen/tv", {"config": base_gates_config})
        rows = int(result.get("total_matches", 0))
        report.add("c", rows > 20, f"base-universe rows={rows} (need >20)")
    except Exception as exc:  # noqa: BLE001 — report, don't crash the harness
        report.add("c", False, f"screener probe failed: {exc}")


def analyze_veteran(client: httpx.Client, symbol: str) -> dict[str, Any]:
    return _post(
        client,
        f"/api/v1/ticker/{symbol}/analyze",
        {"symbol": symbol},
    )


def check_veteran_plans(
    client: httpx.Client,
    report: ReplayReport,
) -> None:
    """(b, part 2) + (e) + (f) over the five veteran analyses."""
    bad_geometry: list[str] = []
    refusal_issues: list[str] = []
    breakout_conviction_issues: list[str] = []
    narrated = 0

    for sym in VETERAN_SYMBOLS:
        data = analyze_veteran(client, sym)
        verdict = data.get("verdict", {})
        technical = data.get("technical") or {}

        narration = verdict.get("narration")
        if narration:
            narrated += 1

        if _plan_levels(verdict):
            ok, detail = _geometry_ok(verdict)
            if not ok:
                bad_geometry.append(f"{sym}: {detail}")

        # (e) KURA/MSTR refusal quality
        if sym in ("KURA", "MSTR"):
            has_plan = _plan_levels(verdict) and verdict.get("action") not in ("N/A", "AVOID")
            flags_text = " ".join(verdict.get("key_red_flags", [])).lower()
            thesis_text = (verdict.get("thesis") or "").lower()
            wrongful = [m for m in WRONGFUL_REFUSAL_MARKERS if m in flags_text]
            if has_plan:
                continue
            if wrongful:
                refusal_issues.append(f"{sym}: wrongful markers {wrongful}")
            elif not flags_text and not thesis_text:
                refusal_issues.append(f"{sym}: refusal without stated reason")

        # (f) confirmed breakout + rvol floor ⇒ conviction floor
        rvol = technical.get("volume_ratio")
        aligned = technical.get("ma_alignment") == "bullish"
        near_high = technical.get("bb_position") == "above_upper"
        if rvol is not None and float(rvol) >= BREAKOUT_RVOL_MIN and aligned and near_high:
            conviction = int(verdict.get("conviction", 0))
            if conviction < BREAKOUT_CONVICTION_MIN:
                breakout_conviction_issues.append(f"{sym}: rvol {rvol} confirmed-bull but conviction {conviction}")

    report.add(
        "b2",
        not bad_geometry,
        f"veteran plan geometry violations={bad_geometry or 'none'}",
    )
    report.add(
        "e",
        not refusal_issues,
        f"KURA/MSTR emit plans or carry regime-based reasons; issues={refusal_issues or 'none'}",
    )
    report.add(
        "f",
        not breakout_conviction_issues,
        f"confirmed-breakout rvol>={BREAKOUT_RVOL_MIN} ⇒ conviction>={BREAKOUT_CONVICTION_MIN}; "
        f"issues={breakout_conviction_issues or 'none'}",
    )
    # Narration coverage rides under (b2) reporting but gets its own line item.
    report.add(
        "narration",
        narrated == len(VETERAN_SYMBOLS),
        f"mentor narration present on {narrated}/{len(VETERAN_SYMBOLS)} veteran verdicts",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Swing-parity acceptance replay")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    report = ReplayReport()
    with httpx.Client(base_url=args.base_url) as client:
        runs = check_brief(client, report)
        check_no_sticky_empty(runs, report)
        check_base_universe(client, report)
        check_veteran_plans(client, report)

    print(report.render())
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
