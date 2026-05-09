# Sandbox H: fp8 Activation Transfer

**Hypothesis:** fp8 activation transfer between sharded inference layers preserves ≥99% of fp16 output quality at half the wire bandwidth.

**Status:** INACTIVE — v6 sharded inference not yet implemented; this gates the v6 rollout.

## Why this is a gate

Spec v0.4 row 28 explicitly conditions the v6 fp8-default decision on Sandbox H: "Activation transfer (v6+ sharded inference): fp8 default with fp16 fallback, gated by Sandbox H confirmation." If H REFUTES on quality, fp8 is too lossy and v6 falls back to fp16 (with no bandwidth savings). If H REFUTES on bandwidth, the v6 economics story is overpromising.

## Source

Spec v0.4 row 28 + research note `docs/superpowers/research/2026-05-09-encryption-compression-optimizations.md`.
