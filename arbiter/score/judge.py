"""Score — judge.

Combine a subject's consolidated Signals plus point-in-time features into one
governed composite Score. This layer is config-driven and domain-agnostic: the
*weights*, the *cited feature-rules*, and their thresholds come from a config object,
so the same judge serves insider-risk, fraud, or AML by swapping config — not code.

Two governance behaviours are structural, not optional:

* **Cited rules carry thresholds.** A feature-rule is ``{feature, op, threshold,
  weight, reason}`` — an auditable statement, not a magic number. This is what makes
  ``score`` a real component and not a bare weighted sum.
* **The advisory floor.** A score driven *only* by model signals is flagged
  ``advisory_only``. The rank layer must not let such a subject escalate to the top
  tier on model evidence alone — models suggest, rules judge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from ..core.contracts import FeatureView, Score, SignalKind, SubjectRecord

_OPS = {
    ">=": lambda a, b: a >= b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
}


@dataclass(frozen=True)
class FeatureRule:
    """An auditable, cited rule over a single feature."""

    id: str
    feature: str
    op: str
    threshold: float
    weight: float
    reason: str = ""

    def fires(self, features: FeatureView) -> bool:
        return _OPS[self.op](features.get(self.feature), self.threshold)


class CompositeJudge:
    """A config-driven :class:`~arbiter.core.contracts.Judge`.

    ``signal_points`` maps a SignalKind to its maximum point contribution (a Signal
    contributes ``value * points``). ``feature_rules`` are cited rules evaluated
    against each subject's FeatureView.
    """

    def __init__(
        self,
        signal_points: Mapping[str, float],
        feature_rules: Sequence[FeatureRule],
        feature_views: Mapping[str, FeatureView],
    ) -> None:
        self.signal_points = dict(signal_points)
        self.feature_rules = list(feature_rules)
        self.feature_views = dict(feature_views)

    @classmethod
    def from_config(
        cls, config: Mapping, feature_views: Mapping[str, FeatureView]
    ) -> "CompositeJudge":
        rules = [FeatureRule(**r) for r in config.get("feature_rules", [])]
        return cls(config.get("signal_points", {}), rules, feature_views)

    def judge(self, subject: SubjectRecord) -> Score:
        contributions: dict[str, float] = {}
        total = 0.0
        has_rule = has_ingested = fired_feature_rule = has_model = False

        for s in subject.signals:
            pts = s.value * self.signal_points.get(s.kind.value, 0.0)
            if pts:
                contributions[f"signal:{s.source_id}"] = round(pts, 4)
                total += pts
            if s.kind == SignalKind.RULE:
                has_rule = True
            elif s.kind == SignalKind.INGESTED:
                has_ingested = True
            elif s.kind == SignalKind.MODEL:
                has_model = True

        features = self.feature_views.get(
            subject.subject_id, FeatureView(subject.subject_id, subject.as_of)
        )
        for rule in self.feature_rules:
            if rule.fires(features):
                contributions[f"rule:{rule.id}"] = rule.weight
                total += rule.weight
                fired_feature_rule = True

        advisory_only = has_model and not (
            has_rule or has_ingested or fired_feature_rule
        )
        return Score(
            subject_id=subject.subject_id,
            composite=round(total, 4),
            contributions=contributions,
            advisory_only=advisory_only,
        )
