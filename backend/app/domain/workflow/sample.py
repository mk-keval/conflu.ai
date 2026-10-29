"""Forward-sample versions (D-76) — which rows are evidence, and for which sample.

The journal keeps every row forever, but a row only counts as evidence for the
sample it was traded under. Versioning makes that explicit instead of relying on
memory or on `exclude_from_stats` flags applied by hand.

Versions
--------
- ``v0.1``   — FWD-v0.1, the first forward sample. **Closed for verdict
  purposes on 2026-10-28** (Q2): it is reference data, never a verdict.
- ``interim`` — daily-loop rows created after the v0.1 close and before the
  v0.2 spec is frozen. Execution diagnostics only; **never evidence**.
- ``v0.2``   — FWD-v0.2, the scored sample. The clock starts at the first fill
  after the Bundle A spec is frozen.

Rows are immutable once written: a re-run must not move a row between samples.
A filled pending order inherits its order's version.

`sample_version` is orthogonal to `voided` and `exclude_from_stats`: those mark
individual bad/legacy rows, this marks the design a row belongs to.
"""

from __future__ import annotations

from typing import Any

SAMPLE_VERSION_V01 = "v0.1"
SAMPLE_VERSION_INTERIM = "interim"
SAMPLE_VERSION_V02 = "v0.2"

SAMPLE_VERSIONS = (
    SAMPLE_VERSION_V01,
    SAMPLE_VERSION_INTERIM,
    SAMPLE_VERSION_V02,
)

# The sample the canonical scorecard judges. Flipped to v0.2 in the spec-freeze
# commit — a visible governance change, not an environment variable.
SCORED_SAMPLE_VERSION = SAMPLE_VERSION_V02

# What every new row/order is stamped with until that freeze.
CURRENT_SAMPLE_VERSION = SAMPLE_VERSION_INTERIM

SAMPLE_VERSION_LABELS = {
    SAMPLE_VERSION_V01: "closed for verdicts 2026-10-28 (Q2/D-76) — reference only",
    SAMPLE_VERSION_INTERIM: "not evidence — loop data between samples",
    SAMPLE_VERSION_V02: "scored sample — starts at first fill after the spec freeze",
}


def normalize_sample_version(value: Any) -> str | None:
    """Canonical version string, or None when the value is unknown.

    A blank value means a pre-versioning row (legacy CSV or a database that
    predates the column), which belongs to v0.1. An unrecognized non-blank
    value is a data error, not a default.
    """
    text = str(value or "").strip().lower()
    if not text:
        return SAMPLE_VERSION_V01
    return text if text in SAMPLE_VERSIONS else None


def current_sample_version() -> str:
    """Version stamped on new journal entries and pending orders."""
    return CURRENT_SAMPLE_VERSION


def is_scored_version(value: Any) -> bool:
    """True when the row belongs to the sample the scorecard judges."""
    return normalize_sample_version(value) == SCORED_SAMPLE_VERSION


__all__ = [
    "SAMPLE_VERSION_V01",
    "SAMPLE_VERSION_INTERIM",
    "SAMPLE_VERSION_V02",
    "SAMPLE_VERSIONS",
    "SAMPLE_VERSION_LABELS",
    "SCORED_SAMPLE_VERSION",
    "CURRENT_SAMPLE_VERSION",
    "normalize_sample_version",
    "current_sample_version",
    "is_scored_version",
]
