# Detection Platform

A generic, configurable, **leakage-safe** detection platform — a clean-room reference
implementation of the signal-to-decision pattern behind insider-risk, fraud, and AML
surveillance systems. Pure Python, locally runnable, test-led.

> **Status:** early build. The architecture and contracts are in place; the runnable
> spine is landing component by component. See [Roadmap](#roadmap).

---

## The idea

Detection systems across domains share one shape: **many weak signals about a subject get
assembled, measured, judged, and prioritized into a small number of cases a human can act
on.** This repo implements that shape generically, so a new domain is a *configuration*, not
a rewrite.

```
   ingest   →   consolidate   →   features   →   score   →   rank   →   observe
  (land &       (assemble:        (measure:      (judge:     (prioritize  (audit,
   connect)      signals→one       neutral,       rules +     & route to   metrics,
                 subject)          point-in-time  models →    a case)      drift)
                                   features)      composite)
                       ▲                              ▲
                       │                              │
              models (suggest, advisory) ────────────┘   feeds scores in as signals
              sandbox (validate / backtest) ── replays the whole spine on labeled history
```

Everything crosses a seam as a **typed contract** ([`core/contracts.py`](detection_platform/core/contracts.py)) — read that file first; the rest of the platform is implementations of those interfaces.

## Two design choices worth your attention

1. **Point-in-time safety (no leakage).** Every record carries an `as_of` timestamp; a
   feature computed `as_of = T` can never depend on data observed after `T`. This is the
   failure that silently kills real ML detection systems — so it is enforced in code and is
   the *first* thing the test suite proves.

2. **Models suggest, rules judge.** A model is not privileged — it is just a `Detector` that
   emits advisory signals, and it **cannot escalate a subject on its own**. Plugging in a
   real ML model means writing one adapter; the architecture does not change.

## Production capabilities → generic stand-ins

In production these capabilities are served by heavyweight platforms. Here they are rendered
as minimal Python interfaces so the architecture is **legible and runnable** — the interface
is the contract, the implementation is swappable.

| Capability | Production-class system | Generic stand-in here |
|---|---|---|
| Event ingestion | a streaming broker | file adapters + an in-process event bus |
| Lakehouse / zones | a lakehouse + table format | append-only JSONL (raw) → local serving store |
| Governance / lineage | a catalog / governance plane | a `catalog` registry: schema + version + owner |
| Entity linking | a graph database | an adjacency map with `connected()` / `cluster()` |
| Case management | an enterprise case manager | a `CaseSink` writing rows + JSON case files |
| Model-risk separation | a model-governance standard | the structural "model can't escalate alone" rule |

## Domains (configuration, not code)

- **`examples/insider_risk/`** — the fleshed reference domain (runnable).
- **`examples/payments_fraud/`** — a second runnable domain; wires an in-platform `ModelDetector`
  and is the *executable* proof that the same spine runs unchanged on a different domain
  (`tests/test_genericity.py`).
- **`examples/aml/`** *(planned)* — a thin placeholder showing the extension point.

## Quickstart

```bash
# run a domain end to end (stdlib only — no install needed)
python -m examples.insider_risk.run
python -m examples.payments_fraud.run     # same platform, different config + a model

# run the test suite (leakage-invariant, golden-trace, advisory-floor, consolidation)
pip install -e ".[dev]"   # pytest + dev extras
python -m pytest -q
```

The demo prints a run report and the surfaced case queue, and writes cases to
`examples/insider_risk/out/` (JSONL + SQLite). A new domain is a new folder under
`examples/` with its own config + feature provider — the platform code is untouched.

## Roadmap

- [x] Phase 0 — typed contracts + component skeleton + this README
- [x] Phase 1 — runnable end-to-end spine on the insider domain + golden-trace & leakage tests
- [x] Phase 2 — pluggable `ModelDetector` seam + a second runnable domain (payments) + genericity test
- [ ] Phase 3 — sandbox/backtest harness (precision@K, lift, walk-forward) + drift check
- [ ] Phase 4 — docs (architecture / PRD / test strategy) + quickstart polish

## License

Apache-2.0 — see [LICENSE](LICENSE).
