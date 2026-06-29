"""Point-in-time helpers — the leakage guard lives here.

Features are computed ``as_of`` a run anchor. The cardinal rule: a value computed
``as_of = T`` must never depend on an event observed after ``T``. Every feature
provider routes its inputs through :func:`as_of_filter` so this is enforced in one
place and provable by a single test.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Iterable, Sequence, TypeVar

T = TypeVar("T")


def as_of_filter(
    events: Iterable[T], as_of: datetime, ts: Callable[[T], datetime]
) -> list[T]:
    """Return only events whose timestamp is at or before ``as_of``.

    This is THE leakage boundary. ``ts`` extracts the event's timestamp. Anything
    strictly after ``as_of`` is invisible — a feature can never see its own future.
    """
    return [e for e in events if ts(e) <= as_of]


def within_window(
    events: Iterable[T],
    as_of: datetime,
    window_days: int,
    ts: Callable[[T], datetime],
) -> list[T]:
    """Events in the trailing ``window_days`` ending at ``as_of`` (inclusive).

    Composes :func:`as_of_filter` — the upper bound is always the point-in-time
    boundary, the lower bound is the rolling window start.
    """
    start = as_of - timedelta(days=window_days)
    return [e for e in as_of_filter(events, as_of, ts) if ts(e) > start]


def zscore(value: float, population: Sequence[float]) -> float:
    """Population z-score of ``value`` against ``population``.

    Returns 0.0 when the population has no spread (std == 0) — a degenerate peer
    group carries no signal, so it must not manufacture one.
    """
    n = len(population)
    if n == 0:
        return 0.0
    mean = sum(population) / n
    var = sum((x - mean) ** 2 for x in population) / n
    if var == 0.0:
        return 0.0
    return (value - mean) / (var ** 0.5)
