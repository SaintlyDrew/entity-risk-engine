"""Drift (PSI) tests: stable distributions don't fire; shifted ones do."""

from __future__ import annotations

from arbiter.observe.drift import check_drift, psi


def test_identical_distribution_has_zero_psi() -> None:
    base = [float(i % 10) for i in range(200)]
    assert psi(base, base) == 0.0
    assert check_drift(base, base).drifted is False


def test_constant_feature_cannot_drift() -> None:
    assert psi([5.0] * 50, [9.0] * 50) == 0.0  # no baseline spread -> 0 by definition


def test_shifted_distribution_is_flagged() -> None:
    baseline = [float(i % 10) for i in range(500)]          # spread 0..9
    shifted = [9.0 + (i % 3) for i in range(500)]           # piled at the top
    result = check_drift(baseline, shifted)
    assert result.psi > 0.25
    assert result.drifted is True


def test_small_shift_below_threshold_is_not_flagged() -> None:
    baseline = [float(i % 10) for i in range(1000)]
    nudged = [float(i % 10) for i in range(1000)]
    nudged[:20] = [9.0] * 20  # tiny perturbation
    result = check_drift(baseline, nudged, threshold=0.25)
    assert result.drifted is False
