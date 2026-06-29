"""Insider-risk feature provider.

This is the *domain* half of the seam: the platform supplies the point-in-time
machinery (``arbiter.features.pointintime``); this file decides what to
measure for insider risk. Swapping domains means writing a sibling provider — the
platform does not change.

Features computed (all point-in-time, all leakage-guarded):

* ``after_hours_30d`` — count of after-hours access events in the trailing 30 days.
* ``export_volume_30d`` — total records exported in the trailing 30 days.
* ``peer_z_after_hours`` — how many standard deviations a subject's after-hours
  activity sits above their **peers** (leave-one-out: a subject is never part of their
  own baseline — you can't be an outlier against yourself).

Note the discipline: features are *neutral measures*. "2 sigma is suspicious" is not
encoded here — that judgement is a cited rule in the config the score layer reads.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from arbiter.core.contracts import FeatureView
from arbiter.features.pointintime import within_window, zscore


@dataclass(frozen=True)
class Event:
    subject_id: str
    event_type: str
    ts: datetime
    magnitude: float


def load_events(path: str | Path) -> list[Event]:
    out: list[Event] = []
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out.append(
                Event(
                    subject_id=row["subject_id"],
                    event_type=row["event_type"],
                    ts=datetime.fromisoformat(row["ts"]),
                    magnitude=float(row["magnitude"]),
                )
            )
    return out


class InsiderFeatureProvider:
    """A :class:`~arbiter.core.contracts.FeatureProvider` for insider risk."""

    WINDOW_DAYS = 30

    def __init__(self, events: list[Event]) -> None:
        self.events = events
        self.subjects = sorted({e.subject_id for e in events})

    def _after_hours_30d(self, subject_id: str, as_of: datetime) -> int:
        rows = [
            e
            for e in self.events
            if e.subject_id == subject_id and e.event_type == "after_hours_access"
        ]
        return len(within_window(rows, as_of, self.WINDOW_DAYS, lambda e: e.ts))

    def _export_volume_30d(self, subject_id: str, as_of: datetime) -> float:
        rows = [
            e
            for e in self.events
            if e.subject_id == subject_id and e.event_type == "export"
        ]
        return sum(
            e.magnitude
            for e in within_window(rows, as_of, self.WINDOW_DAYS, lambda e: e.ts)
        )

    def known_subjects(self, as_of: datetime) -> list[str]:
        """Subjects observable at or before ``as_of``.

        A peer baseline must not include employees whose only activity lies in the
        future — that would leak tomorrow's roster into today's z-score.
        """
        return sorted({e.subject_id for e in self.events if e.ts <= as_of})

    def compute(self, subject_id: str, as_of: datetime) -> FeatureView:
        own = self._after_hours_30d(subject_id, as_of)
        peers = [
            self._after_hours_30d(s, as_of)
            for s in self.known_subjects(as_of)
            if s != subject_id  # leave-one-out, point-in-time peer baseline
        ]
        return FeatureView(
            subject_id=subject_id,
            as_of=as_of,
            values={
                "after_hours_30d": float(own),
                "export_volume_30d": self._export_volume_30d(subject_id, as_of),
                "peer_z_after_hours": round(zscore(float(own), peers), 4),
            },
        )
