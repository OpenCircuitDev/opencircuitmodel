# Sandbox: letta-tool-memory

**Hypothesis:** Letta's tool-call-driven memory paradigm produces ≤70% LoCoMo recall on Llama 3.1 8B Q4 — significantly worse than Mem0's library-driven retrieval. Letta's own engineering admits Llama 8B can't reliably drive their tool-calling memory.

**Status:** INACTIVE — Letta packaging on Llama 8B not yet wired.

## Why this matters

This is a **disconfirmation sandbox** — the expected outcome is CONFIRMED (i.e., Letta performs worse on small models), and that confirmation vindicates spec v0.2 row 9's swap from Letta to Mem0. A REFUTED result would be a surprise that warrants revisiting the lock.

Pair with `memory/mem0-v3-locomo` (same workload, library-driven retrieval) for the head-to-head comparison.

## Source for the claim

Letta engineering blog, cited in spec v0.2 rationale for the Letta → Mem0 swap.
