# Sandbox: cognee-8b-graph-quality

**Hypothesis:** Cognee's graph builder on Llama 3.1 8B Q4 hallucinates ≥80% of graph nodes — confirming Cognee's own docs that 32B-70B models are required for stable construction.

**Status:** INACTIVE — Cognee not in OCM v1 (deliberately, per spec); workload not packaged.

## Why this matters

This is a **disconfirmation sandbox**. Cognee is a popular memory + knowledge-graph framework that initially looked attractive for OCM, but its own docs disqualify it for the small-model default tier. This sandbox documents the limit empirically so future contributors don't relitigate the decision.

CONFIRMED is the expected outcome — it vindicates the v0.4 spec decision to NOT ship Cognee. REFUTED would surprise — Cognee on 8B works better than its own docs claim.

## Source for the claim

Cognee documentation explicit recommendation of deepseek-r1:32b or Llama 3.3 70B. Research note `2026-05-09-decentralized-memory-palace-pattern.md` summarizes the limit.
