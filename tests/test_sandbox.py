"""Sandbox / backtest tests.

Cover the metric math directly (synthetic cases, exact values) and the three
instruments end to end on the insider domain: single backtest, walk-forward stability,
and the A/B pre-ship gate (dropping a rule must be detected as a regression).
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import examples.insider_risk.run as _insider_run
from arbiter.core.contracts import Case, Tier
from arbiter.sandbox.backtest import compare, evaluate, walk_forward
from examples.insider_risk.backtest import _cases
from examples.insider_risk.run import run as run_insider

AS_OF = datetime(2026, 3, 1)
LABELS = {"E-101": True, "E-103": True, "E-106": True,
          "E-102": False, "E-104": False, "E-105": False}
CONFIG_PATH = Path(_insider_run.__file__).parent / "config.json"


def _config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _case(subject: str, score: float, rank: int) -> Case:
    return Case(subject, score, Tier.HIGH, rank, AS_OF)


def test_evaluate_metric_math() -> None:
    cases = [_case("S1", 90, 1), _case("S2", 50, 2), _case("S3", 30, 3)]
    labels = {"S1": True, "S2": False, "S3": True, "S4": False}  # 2 of 4 positive
    m = evaluate(cases, labels, k=2)
    assert m.true_positives_surfaced == 1   # only S1 in the top 2
    assert m.precision_at_k == 0.5
    assert m.recall_at_k == 0.5             # 1 of 2 positives
    assert m.base_rate == 0.5
    assert m.lift_at_k == 1.0


def test_evaluate_handles_empty_and_no_positives() -> None:
    assert evaluate([], LABELS, k=4).precision_at_k == 0.0
    no_pos = {"X": False, "Y": False}
    m = evaluate([_case("X", 10, 1)], no_pos, k=4)
    assert m.recall_at_k == 0.0 and m.lift_at_k == 0.0  # no divide-by-zero


def test_insider_single_backtest() -> None:
    m = evaluate(run_insider(AS_OF).cases, LABELS, k=4)
    assert m.precision_at_k == 0.75   # 3 of the top 4 are real
    assert m.recall_at_k == 1.0       # all 3 true positives surfaced
    assert m.lift_at_k == 1.5         # 1.5x better than the 0.5 base rate


def test_walk_forward_is_point_in_time() -> None:
    config = _config()
    anchors = [datetime(2026, 2, 28), AS_OF]
    wf = walk_forward(lambda a: _cases(config, a), anchors, LABELS, k=4)
    assert len(wf.per_anchor) == 2
    assert 0.0 <= wf.mean_precision_at_k <= 1.0
    assert wf.per_anchor[-1][1].precision_at_k == 0.75  # final anchor == single backtest


def test_ab_comparison_detects_a_regression() -> None:
    config = _config()
    degraded = deepcopy(config)
    degraded["feature_rules"] = [
        r for r in degraded["feature_rules"] if r["id"] != "R-EXPORT"
    ]
    cmp = compare(_cases(config, AS_OF), _cases(degraded, AS_OF), LABELS, k=4)
    assert cmp.precision_delta < 0          # dropping the rule hurts
    assert "REGRESSES" in cmp.verdict()
