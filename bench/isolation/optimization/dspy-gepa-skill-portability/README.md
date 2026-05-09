# Sandbox: dspy-gepa-skill-portability

**Hypothesis:** A DSPy GEPA-compiled program saved on Node A and loaded on Node B preserves ≥95% accuracy. This is the structural foundation for OCM's v2+ skill-federation network-effect lever per spec v0.3 row 23.

**Status:** INACTIVE — DSPy GEPA not yet integrated; two-node harness presumes Phase 7+ mesh transport.

## Why this matters

Spec v0.3 upgraded GEPA from "opt-in extension" to **"v2+ network-effect lever."** The structural claim is: compiled DSPy programs are deterministic, redistributable artifacts that improve every contributor's agent layer with zero user-data privacy surface. **This sandbox tests whether that's actually true** — does a GEPA-compiled skill survive the trip from one node to another?

If CONFIRMED, signed skill artifacts shipped over the OCM mesh become a real federation primitive. If REFUTED, GEPA programs are too model-specific and federation-as-skill-sharing falls apart — OCM would need a different network-effect strategy.

## What this does NOT measure

- The signing / verification path itself (separate sandbox planned)
- Performance on Mem0-mediated context (orthogonal)
- Mesh-transport latency (presumes mesh works; that's `mesh-transport/multipass-fleet`)

## Source for the claim

DSPy GEPA paper (+10pp AIME, +17pp entity extraction baseline numbers) + DSPy program.save()/load() public API. Spec v0.3 row 23 + research note `2026-05-09-decentralized-memory-palace-pattern.md`.
