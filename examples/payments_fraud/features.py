"""Payments-fraud feature provider.

The second domain. Note what is NOT here: any platform code. This file mirrors the
insider provider's *shape* (point-in-time, leave-one-out peer baseline, neutral
measures) but measures card-transaction behaviour instead of employee access. The
platform spine does not know or care which domain it is running — that is the whole
claim, and `tests/test_genericity.py` proves it executable.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from detection_platform.core.contracts import FeatureView
from detection_platform.features.pointintime import within_window, zscore


@dataclass(frozen=True)
class Txn:
    card_id: str
    ts: datetime
    amount: float


def load_txns(path: str | Path) -> list[Txn]:
    out: list[Txn] = []
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out.append(
                Txn(row["card_id"], datetime.fromisoformat(row["ts"]), float(row["amount"]))
            )
    return out


class PaymentsFeatureProvider:
    """A :class:`~detection_platform.core.contracts.FeatureProvider` for card fraud."""

    WINDOW_DAYS = 1  # a 24h velocity window

    def __init__(self, txns: list[Txn]) -> None:
        self.txns = txns

    def known_subjects(self, as_of: datetime) -> list[str]:
        return sorted({t.card_id for t in self.txns if t.ts <= as_of})

    def _window(self, card_id: str, as_of: datetime) -> list[Txn]:
        rows = [t for t in self.txns if t.card_id == card_id]
        return within_window(rows, as_of, self.WINDOW_DAYS, lambda t: t.ts)

    def compute(self, subject_id: str, as_of: datetime) -> FeatureView:
        window = self._window(subject_id, as_of)
        amount_1d = sum(t.amount for t in window)
        peers = [
            sum(t.amount for t in self._window(c, as_of))
            for c in self.known_subjects(as_of)
            if c != subject_id  # leave-one-out, point-in-time
        ]
        return FeatureView(
            subject_id=subject_id,
            as_of=as_of,
            values={
                "txn_count_1d": float(len(window)),
                "amount_1d": amount_1d,
                "amount_z": round(zscore(amount_1d, peers), 4),
            },
        )
