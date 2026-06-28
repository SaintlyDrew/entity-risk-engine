"""Typed contracts for the detection platform.

This module is the architectural spine. Every component communicates through the
records and protocols defined here — nothing crosses a seam untyped. Read this file
first; the rest of the platform is implementations of these interfaces.

Two invariants are load-bearing and enforced downstream:

1. Point-in-time safety (no leakage). Every record carries an ``as_of`` timestamp.
   A value computed ``as_of = T`` must never depend on input observed after ``T``.
   ``features`` enforces this; ``sandbox`` walk-forward relies on it.

2. Models suggest, rules judge. A model is not privileged — it is a ``Detector`` that
   emits ``Signal``s with ``kind="model"``. A model Signal contributes to a composite
   score but cannot, on its own, push a subject over the escalation threshold. The
   ``score`` layer enforces this "advisory floor". This renders model-risk separation
   generically, without any ML dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping, Protocol, Sequence, runtime_checkable

# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class SignalKind(str, Enum):
    """Provenance of a Signal. The score layer treats ``MODEL`` as advisory-only."""

    RULE = "rule"          # deterministic rule fire, authored and cited
    MODEL = "model"        # calibrated model score; advisory — cannot escalate alone
    INGESTED = "ingested"  # a detection authored by an upstream system we consolidate


class Tier(str, Enum):
    """Priority tier assigned by the rank layer. Ordered most- to least-urgent."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --------------------------------------------------------------------------- #
# Records (data crossing the seams)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Signal:
    """One piece of evidence about one subject, emitted by one Detector.

    ``value`` is source-relative: a rule emits 0/1 or a weight; a model emits a
    calibrated score in [0, 1]. ``evidence`` carries the human-readable "why"
    (the cited rule id, the contributing features, the model version).
    """

    subject_id: str
    source_id: str
    kind: SignalKind
    value: float
    as_of: datetime
    evidence: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureView:
    """A point-in-time snapshot of features for one subject.

    Invariant: no value here was derived from data observed after ``as_of``.
    Features are neutral measures (a count, a peer baseline, a z-score) — they
    carry NO judgement. "≥3σ is suspicious" is a rule's opinion, not a feature.
    """

    subject_id: str
    as_of: datetime
    values: Mapping[str, float] = field(default_factory=dict)

    def get(self, name: str, default: float = 0.0) -> float:
        return self.values.get(name, default)


@dataclass(frozen=True)
class SubjectRecord:
    """All consolidated Signals about one subject for one run.

    Produced by ``consolidate`` (assemble verb). Dedup has already removed
    mechanically-duplicate Signals; genuinely distinct lenses on the same subject
    are KEPT — corroboration compounds, it does not deduplicate.
    """

    subject_id: str
    as_of: datetime
    signals: Sequence[Signal] = field(default_factory=tuple)

    def of_kind(self, kind: SignalKind) -> list[Signal]:
        return [s for s in self.signals if s.kind == kind]

    @property
    def has_rule_signal(self) -> bool:
        return any(s.kind == SignalKind.RULE for s in self.signals)


@dataclass(frozen=True)
class Score:
    """The judged composite for one subject.

    ``advisory_only`` is True when the composite is driven purely by model/ingested
    Signals with no corroborating rule — the advisory floor. The rank layer must not
    assign such a subject to CRITICAL on model evidence alone.
    """

    subject_id: str
    composite: float
    contributions: Mapping[str, float] = field(default_factory=dict)
    advisory_only: bool = False


@dataclass(frozen=True)
class Case:
    """The egress record routed to a case sink — one per surfaced subject."""

    subject_id: str
    score: float
    tier: Tier
    rank: int
    as_of: datetime
    evidence: Mapping[str, object] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Protocols (the swappable seams)
# --------------------------------------------------------------------------- #


@runtime_checkable
class Detector(Protocol):
    """Anything that emits Signals: a rule set, a model, or an ingest adapter.

    The platform is agnostic to which. Plugging in a real XGBoost model means
    writing one ``Detector`` whose ``emit`` returns ``kind="model"`` Signals — the
    architecture does not change. That is the "pluggable" claim, proven structurally.
    """

    detector_id: str

    def emit(
        self, subject_id: str, features: FeatureView, as_of: datetime
    ) -> Sequence[Signal]: ...


@runtime_checkable
class FeatureProvider(Protocol):
    """Computes point-in-time features. Must not leak past ``as_of``."""

    def compute(self, subject_id: str, as_of: datetime) -> FeatureView: ...

    def known_subjects(self, as_of: datetime) -> Sequence[str]:
        """Subjects observable at or before ``as_of`` (the point-in-time roster)."""
        ...


@runtime_checkable
class Judge(Protocol):
    """Combines a subject's Signals into a composite Score (the score/judge verb)."""

    def judge(self, subject: SubjectRecord) -> Score: ...


@runtime_checkable
class Ranker(Protocol):
    """Orders scored subjects and assigns tiers under a capacity constraint."""

    def rank(self, scores: Sequence[Score], as_of: datetime) -> Sequence[Case]: ...


@runtime_checkable
class CaseSink(Protocol):
    """Terminal routing boundary — persists/forwards Cases (one exit point)."""

    def emit(self, case: Case) -> None: ...
