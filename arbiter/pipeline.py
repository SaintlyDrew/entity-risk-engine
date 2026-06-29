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
from .core.contracts import (
    Case,
    Detector,
    FeatureProvider,
    FeatureView,
    Score,
    Signal,
    SubjectRecord,
)
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
    detectors: Sequence[Detector] = (),
) -> PipelineResult:
    # Point-in-time: an ingested signal dated after the run anchor is not yet
    # observable. Filtering here is what makes a walk-forward backtest honest.
    signals = [s for s in signals if s.as_of <= as_of]

    # subject universe: everyone an ingested signal mentions, plus everyone the
    # provider knows about as_of (so an in-platform detector can surface a subject who
    # had no upstream signal). Point-in-time: future-only subjects are excluded.
    universe = sorted(
        {s.subject_id for s in signals} | set(feature_provider.known_subjects(as_of))
    )

    # measure: point-in-time features per subject (leakage-guarded in the provider)
    feature_views = {sid: feature_provider.compute(sid, as_of) for sid in universe}

    # suggest: in-platform detectors (rules, models) emit Signals from features. A model
    # is just a Detector here — it has no special path through the platform.
    detector_signals: list[Signal] = []
    for detector in detectors:
        for sid in universe:
            detector_signals.extend(detector.emit(sid, feature_views[sid], as_of))

    # assemble: many signals (ingested + detector-emitted) -> one record per subject.
    # Every known subject is judged, not only those carrying a signal: the cited rules
    # in the score layer are population-wide detections, so a rule (e.g. velocity) must
    # be able to surface a subject that no upstream system flagged.
    by_subject = {
        r.subject_id: r
        for r in consolidate(list(signals) + detector_signals, as_of)
    }
    records = [by_subject.get(sid, SubjectRecord(sid, as_of, ())) for sid in universe]

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
