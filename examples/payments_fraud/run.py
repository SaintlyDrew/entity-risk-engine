"""Run the payments-fraud domain end to end.

    python -m examples.payments_fraud.run

Identical platform call to the insider domain — the only differences are the config,
the feature provider, the data, and that this domain wires an in-platform
``ModelDetector`` (a calibrated fraud score) alongside its ingested signals. The model
enters the pipeline as just another signal source; the advisory floor governs it.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from arbiter.ingest.adapters import load_jsonl_signals
from arbiter.models.detector import LinearModel, ModelDetector
from arbiter.pipeline import PipelineResult, run_pipeline

from .features import PaymentsFeatureProvider, load_txns

HERE = Path(__file__).parent
DATA = HERE / "data"
DEFAULT_AS_OF = datetime(2026, 3, 1, 12, 0, 0)

# A trivial, dependency-free fraud model. In production this is a trained artifact;
# here a hand-set logistic over two features is enough to exercise the seam.
FRAUD_MODEL = ModelDetector(
    LinearModel(
        model_id="card_fraud_v1",
        version="card_fraud_v1.0",
        coefficients={"amount_z": 1.2, "txn_count_1d": 0.4},
        intercept=-3.0,
    ),
    min_emit=0.5,
)


def run(as_of: datetime = DEFAULT_AS_OF) -> PipelineResult:
    config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    signals = load_jsonl_signals(DATA / "signals.jsonl")
    provider = PaymentsFeatureProvider(load_txns(DATA / "transactions.csv"))
    return run_pipeline(signals, provider, config, as_of, detectors=[FRAUD_MODEL])


def main() -> None:
    result = run()
    print(f"\nRun report (as_of {DEFAULT_AS_OF}):")
    print(json.dumps(result.report.as_dict(), indent=2))
    print("\nSurfaced case queue:")
    print(f"  {'rank':<5}{'subject':<9}{'tier':<10}{'score':<8}{'why'}")
    for case in result.cases:
        flag = " [advisory-capped]" if case.evidence.get("advisory_only") else ""
        contribs = ", ".join(case.evidence["contributions"].keys())
        print(
            f"  {case.rank:<5}{case.subject_id:<9}{case.tier.value:<10}"
            f"{case.score:<8}{contribs}{flag}"
        )
    print(f"\nBelow the line: {[s.subject_id for s in result.below_line]}")


if __name__ == "__main__":
    main()
