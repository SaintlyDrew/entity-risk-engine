# Test Strategy

The test suite is not an afterthought here — it is part of the argument. A detection
platform's value rests on guarantees (no leakage, deterministic, models can't escalate
alone), and a guarantee you don't test is a guarantee you don't have. The suite is layered
so each layer maps to a specific failure mode it exists to catch.

## Test layers → failure modes

| Layer | File(s) | Failure mode it guards against |
|---|---|---|
| **Leakage invariant** | `test_leakage_invariant.py` | A feature sees its own future (the silent ML-system killer). Includes a **non-vacuity** test proving the feature *does* respond to in-window data — so the invariant isn't passing trivially. |
| **Golden trace** | `test_golden_trace.py`, `test_genericity.py` | End-to-end behavioural drift. The exact case queue, tiers, scores, and report are locked; any change is made visible and deliberate. Determinism asserted by bit-for-bit replay. |
| **Advisory floor** | `test_advisory_floor.py` | A model escalating on its own. Asserts a model-only subject is capped, and that corroboration lifts the cap. |
| **Consolidation** | `test_consolidate.py` | Losing corroboration (collapsing distinct lenses) or double-counting (keeping mechanical duplicates). Plus idempotency. |
| **Models seam** | `test_models_seam.py` | A broken pluggability claim. Asserts a model *and* a rule detector both satisfy `Detector` (and a bare object does not), calibrated emit, silence below the floor, and feature-contract enforcement. |
| **Genericity** | `test_genericity.py` | The platform secretly being domain-specific. Runs two domains through one spine; locks the second domain's golden; exercises the case-sink egress. |
| **Sandbox** | `test_sandbox.py` | Wrong validation math. Exact precision/recall/lift on synthetic data; divide-by-zero guards; walk-forward point-in-time; A/B regression detection. |
| **Drift** | `test_drift.py` | A drift metric that doesn't fire (or fires on noise). Stable distributions → PSI 0; a real shift → flagged. |

## Principles

- **Test the invariants, not just the happy path.** The leakage and advisory-floor tests
  assert *properties*, not example outputs — they catch a class of bugs, not one bug.
- **Guard the guards.** A test that can pass for the wrong reason is worse than no test. The
  leakage suite explicitly proves it is non-vacuous.
- **Golden traces over assertions-on-shape.** Locking the exact end-to-end result makes every
  behavioural change a conscious decision at review time.
- **Determinism is a feature, so it's tested.** Same inputs → same bytes.

## Running

```bash
pip install -e ".[dev]"
python -m pytest -q          # the whole suite, sub-second
```

## Deliberately not done

No coverage-percentage targets, no mutation testing, no load tests. They are the wrong
signal for a reference implementation whose claim is *correctness of the invariants*, not
exhaustive line coverage. A CI workflow runs the suite on every push.
