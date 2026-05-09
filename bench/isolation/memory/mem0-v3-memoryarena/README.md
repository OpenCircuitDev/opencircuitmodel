# Sandbox: mem0-v3-memoryarena

**Hypothesis:** Mem0 v3 + Qwen3 8B Q4 hits ≥55% on Stanford MemoryArena's interdependent task suite — between the naive baseline (40-50%) and the LoCoMo ceiling (100% which Stanford showed degrades to 40-60% on real interdependent work).

**Status:** INACTIVE — Stanford workload not yet packaged.

## Why this matters

LoCoMo measures recall ("can the agent retrieve a stated fact?") which is necessary but insufficient. MemoryArena measures whether the agent uses retrieved context to *act correctly across interdependent multi-session tasks*. Stanford's 2026 paper showed agents at near-100% LoCoMo drop to 40-60% on these real-world workloads — a calibration the spec's verification plan cites for honest evaluation.

This sandbox is paired with `mem0-v3-locomo`. Both must run; CONFIRMED on LoCoMo + REFUTED on MemoryArena would still be a useful real-world signal.

## What this does NOT measure

- Single-fact recall (LoCoMo's domain — see sister sandbox)
- Generation quality (orthogonal to memory retrieval)
- Library-driven vs tool-driven memory tradeoffs (compare against `letta-tool-memory` when implemented)

## Source for the claim

Stanford MemoryArena (2026), referenced in spec v0.3 verification revision and `docs/superpowers/research/2026-05-09-decentralized-memory-palace-pattern.md`.
