"""Backtest the insider-risk config against labeled history.

    python -m examples.insider_risk.backtest

Demonstrates the three sandbox instruments:
1. a single point-in-time backtest (precision@K / recall / lift),
2. a walk-forward across anchors (stability over time, leakage-free), and
3. an A/B comparison — does dropping a rule hurt detection? (the pre-ship gate).
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from arbiter.ingest.adapters import (
    load_csv_rule_fires,
    load_jsonl_signals,
    normalize,
)
from arbiter.pipeline import run_pipeline
from arbiter.sandbox.backtest import compare, evaluate, walk_forward

from .features import InsiderFeatureProvider, load_events

HERE = Path(__file__).parent
DATA = HERE / "data"
K = 4


def _labels() -> dict[str, bool]:
    raw = json.loads((DATA / "labels.json").read_text(encoding="utf-8"))
    return {s: v for s, v in raw.items() if isinstance(v, bool)}


def _cases(config, as_of):
    signals = normalize(
        load_jsonl_signals(DATA / "signals.jsonl"),
        load_csv_rule_fires(DATA / "rule_fires.csv"),
    )
    provider = InsiderFeatureProvider(load_events(DATA / "events.csv"))
    return run_pipeline(signals, provider, config, as_of).cases


def main() -> None:
    config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    labels = _labels()

    print("\n1) Single backtest @ 2026-03-01")
    metrics = evaluate(_cases(config, datetime(2026, 3, 1)), labels, K)
    print(json.dumps(metrics.as_dict(), indent=2))

    print("\n2) Walk-forward (point-in-time anchors)")
    anchors = [datetime(2026, 2, 25), datetime(2026, 2, 28), datetime(2026, 3, 1)]
    wf = walk_forward(lambda a: _cases(config, a), anchors, labels, K)
    print(json.dumps(wf.as_dict(), indent=2))

    print("\n3) A/B: baseline vs. a variant that drops the bulk-export rule")
    degraded = deepcopy(config)
    degraded["feature_rules"] = [
        r for r in degraded["feature_rules"] if r["id"] != "R-EXPORT"
    ]
    cmp = compare(
        _cases(config, datetime(2026, 3, 1)),
        _cases(degraded, datetime(2026, 3, 1)),
        labels,
        K,
    )
    print(f"   baseline precision@{K}:  {cmp.baseline.precision_at_k:.4f}")
    print(f"   candidate precision@{K}: {cmp.candidate.precision_at_k:.4f}")
    print(f"   verdict: {cmp.verdict()}")


if __name__ == "__main__":
    main()
