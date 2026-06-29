"""Rank — prioritize & route.

Order scored subjects, assign tiers, and apply the **capacity** constraint: an
analyst team can only work N cases per run, so the platform surfaces the top N and
holds the rest below the line (logged, not dropped). This is the prioritization verb,
and it is deliberately distinct from judging — *what* is risky (score) and *what gets
worked first under finite capacity* (rank) are different decisions.

The advisory floor is enforced here: an ``advisory_only`` subject (model-evidence only)
cannot be assigned a tier more severe than the configured cap. Models suggest; they do
not escalate alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

from ..core.contracts import Case, Score, Tier

# Severity order, most severe first. Index = severity rank (lower = more severe).
_SEVERITY = [Tier.CRITICAL, Tier.HIGH, Tier.MEDIUM, Tier.LOW]


@dataclass(frozen=True)
class RankResult:
    surfaced: tuple[Case, ...]      # the capacity-bounded worked queue
    below_line: tuple[Score, ...]   # held, not dropped — auditable


def _tier_for(composite: float, thresholds: Sequence[Mapping]) -> Tier:
    """Highest tier whose ``min`` the composite meets. ``thresholds`` is config."""
    for entry in sorted(thresholds, key=lambda e: e["min"], reverse=True):
        if composite >= entry["min"]:
            return Tier(entry["tier"])
    return Tier.LOW


def _cap(tier: Tier, cap: Tier) -> Tier:
    """Clamp ``tier`` so it is no more severe than ``cap`` (the advisory floor)."""
    return _SEVERITY[max(_SEVERITY.index(tier), _SEVERITY.index(cap))]


def rank(
    scores: Sequence[Score],
    as_of: datetime,
    tiers: Sequence[Mapping],
    capacity: int,
    advisory_cap: str,
) -> RankResult:
    """Prioritize scores into a capacity-bounded queue of Cases.

    Deterministic ordering: composite desc, then subject_id asc as the tie-break.
    """
    cap_tier = Tier(advisory_cap)

    # Tier every score first (applying the advisory floor), THEN order. A work queue
    # is worked most-severe-tier first, and the floor must move a capped subject down
    # the queue, not merely relabel it — so tier drives ordering, score breaks ties.
    tiered: list[tuple[Score, Tier]] = []
    for score in scores:
        tier = _tier_for(score.composite, tiers)
        if score.advisory_only:
            tier = _cap(tier, cap_tier)
        tiered.append((score, tier))

    ordered = sorted(
        tiered, key=lambda st: (_SEVERITY.index(st[1]), -st[0].composite, st[0].subject_id)
    )

    surfaced: list[Case] = []
    for position, (score, tier) in enumerate(ordered[:capacity], start=1):
        surfaced.append(
            Case(
                subject_id=score.subject_id,
                score=score.composite,
                tier=tier,
                rank=position,
                as_of=as_of,
                evidence={
                    "contributions": dict(score.contributions),
                    "advisory_only": score.advisory_only,
                },
            )
        )
    return RankResult(
        surfaced=tuple(surfaced),
        below_line=tuple(s for s, _ in ordered[capacity:]),
    )
