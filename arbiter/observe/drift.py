"""Observe — feature drift.

A risk-scoring engine decays silently: the world shifts, a feature's distribution moves,
and yesterday's calibrated thresholds quietly stop meaning what they meant. This module
is the early warning — one standard metric, the Population Stability Index (PSI),
comparing a feature's current distribution against a stored baseline.

This is deliberately *one function*, not a monitoring platform. The capability — "notice
when an input has drifted before it corrupts the output" — is the point; the dashboards
that would surround it in production are out of scope for a reference implementation.

PSI interpretation (industry convention):
    < 0.10  no material shift
    0.10 - 0.25  moderate shift — investigate
    > 0.25  significant shift — recalibrate
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

_EPS = 1e-6  # floor so empty bins never produce log(0) / divide-by-zero


@dataclass(frozen=True)
class DriftResult:
    psi: float
    drifted: bool
    threshold: float

    def as_dict(self) -> dict:
        return {
            "psi": round(self.psi, 4),
            "drifted": self.drifted,
            "threshold": self.threshold,
        }


def _proportions(values: Sequence[float], edges: list[float]) -> list[float]:
    """Fraction of ``values`` falling in each bin defined by ``edges``."""
    counts = [0] * (len(edges) - 1)
    for v in values:
        # rightmost bin is closed on the upper end
        placed = False
        for i in range(len(edges) - 1):
            if v < edges[i + 1]:
                counts[i] += 1
                placed = True
                break
        if not placed:
            counts[-1] += 1
    n = len(values) or 1
    return [c / n for c in counts]


def psi(expected: Sequence[float], actual: Sequence[float], bins: int = 10) -> float:
    """Population Stability Index of ``actual`` vs the ``expected`` baseline.

    Bins are equal-width over the baseline's range. Returns 0.0 when the baseline has
    no spread (a constant feature cannot drift in distribution).
    """
    lo, hi = min(expected), max(expected)
    if hi == lo:
        return 0.0
    edges = [lo + (hi - lo) * i / bins for i in range(bins + 1)]
    edges[-1] = math.inf  # absorb anything at/above the baseline max
    edges[0] = -math.inf   # absorb anything below the baseline min

    exp_p = _proportions(expected, edges)
    act_p = _proportions(actual, edges)
    total = 0.0
    for e, a in zip(exp_p, act_p):
        e = max(e, _EPS)
        a = max(a, _EPS)
        total += (a - e) * math.log(a / e)
    return total


def check_drift(
    expected: Sequence[float],
    actual: Sequence[float],
    threshold: float = 0.25,
    bins: int = 10,
) -> DriftResult:
    """Compute PSI and flag whether the feature has drifted past ``threshold``."""
    value = psi(expected, actual, bins)
    return DriftResult(psi=value, drifted=value > threshold, threshold=threshold)
