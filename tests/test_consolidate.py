"""Consolidate invariants: idempotency, dedup vs corroboration.

These assert the two behaviours the ``consolidate`` docstring promises — they are the
executable version of the design's "dedup removes mechanical duplicates; corroboration
keeps distinct lenses" claim.
"""

from __future__ import annotations

from datetime import datetime

from arbiter.consolidate.consolidate import consolidate
from arbiter.core.contracts import Signal, SignalKind

AS_OF = datetime(2026, 3, 1)


def _sig(subject, source, kind=SignalKind.RULE, value=1.0, ts=AS_OF) -> Signal:
    return Signal(subject, source, kind, value, ts)


def test_consolidation_is_idempotent() -> None:
    signals = [_sig("E-1", "r.a"), _sig("E-1", "r.b"), _sig("E-2", "r.a")]
    once = consolidate(signals, AS_OF)
    twice = consolidate(
        [s for rec in once for s in rec.signals], AS_OF
    )
    assert once == twice


def test_mechanical_duplicate_is_dropped() -> None:
    dup = _sig("E-1", "r.a")
    [record] = consolidate([dup, dup], AS_OF)
    assert len(record.signals) == 1


def test_distinct_lenses_are_kept_and_compound() -> None:
    """Same subject, different sources/kinds = corroboration. Keep them all."""
    signals = [
        _sig("E-1", "rule.snoop", SignalKind.RULE),
        _sig("E-1", "dlp.email", SignalKind.INGESTED),
        _sig("E-1", "model.exfil", SignalKind.MODEL, value=0.7),
    ]
    [record] = consolidate(signals, AS_OF)
    assert len(record.signals) == 3
    assert record.has_rule_signal
    assert len(record.of_kind(SignalKind.MODEL)) == 1
