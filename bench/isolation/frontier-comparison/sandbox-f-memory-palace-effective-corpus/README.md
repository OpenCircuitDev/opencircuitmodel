# Sandbox F: Memory Palace Effective-Corpus

**Hypothesis:** OCM's full memory stack (Mem0 + Memory Palace at 5 GB scale) hits ≥92% on long-horizon QA at ≤8 000 tokens/query — comparable to or better than a frontier 1M-token-context model paying 200× more tokens per query.

**Status:** INACTIVE — Memory Palace federation (v3.5+) not yet implemented; this is the v0.4 spec's load-bearing future measurement.

## Why this is the most consequential sandbox

Spec v0.4 row 27 locks the **Effective-Context Triad** (Expansion / Stratification / Quick Look-Up) as a cross-cutting design constraint. Sandbox F is its empirical test. If CONFIRMED, OCM's pitch holds: knowledge axis (palace) + retrieval axis (Mem0) compounds to beat raw context-window expansion at fraction of the per-query cost. If REFUTED, the triad needs revising.

## Comparison anchor

Frontier 1M-token-context model (Gemini 1.5 Pro 1M, Claude 3.5 Sonnet 200K, or GPT-4 Turbo 128K with full corpus stuffed). Same 50-prompt suite, full corpus dropped into the prompt. Expected: ~92-98% accuracy at ~200K-1M tokens/query. OCM target: ~92% at ≤8K tokens/query.

## What CONFIRMED unlocks

- Spec row 26 (Memory Palace federation) gets locked as a network-effect lever
- The "Effective-Context > Single-Window" pitch moves from speculation to evidence
- v3.5+ palace work has clear ROI

## What REFUTED unlocks

- Either the palace design needs different chunking / signing / sub-context retrieval
- Or the retrieval policy (Mem0's library-driven approach) needs tuning
- Or the triad isn't actually load-bearing and v0.4 row 27 needs softening

## Source

- Spec v0.4 row 27 + 26
- Research note `docs/superpowers/research/2026-05-09-effective-context-triad-expansion-stratification-lookup.md`
- Research note `docs/superpowers/research/2026-05-09-decentralized-memory-palace-pattern.md`
