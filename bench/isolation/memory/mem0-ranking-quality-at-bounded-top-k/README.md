# Sandbox: mem0-ranking-quality-at-bounded-top-k

**Hypothesis:** Mem0's retrieval ranking correctly surfaces ground-truth memories at recall@5 ≥ 80% when each user has 15 memories (top_k=5 < per-user-corpus, forcing the ranking layer to actually choose).

**Status:** INACTIVE — blocked on Mem0 v2 score-normalization bug (see related).

## Why this is the harder test

The companion sandbox `memory/mem0-library-retrieval-recall` validates retrieval works for the **bounded case** — when each user has ≤ top_k memories, all of them return regardless of ranking quality. That sandbox CONFIRMED at 100% recall@10.

But spec row 9's claim about Mem0 ("91.6 LoCoMo at ~7000 tokens/retrieval") implies a much harder case: thousands of memories per user, retrieval must surface the relevant subset. That requires the ranking layer to actually rank — not just return everything.

## Why this is INACTIVE

Building the bounded sandbox surfaced a Mem0 v2 score-normalization bug:
the most-recently-added memory always reports `score=1.0` regardless of
query relevance. This bug is in Mem0's result-formatting layer (reproduces
across both `faiss` and `chroma` providers), so it would dominate any
ranking-quality measurement on Mem0 v2 — the verdict would be REFUTED
even when the underlying vector search works.

This sandbox stays INACTIVE until either:
- Mem0 upstream fixes the score=1.0 bug (PR pending), OR
- Mem0 v3 ships and resolves it as part of the rewrite

## Workload (planned)

Expand the existing `mem0-retrieval-recall-corpus.jsonl` (8-10 memories per
user) to 15 memories per user, with queries that target specific memories
by way of distinguishing detail. Top_k=5 means retrieval must rank the
5 most relevant out of 15 candidates per query.

## Source

Spec v0.4 row 9. Companion: `memory/mem0-library-retrieval-recall`.
