"""Models — suggest (advisory).

A model is not privileged in this platform. It is a :class:`~arbiter.core
.contracts.Detector` that emits ``kind="model"`` Signals from features — exactly like a
rule, except its output is a calibrated probability rather than a 0/1. Plugging in a
real model (XGBoost, a torch net, a vendor score) means writing one ``ModelDetector``
around it; nothing else in the platform changes. That is the pluggability claim, made
provable by structure.

``LinearModel`` is a deliberately trivial, dependency-free scorer (a logistic over named
features). The point is the *seam*, not the algorithm — swap in any object with a
``score(FeatureView) -> float`` and the same wrapper carries it.

Two maturity behaviours are structural:

* **Feature contract.** The model declares the features it consumes and validates they
  are present at scoring time — the generic form of train/serve parity (a model must
  see the same inputs in production as in training, or it is silently wrong).
* **Calibrated, provenance-stamped output.** The emitted Signal carries the model
  version and the exact feature values it scored, so any alert is explainable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Sequence

from ..core.contracts import FeatureView, Signal, SignalKind


class FeatureContractError(ValueError):
    """Raised when a model is asked to score without a feature it declared it needs."""


@dataclass(frozen=True)
class LinearModel:
    """A logistic scorer over named features. Output is calibrated to [0, 1]."""

    model_id: str
    version: str
    coefficients: Mapping[str, float]
    intercept: float = 0.0

    @property
    def required_features(self) -> tuple[str, ...]:
        return tuple(self.coefficients)

    def score(self, features: FeatureView) -> float:
        missing = [f for f in self.required_features if f not in features.values]
        if missing:
            raise FeatureContractError(
                f"{self.model_id} requires {missing} but the FeatureView for "
                f"{features.subject_id} does not provide them"
            )
        z = self.intercept + sum(
            w * features.get(f) for f, w in self.coefficients.items()
        )
        return 1.0 / (1.0 + math.exp(-z))


@dataclass(frozen=True)
class ModelDetector:
    """Wrap a model as a Detector. Emits a calibrated, advisory Signal per subject.

    ``min_emit`` is the calibration floor: below it the model stays silent rather than
    contributing noise (a model that fires on everyone is a model that says nothing).
    """

    model: LinearModel
    min_emit: float = 0.5

    @property
    def detector_id(self) -> str:
        return f"model.{self.model.model_id}"

    def emit(
        self, subject_id: str, features: FeatureView, as_of: datetime
    ) -> Sequence[Signal]:
        score = self.model.score(features)
        if score < self.min_emit:
            return ()
        return (
            Signal(
                subject_id=subject_id,
                source_id=self.detector_id,
                kind=SignalKind.MODEL,
                value=round(score, 4),
                as_of=as_of,
                evidence={
                    "model_version": self.model.version,
                    "features": {
                        f: features.get(f) for f in self.model.required_features
                    },
                },
            ),
        )
