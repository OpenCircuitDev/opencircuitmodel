# Sandbox: continuedev-hybrid-retrieval

**Hypothesis:** Continue.dev's hybrid retrieval (LanceDB + ripgrep + LLM rerank, all local) outperforms pure vector RAG by ≥10 points on code-context Q&A. Spec v0.3 row 25 lock candidate.

**Status:** INACTIVE — code-Q&A workload + LanceDB pipeline not yet wired.

## Pair with

- `retrieval/aider-repomap-fidelity` — alternate compressed-view approach (deterministic, no LLM at retrieval time)
- `retrieval/pure-vector-rag-baseline` (planned) — the comparison anchor

The spec v0.3 picks both repomap (row 24) and hybrid (row 25). Repomap is the v1 default; hybrid is the production-grade blueprint to lift when MCP code tooling matures.

## Source for the claim

Continue.dev open-source design docs + production telemetry. Research note `2026-05-09-decentralized-memory-palace-pattern.md` cites the head-to-head against pure vector RAG.
