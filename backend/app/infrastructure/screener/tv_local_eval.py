# Local filter evaluation — pandas-backed shims for FILTER_MAP expressions (P1.2)
"""
One-Snapshot-Multi-Screen evaluates every template's filters LOCALLY against
a single broad TV snapshot DataFrame instead of issuing one upstream query
per template.

The :data:`FILTER_MAP` lambdas in ``tv_specialist`` are expression builders
parameterised by a ``Column`` factory. Feeding them :class:`LocalColumn`
makes them produce :class:`LocalCond` boolean-mask wrappers instead of TV
query expressions, so the SAME filter definitions drive both upstream
(server-side where clauses) and local (pandas masking) evaluation — one
source of truth for screen semantics.

Semantics mirror the TV-side operators:

======================  ====================================================
TV operator             Local equivalent
======================  ====================================================
``a > b`` / ``<`` etc   numeric comparison (NaN -> False)
``col.isin(values)``    ``Series.isin``
``crosses_above(o)``    ``(s > o) & (s.shift(1) <= o.shift(1))``
``crosses_below(o)``    inverse cross
``s.below_pct(o, p)``   ``s < o * p`` (pct as multiplier, e.g. 1.03)
``And(...) / Or(...)``  ``&`` / ``|`` reduction (see tv_specialist._and/_or)
======================  ====================================================

Known divergence (documented, accepted while the feature flag is OFF by
default): rules tagged with a non-default timeframe are evaluated against
the single snapshot interval rather than their own timeframe.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


class FilterEvaluationError(ValueError):
    """Raised when a filter cannot be evaluated against the local snapshot."""


class LocalCond:
    """Boolean-mask wrapper supporting ``&`` / ``|`` composition."""

    __slots__ = ("mask",)

    def __init__(self, mask: pd.Series) -> None:
        self.mask = mask.fillna(False).astype(bool)

    def __and__(self, other: "LocalCond") -> "LocalCond":
        return LocalCond(self.mask & other.mask)

    def __or__(self, other: "LocalCond") -> "LocalCond":
        return LocalCond(self.mask | other.mask)


def _is_local_cond(obj: Any) -> bool:
    """True when *obj* is a locally-evaluated condition."""
    return isinstance(obj, LocalCond)


class LocalColumn:
    """Column factory product evaluating FILTER_MAP expressions on a frame."""

    __slots__ = ("_name", "_raw")

    def __init__(self, frame: pd.DataFrame, name: str) -> None:
        self._name = name
        try:
            self._raw = frame[name]
        except KeyError as exc:
            raise FilterEvaluationError(f"column '{name}' missing from base snapshot") from exc

    @property
    def name(self) -> str:
        return self._name

    def _numeric(self) -> pd.Series:
        return pd.to_numeric(self._raw, errors="coerce")

    def _other_numeric(self, other: Any) -> pd.Series:
        if isinstance(other, LocalColumn):
            return other._numeric()
        return pd.to_numeric(pd.Series(other, index=self._raw.index), errors="coerce")

    # -- comparisons ---------------------------------------------------

    def __gt__(self, other: Any) -> LocalCond:
        return LocalCond(self._numeric() > self._other_numeric(other))

    def __lt__(self, other: Any) -> LocalCond:
        return LocalCond(self._numeric() < self._other_numeric(other))

    def __ge__(self, other: Any) -> LocalCond:
        return LocalCond(self._numeric() >= self._other_numeric(other))

    def __le__(self, other: Any) -> LocalCond:
        return LocalCond(self._numeric() <= self._other_numeric(other))

    # NOTE: overriding __eq__ disables hashing — acceptable for these
    # short-lived per-evaluation objects.
    def __eq__(self, other: Any) -> LocalCond:  # type: ignore[override]
        return LocalCond(self._raw == other)

    # -- compound operators --------------------------------------------

    def isin(self, values: Any) -> LocalCond:
        return LocalCond(self._raw.isin(list(values)))

    def crosses_above(self, other: Any) -> LocalCond:
        s = self._numeric()
        o = self._other_numeric(other)
        fresh_cross = (s > o) & (s.shift(1) <= o.shift(1))
        return LocalCond(fresh_cross)

    def crosses_below(self, other: Any) -> LocalCond:
        s = self._numeric()
        o = self._other_numeric(other)
        fresh_cross = (s < o) & (s.shift(1) >= o.shift(1))
        return LocalCond(fresh_cross)

    def below_pct(self, other: Any, pct: float = 1.03) -> LocalCond:
        """``self < other * pct`` — pct is a multiplier (mirrors TV side)."""
        s = self._numeric()
        o = self._other_numeric(other)
        return LocalCond(s < o * pct)
