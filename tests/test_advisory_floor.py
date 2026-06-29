"""The advisory floor: models suggest, rules judge.

A subject scored on model evidence ALONE is flagged ``advisory_only`` and cannot be
escalated above the configured cap, no matter how high the model score. The moment a
rule or ingested signal corroborates, the floor lifts. This is model-risk separation
rendered as a structural rule, tested directly at the score+rank seam.
"""

from __future__ import annotations

from datetime import datetime

from arbiter.core.contracts import (
    FeatureView,
    Signal,
    SignalKind,
    SubjectRecord,
    Tier,
)
from arbiter.rank.ranker import rank
from arbiter.score.judge import CompositeJudge

AS_OF = datetime(2026, 3, 1)
CONFIG = {
    "signal_points": {"rule": 35, "ingested": 30, "model": 28},
    "feature_rules": [],
    "tiers": [
        {"tier": "critical", "min": 70},
        {"tier": "high", "min": 45},
        {"tier": "medium", "min": 20},
        {"tier": "low", "min": 0},
    ],
    "capacity": 10,
    "advisory_cap": "medium",
}


def _judge_and_rank(records):
    views = {r.subject_id: FeatureView(r.subject_id, AS_OF) for r in records}
    judge = CompositeJudge.from_config(CONFIG, views)
    scores = [judge.judge(r) for r in records]
    result = rank(scores, AS_OF, CONFIG["tiers"], CONFIG["capacity"], CONFIG["advisory_cap"])
    return {c.subject_id: c for c in result.surfaced}


def test_model_only_subject_is_flagged_and_capped() -> None:
    # Two strong model signals -> raw 49.0 -> 'high', but model-only -> capped to medium.
    record = SubjectRecord(
        "M-1",
        AS_OF,
        (
            Signal("M-1", "model.a", SignalKind.MODEL, 0.95, AS_OF),
            Signal("M-1", "model.b", SignalKind.MODEL, 0.80, AS_OF),
        ),
    )
    case = _judge_and_rank([record])["M-1"]
    assert case.evidence["advisory_only"] is True
    assert case.score == 49.0
    assert case.tier == Tier.MEDIUM  # floored down from 'high'


def test_corroboration_lifts_the_floor() -> None:
    # Same model evidence + one ingested signal -> not advisory -> 'high' stands.
    record = SubjectRecord(
        "M-2",
        AS_OF,
        (
            Signal("M-2", "model.a", SignalKind.MODEL, 0.95, AS_OF),
            Signal("M-2", "dlp.x", SignalKind.INGESTED, 1.0, AS_OF),
        ),
    )
    case = _judge_and_rank([record])["M-2"]
    assert case.evidence["advisory_only"] is False
    assert case.tier == Tier.HIGH
