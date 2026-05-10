# Sandbox: mem0-library-retrieval-recall

**Hypothesis:** Mem0's library-driven retrieval (search) returns ALL ground-truth memory IDs in the top-10 for ≥95% of queries on a 39-memory / 39-query synthetic workload, with **0% cross-user-id leakage**.

**Status:** ACTIVE — first ACTIVE memory-category sandbox.

## What this measures

- **Primary**: recall@10 — fraction of queries where every expected memory_id appears in the top-10 retrieved set
- **Secondary**: cross-user-id leak rate — fraction of queries where retrieval returned a memory belonging to a DIFFERENT user_id (must be 0.0 — Mem0's user_id isolation is a security boundary)

## What this does NOT measure

- **Mem0's LLM-driven memory extraction** (the `add(infer=True)` path that uses an LLM to digest raw conversation into atomic memories). This sandbox bypasses extraction by passing pre-formatted memories with `infer=False`.
- **The full LoCoMo benchmark** — that's a separate sandbox at `memory/mem0-v3-locomo` (still INACTIVE pending real Mem0 v3 + the LoCoMo dataset). LoCoMo is multi-session interdependent reasoning; this sandbox is single-fact retrieval recall.
- **Embedding model quality in absolute terms** — uses `all-MiniLM-L6-v2` (small, fast, no API key). Larger embedding models (e5, BGE, OpenAI text-embedding-3) would likely score higher; but this sandbox tests the PATTERN, not the optimal config.

## Why split extraction from retrieval

Spec row 9's claim is that **library-driven retrieval** beats agent-driven memory tool calls. The retrieval layer is the load-bearing piece of that argument — it's what runs on every chat turn before the model. Extraction runs once-per-conversation, which is a different latency budget. Testing them separately gives clean signal on each axis.

## Hermetic config

| Layer | Pick | Reason |
|---|---|---|
| Embedder | `sentence-transformers/all-MiniLM-L6-v2` (HuggingFace) | No API key; pip-installable; CPU-fast (~5ms/embedding) |
| Vector store | `faiss-cpu` (local file-backed) | No server; deterministic; cross-platform |
| LLM | Stub OpenAI config | Never actually called because `infer=False` |

## How to interpret

| Verdict | What it means |
|---|---|
| CONFIRMED on both | Mem0 retrieval works as advertised on this workload. Pattern (library-driven retrieval) holds for spec row 9 |
| REFUTED on recall | Mem0's vector search isn't retrieving the obvious matches. Likely embedding model issue, or Mem0's reranking is broken |
| REFUTED on cross-user-leak | **SECURITY BUG** — Mem0 is returning memories across user_id boundaries. The user_id parameter isn't being honored. This is the structural-invariant version of "your harness is wrong" — the sandbox is correctly wired but Mem0 has a regression |

## Discovered upstream bug (Mem0 v2)

Building this sandbox surfaced a real Mem0 v2 score-normalization bug
worth filing upstream:

- The MOST RECENTLY ADDED memory always reports `score=1.0` regardless of
  query relevance. Earlier memories report their actual cosine similarity
  (e.g. 0.73 for a perfect semantic match). Reproduced on both `faiss` and
  `chroma` vector store providers, suggesting the bug is in Mem0's
  result-formatting layer, not provider-specific.
- Effect: when a user has MORE memories than top_k, the wrong memory gets
  ranked first and the correct match can be cut from the result set.
- Workaround in this sandbox: the workload caps each user to ≤10 memories,
  matching top_k=10. With user_id filter scoping retrieval to the user's
  full corpus AND k covering it, ranking quality doesn't determine which
  memories return — they all return.
- Follow-up sandbox slot needed: `mem0-ranking-quality-at-bounded-top-k`
  (testing the case where user has MORE memories than top_k and retrieval
  must rank correctly to surface the right ones). Stays INACTIVE pending
  Mem0 upstream fix or a v3 release without the recency-bias bug.

This sandbox therefore tests a **bounded subset of spec row 9's claim**:
library-driven retrieval correctly returns all user-scoped memories when
top_k covers the per-user corpus. The harder case (top_k < per-user count)
is captured by the follow-up sandbox above.

## Source

Spec v0.4 row 9 — "Mem0 v3 + OpenMemory MCP local mode. v0.3 reaffirmation with stronger evidence: Mem0 v3 hits 91.6 LoCoMo / 93.4 LongMemEval at ~7000 tokens/retrieval; library-driven retrieval (no agent decision required) is structurally aligned with the small-model thesis."

This sandbox does NOT validate the 91.6 LoCoMo number directly (different workload). It validates that the LIBRARY-DRIVEN RETRIEVAL PATTERN works on a hermetic test. The LoCoMo number itself stays in the still-INACTIVE `mem0-v3-locomo` sandbox pending real Mem0 v3 + real LoCoMo data.
