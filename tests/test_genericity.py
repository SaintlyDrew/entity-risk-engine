"""The genericity claim, made executable.

The platform's central claim is: a new domain is a configuration, not a rewrite. These
tests prove it by running BOTH domains through the *same* ``run_pipeline`` and asserting
each produces a well-formed, deterministic result — with zero domain-specific platform
code. The payments domain additionally exercises an in-platform ``ModelDetector`` and
the ``CaseSink`` egress boundary.
"""

from __future__ import annotations

from detection_platform.core.contracts import Tier
from detection_platform.rank.sink import InMemoryCaseSink
from examples.insider_risk.run import run as run_insider
from examples.payments_fraud.run import run as run_payments

_VALID_TIERS = {t.value for t in Tier}
_SEVERITY = [Tier.CRITICAL, Tier.HIGH, Tier.MEDIUM, Tier.LOW]


def _assert_well_formed(result) -> None:
    """Structural invariants every domain's output must satisfy, whatever the domain."""
    cases = result.cases
    # ranks are 1..n and contiguous
    assert [c.rank for c in cases] == list(range(1, len(cases) + 1))
    # every tier is valid and the queue is ordered most-severe-first
    severities = [_SEVERITY.index(c.tier) for c in cases]
    assert severities == sorted(severities)
    assert all(c.tier.value in _VALID_TIERS for c in cases)
    # the report reconciles with the cases
    rep = result.report
    assert rep.surfaced == len(cases)
    assert rep.scored == rep.surfaced + rep.below_line


def test_both_domains_run_through_the_same_spine() -> None:
    for result in (run_insider(), run_payments()):
        _assert_well_formed(result)
        assert len(result.cases) > 0


# Payments golden — locks the second domain's deterministic output (incl. the
# model-detector advisory case and the velocity rule surfacing a signal-less subject).
EXPECTED_PAYMENTS_QUEUE = [
    (1, "C-201", "high", 65.0),
    (2, "C-203", "medium", 35.0),     # surfaced by the velocity RULE alone (no signal)
    (3, "C-204", "medium", 30.0),
    (4, "C-202", "medium", 27.9608),  # model-only -> advisory-capped to medium
]


def test_payments_golden_trace() -> None:
    result = run_payments()
    actual = [(c.rank, c.subject_id, c.tier.value, c.score) for c in result.cases]
    assert actual == EXPECTED_PAYMENTS_QUEUE
    assert [s.subject_id for s in result.below_line] == ["C-205"]


def test_model_detector_produced_an_advisory_case() -> None:
    """C-202's only evidence is the in-platform model -> it must be advisory-capped."""
    case = next(c for c in run_payments().cases if c.subject_id == "C-202")
    assert case.evidence["advisory_only"] is True
    assert case.tier.value == "medium"


def test_case_sink_egress_is_generic() -> None:
    """The CaseSink boundary works for any domain's cases."""
    sink = InMemoryCaseSink()
    result = run_payments()
    for case in result.cases:
        sink.emit(case)
    assert len(sink.cases) == len(result.cases)
    assert sink.cases[0].subject_id == "C-201"
