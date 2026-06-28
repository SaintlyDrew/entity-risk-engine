"""The flagship test: point-in-time safety (no leakage).

A feature computed ``as_of = T`` must be identical whether or not events dated after
``T`` exist in the data. This is the failure that silently destroys real detection /
ML systems — a model that "knows the future" looks brilliant in backtest and fails in
production. We prove the guard holds, and (crucially) we prove the test is NOT vacuous
by showing an in-window event *does* move the feature.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from examples.insider_risk.features import Event, InsiderFeatureProvider

AS_OF = datetime(2026, 3, 1)


def _base_events() -> list[Event]:
    return [
        Event("E-1", "after_hours_access", datetime(2026, 2, 10, 22), 1),
        Event("E-1", "after_hours_access", datetime(2026, 2, 20, 23), 1),
        Event("E-1", "export", datetime(2026, 2, 15, 12), 200),
        Event("E-2", "after_hours_access", datetime(2026, 2, 11, 22), 1),
    ]


@pytest.mark.parametrize(
    "poison",
    [
        Event("E-1", "after_hours_access", datetime(2026, 4, 1, 22), 1),
        Event("E-1", "after_hours_access", datetime(2099, 1, 1, 22), 1),
        Event("E-1", "export", datetime(2026, 3, 2, 12), 9999),
        # A future event for an existing PEER must not move E-1's peer z-score...
        Event("E-2", "after_hours_access", datetime(2026, 4, 1, 22), 1),
        # ...and a future-only NEW subject must not enter the peer baseline at all
        # (this is the subtle population-membership leak the leave-one-out fix closes).
        Event("E-NEW", "after_hours_access", datetime(2030, 1, 1, 22), 5),
    ],
)
def test_future_events_do_not_change_as_of_features(poison: Event) -> None:
    """Injecting any post-``as_of`` event leaves the as_of FeatureView unchanged.

    Covers three leakage surfaces: the subject's own future activity, a peer's future
    activity, and a future-only employee leaking into the peer population.
    """
    baseline = InsiderFeatureProvider(_base_events()).compute("E-1", AS_OF)
    poisoned = InsiderFeatureProvider(_base_events() + [poison]).compute("E-1", AS_OF)
    assert poisoned.values == baseline.values


def test_invariant_is_not_vacuous() -> None:
    """Sanity: an event BEFORE as_of DOES move the feature.

    Without this, the leakage test could pass simply because the feature never
    responds to anything. This guards the guard.
    """
    baseline = InsiderFeatureProvider(_base_events()).compute("E-1", AS_OF)
    in_window = Event("E-1", "after_hours_access", datetime(2026, 2, 25, 22), 1)
    moved = InsiderFeatureProvider(_base_events() + [in_window]).compute("E-1", AS_OF)
    assert moved.values["after_hours_30d"] == baseline.values["after_hours_30d"] + 1
