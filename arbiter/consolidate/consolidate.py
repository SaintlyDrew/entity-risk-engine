"""Consolidate — assemble.

Collapse many Signals into one :class:`SubjectRecord` per subject. The senior
distinction lives here:

* **Dedup** removes a *mechanically duplicate* Signal — the same source reporting the
  same thing twice. That is noise; drop it.
* **Corroboration** keeps *distinct lenses* on the same subject — a rule fire AND a DLP
  hit AND a model score are three independent reasons to look, and they COMPOUND. Never
  collapse them; that is the whole point of consolidation.

Consolidation is idempotent: running it twice yields the same records as running it once.
"""

from __future__ import annotations

from typing import Iterable

from ..core.contracts import Signal, SubjectRecord


def _dedup_key(s: Signal) -> tuple:
    """Identity of a *mechanically duplicate* Signal.

    Same subject, same source, same timestamp, same value => the same observation
    reported twice. Different on any axis => a distinct lens; keep it.
    """
    return (s.subject_id, s.source_id, s.kind, s.as_of, s.value)


def consolidate(signals: Iterable[Signal], as_of) -> list[SubjectRecord]:
    """Group de-duplicated Signals by subject into SubjectRecords.

    Records and their signals are returned in a deterministic order (sorted), so the
    whole pipeline is replayable bit-for-bit.
    """
    seen: set[tuple] = set()
    by_subject: dict[str, list[Signal]] = {}
    for s in signals:
        key = _dedup_key(s)
        if key in seen:
            continue  # mechanical duplicate — dropped
        seen.add(key)
        by_subject.setdefault(s.subject_id, []).append(s)

    records: list[SubjectRecord] = []
    for subject_id in sorted(by_subject):
        sigs = sorted(
            by_subject[subject_id],
            key=lambda s: (s.kind.value, s.source_id, s.as_of, s.value),
        )
        records.append(
            SubjectRecord(subject_id=subject_id, as_of=as_of, signals=tuple(sigs))
        )
    return records
