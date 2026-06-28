# AML — extension placeholder (not yet implemented)

This folder is intentionally a stub. It documents how an **anti-money-laundering** domain
would map onto the platform, without pretending to a runnable instance — AML is a deep
specialty, and a credible instantiation needs real typology expertise, not a sketch.

The point it makes: nothing about the platform is insider- or fraud-specific. A third
domain slots in the same way the first two did.

## How AML would instantiate the platform

- **Subject:** a customer / account (instead of an employee or a card).
- **Ingested signals:** transaction-monitoring rule fires (structuring, rapid movement),
  sanctions/PEP screening hits, SAR/case outcomes from prior investigations.
- **Features (`FeatureProvider`):** point-in-time measures over transaction history —
  e.g. cash-intensity, counterparty fan-out, velocity vs a peer segment, cross-border ratio.
  Same leakage discipline (`as_of`), same leave-one-out peer baseline.
- **Cited rules (`config.json`):** typology thresholds (e.g. structuring just under a
  reporting limit; rapid in-out within N days) — each an auditable, threshold-bearing rule.
- **Model detector:** a typology-scoring model wrapped as a `ModelDetector`, advisory-floored
  exactly as elsewhere — it suggests, the rules judge.
- **Rank / sink:** tiered, capacity-bounded queue routed to a case manager (here, a `CaseSink`).
- **Sandbox:** backtest a candidate typology rule against labeled SARs; A/B before deployment.

## What a real implementation would add

- A `features.py` `FeatureProvider` over transaction data.
- A `config.json` encoding the in-scope typologies as cited rules.
- Sample (synthetic) transaction + outcome data, and a `run.py`.
- Genuine typology review — which is the part that needs a domain specialist, and is why
  this stays a placeholder rather than a guess.

See `examples/insider_risk/` and `examples/payments_fraud/` for the pattern a real AML
instance would follow.
