"""Ingest — land & connect.

Normalize heterogeneous upstream inputs into typed :class:`Signal`s. Real systems
read these off a streaming bus; here they are file adapters. The architectural point
is the same: producers are decoupled from the platform by a normalization boundary,
so adding a source means adding an adapter, not editing the platform.

Two adapters ship here — JSONL (upstream detections / model scores) and CSV (a
rules-engine fire export) — to show the platform consolidates signals it did not
author. Add a third source the same way.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from ..core.contracts import Signal, SignalKind


def _parse_ts(raw: str) -> datetime:
    """Accept ISO-8601 with or without a trailing 'Z'."""
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)


def load_jsonl_signals(path: str | Path) -> list[Signal]:
    """Load upstream/ingested detections and model scores from a JSONL file.

    Each line: {subject_id, source_id, kind, value, as_of, evidence?}.
    """
    out: list[Signal] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        out.append(
            Signal(
                subject_id=str(rec["subject_id"]),
                source_id=str(rec["source_id"]),
                kind=SignalKind(rec["kind"]),
                value=float(rec["value"]),
                as_of=_parse_ts(rec["as_of"]),
                evidence=dict(rec.get("evidence", {})),
            )
        )
    return out


def load_csv_rule_fires(path: str | Path) -> list[Signal]:
    """Load a rules-engine fire export (CSV) as ``kind=rule`` Signals.

    Columns: subject_id, rule_id, as_of[, reason]. A fire is value 1.0.
    """
    out: list[Signal] = []
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out.append(
                Signal(
                    subject_id=str(row["subject_id"]),
                    source_id=str(row["rule_id"]),
                    kind=SignalKind.RULE,
                    value=1.0,
                    as_of=_parse_ts(row["as_of"]),
                    evidence={"reason": row.get("reason", "")},
                )
            )
    return out


def normalize(*signal_batches: Iterable[Signal]) -> list[Signal]:
    """Flatten signals from multiple adapters into one normalized stream."""
    out: list[Signal] = []
    for batch in signal_batches:
        out.extend(batch)
    return out
