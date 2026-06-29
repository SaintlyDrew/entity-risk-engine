"""Sandbox — validate / backtest.

The capability that separates "I wired a pipeline" from "I can prove a detector works
before shipping it." Given labeled history (which subjects were *actually* true
positives), the sandbox replays a candidate configuration and measures detection
quality — so a proposed rule or model change is evaluated against ground truth in a
safe sandbox, not in production.

Three instruments, all thin and deterministic:

* :func:`evaluate` — precision@K / recall@K / lift for one run against labels.
* :func:`walk_forward` — the same evaluation across a sequence of point-in-time anchors,
  to see whether a config is stable over time (each anchor sees only data <= itself, so
  this is leakage-free by construction).
* :func:`compare` — A/B two candidate configs and report the precision delta: did the
  change help, hurt, or do nothing?
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from ..core.contracts import Case


@dataclass(frozen=True)
class Metrics:
    k: int
    alert_volume: int
    true_positives_surfaced: int
    precision_at_k: float
    recall_at_k: float
    lift_at_k: float
    base_rate: float

    def as_dict(self) -> dict:
        return {
            "k": self.k,
            "alert_volume": self.alert_volume,
            "true_positives_surfaced": self.true_positives_surfaced,
            "precision_at_k": round(self.precision_at_k, 4),
            "recall_at_k": round(self.recall_at_k, 4),
            "lift_at_k": round(self.lift_at_k, 4),
            "base_rate": round(self.base_rate, 4),
        }


def evaluate(cases: Sequence[Case], labels: Mapping[str, bool], k: int) -> Metrics:
    """Score a ranked case list against ground-truth labels.

    ``labels`` maps subject_id -> is-true-positive over the evaluated population.
    ``precision@K`` = of the top-K surfaced cases, how many were real. ``lift`` = how
    much better than picking at random (precision / base rate).
    """
    top_k = list(cases)[:k]
    total_positives = sum(1 for v in labels.values() if v)
    base_rate = total_positives / len(labels) if labels else 0.0

    tp_surfaced = sum(1 for c in top_k if labels.get(c.subject_id, False))
    precision = tp_surfaced / len(top_k) if top_k else 0.0
    recall = tp_surfaced / total_positives if total_positives else 0.0
    lift = precision / base_rate if base_rate else 0.0

    return Metrics(
        k=k,
        alert_volume=len(top_k),
        true_positives_surfaced=tp_surfaced,
        precision_at_k=precision,
        recall_at_k=recall,
        lift_at_k=lift,
        base_rate=base_rate,
    )


@dataclass(frozen=True)
class WalkForwardResult:
    per_anchor: tuple[tuple[str, Metrics], ...]
    mean_precision_at_k: float

    def as_dict(self) -> dict:
        return {
            "anchors": [
                {"as_of": label, **m.as_dict()} for label, m in self.per_anchor
            ],
            "mean_precision_at_k": round(self.mean_precision_at_k, 4),
        }


def walk_forward(
    run_fn: Callable[[object], Sequence[Case]],
    anchors: Sequence,
    labels: Mapping[str, bool],
    k: int,
) -> WalkForwardResult:
    """Evaluate the same config at each anchor. ``run_fn(anchor) -> ranked cases``.

    Each anchor is a point-in-time cut: the platform sees only data at or before it, so
    this measures genuine forward stability, not in-sample fit.
    """
    rows: list[tuple[str, Metrics]] = []
    for anchor in anchors:
        cases = run_fn(anchor)
        rows.append((str(anchor), evaluate(cases, labels, k)))
    mean_p = sum(m.precision_at_k for _, m in rows) / len(rows) if rows else 0.0
    return WalkForwardResult(per_anchor=tuple(rows), mean_precision_at_k=mean_p)


@dataclass(frozen=True)
class Comparison:
    baseline: Metrics
    candidate: Metrics

    @property
    def precision_delta(self) -> float:
        return self.candidate.precision_at_k - self.baseline.precision_at_k

    def verdict(self) -> str:
        d = self.precision_delta
        if d > 0:
            return f"candidate IMPROVES precision@{self.candidate.k} by {d:+.4f}"
        if d < 0:
            return f"candidate REGRESSES precision@{self.candidate.k} by {d:+.4f}"
        return f"no change in precision@{self.candidate.k}"


def compare(
    baseline_cases: Sequence[Case],
    candidate_cases: Sequence[Case],
    labels: Mapping[str, bool],
    k: int,
) -> Comparison:
    """A/B two candidate configs against the same labels — the pre-ship gate."""
    return Comparison(
        baseline=evaluate(baseline_cases, labels, k),
        candidate=evaluate(candidate_cases, labels, k),
    )
