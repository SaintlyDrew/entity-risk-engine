"""Run the insider-risk domain end to end.

    python -m examples.insider_risk.run

Loads the config + sample data, walks the platform spine, prints the run report and
the surfaced case queue, and writes the cases to JSONL + SQLite under ``out/``.

The ``run`` function is the single wiring point; tests import it so the demo and the
golden-trace test exercise the exact same path.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from arbiter.ingest.adapters import (
    load_csv_rule_fires,
    load_jsonl_signals,
    normalize,
)
from arbiter.pipeline import PipelineResult, run_pipeline
from arbiter.rank.sink import JsonlCaseSink, SqliteCaseSink

from .features import InsiderFeatureProvider, load_events

HERE = Path(__file__).parent
DATA = HERE / "data"
DEFAULT_AS_OF = datetime(2026, 3, 1)


def run(as_of: datetime = DEFAULT_AS_OF) -> PipelineResult:
    config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    signals = normalize(
        load_jsonl_signals(DATA / "signals.jsonl"),
        load_csv_rule_fires(DATA / "rule_fires.csv"),
    )
    provider = InsiderFeatureProvider(load_events(DATA / "events.csv"))
    return run_pipeline(signals, provider, config, as_of)


def main() -> None:
    result = run()
    print(f"\nRun report (as_of {DEFAULT_AS_OF.date()}):")
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

    print(f"\nBelow the line (held, not dropped): "
          f"{[s.subject_id for s in result.below_line]}")

    out = HERE / "out"
    jsonl = JsonlCaseSink(out / "cases.jsonl")
    sqlite = SqliteCaseSink(out / "cases.sqlite")
    for case in result.cases:
        jsonl.emit(case)
        sqlite.emit(case)
    sqlite.close()
    print(f"\nCases written to {out}/cases.jsonl and out/cases.sqlite")


if __name__ == "__main__":
    main()
