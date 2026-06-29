"""Arbiter — the Entity Risk Scoring Engine.

A generic, leakage-safe engine that fuses signals from many detectors into one
explainable, prioritized risk score per entity. Clean-room reference implementation.
Signals (rules, models, ingested) flow through a typed verb-spine:
ingest -> consolidate -> features -> score -> rank -> observe.
"""
