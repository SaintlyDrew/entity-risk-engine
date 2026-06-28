"""The orchestrator — the verb-spine wired end to end.

``run_pipeline`` is **domain-agnostic**: it takes already-ingested Signals, a
``FeatureProvider``, and a config object, and walks the spine
consolidate -> features -> score -> rank -> observe. The domain supplies the feature
provider, the config, and the data — never edits this function. Swapping the domain
(insider -> fraud -> AML) is a change of inputs, not of code. That is the platform's
central claim, and ``run_pipeline`` is where it is kept honest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

from .consolidate.consolidate import consolidate
from .core.contracts import Case, FeatureProvider, FeatureView, Score, Signal
from .observe.audit import RunReport, summarize
from .rank.ranker import rank
from .score.judge import CompositeJudge


@dataclass(frozen=True)
class PipelineResult:
    cases: tuple[Case, ...]          # surfaced, capacity-bounded
    below_line: tuple[Score, ...]
    scores: tuple[Score, ...]        # every scored subject
    feature_views: Mapping[str, FeatureView]
    report: RunReport


def run_pipeline(
    signals: Sequence[Signal],
    feature_provider: FeatureProvider,
    config: Mapping,
    as_of: datetime,
) -> PipelineResult:
    # assemble: many signals -> one record per subject
    records = consolidate(signals, as_of)

    # measure: point-in-time features per subject (leakage-guarded in the provider)
    subject_ids = sorted({r.subject_id for r in records})
    feature_views = {
        sid: feature_provider.compute(sid, as_of) for sid in subject_ids
    }

    # judge: governed composite per subject
    judge = CompositeJudge.from_config(config, feature_views)
    scores = [judge.judge(r) for r in records]

    # prioritize: capacity-bounded queue + advisory floor
    ranked = rank(
        scores,
        as_of,
        tiers=config["tiers"],
        capacity=int(config["capacity"]),
        advisory_cap=config["advisory_cap"],
    )

    # observe: a run that explains itself
    report = summarize(ranked, scores)

    return PipelineResult(
        cases=ranked.surfaced,
        below_line=ranked.below_line,
        scores=tuple(scores),
        feature_views=feature_views,
        report=report,
    )
