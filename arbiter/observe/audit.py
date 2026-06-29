"""Observe — audit & metrics.

A run is not finished until it can explain itself. This module summarizes a run into
a deterministic report: how many subjects were scored, the tier distribution of the
surfaced queue, how many were held below the line, and how many rode the advisory
floor. (Drift monitoring is a separate, later capability — see the roadmap.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ..core.contracts import Score
from ..rank.ranker import RankResult


@dataclass(frozen=True)
class RunReport:
    scored: int
    surfaced: int
    below_line: int
    advisory_only: int
    tier_distribution: Mapping[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "scored": self.scored,
            "surfaced": self.surfaced,
            "below_line": self.below_line,
            "advisory_only": self.advisory_only,
            "tier_distribution": dict(self.tier_distribution),
        }


def summarize(result: RankResult, all_scores: list[Score]) -> RunReport:
    tier_dist: dict[str, int] = {}
    for case in result.surfaced:
        tier_dist[case.tier.value] = tier_dist.get(case.tier.value, 0) + 1
    return RunReport(
        scored=len(all_scores),
        surfaced=len(result.surfaced),
        below_line=len(result.below_line),
        advisory_only=sum(1 for s in all_scores if s.advisory_only),
        tier_distribution=dict(sorted(tier_dist.items())),
    )
