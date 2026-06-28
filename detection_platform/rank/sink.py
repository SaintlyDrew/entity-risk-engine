"""Case sinks — the single routing boundary out of the platform.

A surfaced subject becomes exactly one Case, written to a sink. In production this is
an enterprise case manager; here the sink is a swappable interface with three
implementations (in-memory for tests, JSONL, SQLite). The boundary is the point — one
exit, typed, auditable — not the storage technology.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from ..core.contracts import Case


def _row(case: Case) -> dict:
    return {
        "subject_id": case.subject_id,
        "score": case.score,
        "tier": case.tier.value,
        "rank": case.rank,
        "as_of": case.as_of.isoformat(),
        "evidence": dict(case.evidence),
    }


@dataclass
class InMemoryCaseSink:
    """Collects Cases in a list. The default for tests and dry runs."""

    cases: list[Case] = field(default_factory=list)

    def emit(self, case: Case) -> None:
        self.cases.append(case)


@dataclass
class JsonlCaseSink:
    """Appends one JSON object per Case to a ``.jsonl`` file."""

    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")  # truncate per run

    def emit(self, case: Case) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_row(case), sort_keys=True) + "\n")


@dataclass
class SqliteCaseSink:
    """Writes Cases to a ``cases`` table in a SQLite database."""

    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute("DROP TABLE IF EXISTS cases")  # truncate per run (match JSONL)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS cases (
                   subject_id TEXT, score REAL, tier TEXT,
                   rank INTEGER, as_of TEXT, evidence TEXT
               )"""
        )
        self._conn.commit()

    def emit(self, case: Case) -> None:
        r = _row(case)
        self._conn.execute(
            "INSERT INTO cases VALUES (?,?,?,?,?,?)",
            (
                r["subject_id"],
                r["score"],
                r["tier"],
                r["rank"],
                r["as_of"],
                json.dumps(r["evidence"], sort_keys=True),
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
