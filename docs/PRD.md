# Product Requirements — Arbiter (Entity Risk Scoring Engine, reference)

> A product framing for a reference system. It states the problem, the users, and the
> capability set the architecture delivers — the "why" behind the code.

## Problem

Organizations run many independent detectors — rule engines, data-loss/policy systems,
ML models, watchlists — each emitting alerts in its own format, on its own subjects, with
its own notion of severity. Investigators drown: too many alerts, no shared priority, no
way to tell corroborated risk from a single noisy fire. Meanwhile the detectors themselves
decay (drift) and are changed without anyone proving the change helped.

## Goal

A single platform that **consolidates** signals across detectors, **enriches** them with
point-in-time features, **judges** them under governed rules, **prioritizes** them under
finite analyst capacity, and provides a **sandbox** to validate any detector change before
it ships — generic across detection domains.

## Users

| Persona | Need the platform serves |
|---|---|
| **Analyst** | A ranked, capacity-bounded queue of cases, each explaining *why* it surfaced. |
| **Detection engineer** | Add a rule or model as a config/adapter change; validate it in the sandbox before prod. |
| **Data scientist** | Plug a model in behind one interface; trust point-in-time feature parity. |
| **Risk / governance** | Assurance that models can't escalate alone, that runs are auditable and deterministic, and that drift is monitored. |

## Capabilities

1. **Multi-source consolidation** — heterogeneous detectors normalized to one signal model;
   dedup vs corroboration handled correctly.
2. **Point-in-time feature store** — neutral, reusable measures shared by rules and models,
   leakage-safe.
3. **Governed scoring** — cited, threshold-bearing rules + weighted signals → composite, with
   an advisory floor on model-only evidence.
4. **Capacity-aware prioritization** — tiered, most-severe-first, bounded queue; nothing
   dropped silently (below-the-line is held and auditable).
5. **Pluggable models** — a model is a `Detector`; swapping in a real one is one adapter.
6. **Validation sandbox** — precision@K / lift backtests, leakage-free walk-forward, and A/B
   comparison as a pre-ship gate.
7. **Observability** — per-run audit report + feature-drift (PSI) monitoring.

## Domain instantiation model

A new domain (insider risk, payments fraud, AML, ...) is delivered as a `FeatureProvider`
+ a `config.json` + optional detectors + sample data — **no platform code changes**. Two
domains ship as worked examples; the genericity test proves the claim.

## Success metrics (how you'd judge a real deployment)

- **Detection quality:** precision@K and lift over base rate, tracked via the sandbox.
- **Analyst efficiency:** fraction of worked cases that are true positives (precision of the
  surfaced queue).
- **Change safety:** every rule/model change has a sandbox A/B showing non-regression before
  deployment.
- **Integrity:** deterministic re-runs; zero point-in-time leakage; drift surfaced before it
  degrades output.

## Scope & phasing

Built (this repo): the generic spine, the models seam, the sandbox, two domains, the test
suite, CI. **Out of scope** for the reference: streaming infrastructure, an ML training
stack, a case-management UI, and production governance machinery — named in
[ARCHITECTURE.md](ARCHITECTURE.md) as the production counterparts of the interfaces here.

## Open questions (a real deployment would resolve)

- Label latency: confirmed-case outcomes lag, so backtest labels are always partially stale —
  how is the evaluation windowed?
- Capacity calibration: is the queue bound a fixed headcount or a dynamic SLA?
- Feedback loop: do investigator dispositions feed back into rule/model tuning, and how is
  that loop kept from gaming itself?
