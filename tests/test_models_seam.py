"""The models seam: a model is just a Detector.

These tests prove the pluggability claim structurally — a ``ModelDetector`` satisfies
the same ``Detector`` protocol a rule-based detector would, emits a calibrated advisory
signal, stays silent below its calibration floor, and validates its feature contract.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from detection_platform.core.contracts import Detector, FeatureView, SignalKind
from detection_platform.models.detector import (
    FeatureContractError,
    LinearModel,
    ModelDetector,
)

AS_OF = datetime(2026, 3, 1)
MODEL = ModelDetector(
    LinearModel("m", "m.v1", {"amount_z": 1.2, "txn_count_1d": 0.4}, intercept=-3.0),
    min_emit=0.5,
)


class _RuleDetector:
    """A trivial non-model Detector — proves the protocol is not model-specific."""

    detector_id = "rule.demo"

    def emit(self, subject_id, features, as_of):
        return ()


def test_model_and_rule_detectors_both_satisfy_the_protocol() -> None:
    assert isinstance(MODEL, Detector)
    assert isinstance(_RuleDetector(), Detector)
    # non-vacuous: an object lacking emit/detector_id is NOT a Detector
    assert not isinstance(object(), Detector)


def test_model_emits_calibrated_signal_above_floor() -> None:
    fv = FeatureView("C-1", AS_OF, {"amount_z": 7.0, "txn_count_1d": 1.0})
    [sig] = MODEL.emit("C-1", fv, AS_OF)
    assert sig.kind == SignalKind.MODEL
    assert 0.0 <= sig.value <= 1.0 and sig.value > 0.5
    assert sig.evidence["model_version"] == "m.v1"
    assert set(sig.evidence["features"]) == {"amount_z", "txn_count_1d"}


def test_model_is_silent_below_floor() -> None:
    fv = FeatureView("C-2", AS_OF, {"amount_z": -1.0, "txn_count_1d": 0.0})
    assert MODEL.emit("C-2", fv, AS_OF) == ()


def test_feature_contract_is_enforced() -> None:
    """A model asked to score without a feature it declared must fail loudly, not
    silently treat the missing input as zero (that is how serving skew hides)."""
    fv = FeatureView("C-3", AS_OF, {"txn_count_1d": 3.0})  # amount_z absent
    with pytest.raises(FeatureContractError):
        MODEL.emit("C-3", fv, AS_OF)
