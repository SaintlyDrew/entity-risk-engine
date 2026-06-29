# Architecture

Arbiter turns **many weak signals about a subject** into **a small, ranked
set of cases a human can act on** — and does it the same way across domains (insider risk,
payments fraud, AML, abuse). This document explains how the pieces fit and *why* the
boundaries are where they are.

## The verb-spine

Each component owns one verb. The spine is the architecture; everything else is detail.

| Component | Verb | Responsibility |
|---|---|---|
| `ingest` | **land & connect** | Normalize heterogeneous inputs (rule fires, policy hits, model scores) into typed `Signal`s. Adding a source = adding an adapter. |
| `consolidate` | **assemble** | Collapse many signals about one subject into one `SubjectRecord`. Dedup mechanical duplicates; **keep** distinct lenses (they corroborate). |
| `features` | **measure** | Compute neutral, reusable, point-in-time features, read by *both* rules and models. |
| `score` | **judge** | Combine signals + cited feature-rules into a governed composite. Enforce the advisory floor. |
| `rank` | **prioritize & route** | Tier, order most-severe-first, bound by analyst capacity, route to a case sink. |
| `observe` | **observe** | Audit the run; flag feature drift. |
| `models` | **suggest** | A pluggable `Detector` emitting calibrated, advisory signals — one signal source among many. |
| `sandbox` | **validate** | Replay labeled history through a candidate config and measure detection quality before it ships. |

```
ingest → consolidate → features → score → rank → observe
                            ▲          ▲
        models (suggest) ───┘──────────┘   feeds signals into the judge
        sandbox (validate) ── replays the whole spine on labeled history
```

## The contracts are the spine

Everything crosses a seam as a typed record defined in [`core/contracts.py`](../arbiter/core/contracts.py):
`Signal`, `FeatureView`, `SubjectRecord`, `Score`, `Case`, plus the `Detector`,
`FeatureProvider`, `Judge`, `Ranker`, and `CaseSink` protocols. A new implementation of
any seam (a graph-backed feature store, a real ML model, an enterprise case manager) is a
new class satisfying a protocol — the orchestrator never changes.

## Two load-bearing invariants

1. **Point-in-time safety (no leakage).** Every record carries an `as_of`. A value computed
   `as_of = T` never depends on data observed after `T` — enforced at one chokepoint
   (`features/pointintime.py`) and extended to ingested signals (filtered by `as_of` in the
   pipeline) and to the peer baseline (the roster is point-in-time). This is the failure that
   silently destroys real ML detection systems; here it is enforced and tested first.

2. **Models suggest, rules judge.** A model is a `Detector` emitting `kind="model"` signals;
   it contributes to a composite but **cannot escalate a subject on its own** (the advisory
   floor, enforced in both `score` and `rank`). This is model-risk separation rendered
   generically — no specific regulation, just the structural control.

## Why `score` and `rank` are separate

*What* is risky (a judgement, with cited rules and thresholds) and *what gets worked first
under finite capacity* (a prioritization) are different decisions with different owners.
Collapsing them is the most common boundary error in detection systems. Keeping them apart
is what lets the advisory floor cap a *tier* while the capacity constraint shapes the *queue*.

## Production capabilities → generic stand-ins

The platform replaces heavyweight infrastructure with minimal Python interfaces so the
architecture is legible and runnable. The interface is the contract; the implementation is
swappable.

| Capability | Production-class system | Stand-in here |
|---|---|---|
| Event ingestion | streaming broker | file adapters + (extensible to) an event bus |
| Lakehouse / zones | lakehouse + table format | append-only files → serving store |
| Governance / lineage | catalog / governance plane | typed contracts + provenance on every record |
| Entity linking | graph database | (extension point) adjacency + clustering |
| Case management | enterprise case manager | `CaseSink` (in-memory / JSONL / SQLite) |
| Model-risk separation | model-governance standard | the structural "model can't escalate alone" |

## Determinism & auditability

The pipeline is deterministic: same inputs + same config → bit-identical output (the
golden-trace test asserts it). Every case carries its contributions and provenance, and the
run report reconciles surfaced + below-the-line counts. A reviewer can ask "re-run it; same
answer?" and the platform answers in code.

## Extending to a new domain

A domain is a **configuration**, not a fork:
1. Write a `FeatureProvider` (what to measure) over your data.
2. Write a `config.json` (signal weights, cited feature-rules + thresholds, tiers, capacity,
   advisory cap).
3. Optionally wire a `ModelDetector`.
4. Call `run_pipeline(signals, provider, config, as_of, detectors=...)`.

`examples/insider_risk` and `examples/payments_fraud` are two such instantiations of the
*same* platform code. `tests/test_genericity.py` proves it.

## Deliberately out of scope

A reference implementation, not a product: no streaming infra, no ML training stack, no
governance machinery, no UI. Those are named here as the production counterparts of the
interfaces — the point is to show the *shape* of the system, runnably, not to rebuild it.
