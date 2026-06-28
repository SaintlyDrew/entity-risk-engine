"""detection_platform — a generic, configurable, leakage-safe detection platform.

Clean-room reference implementation. Signals (rules, models, ingested) flow through a
typed verb-spine: ingest -> consolidate -> features -> score -> rank -> observe.
"""
