# Sandbox: aider-repomap-fidelity

**Hypothesis:** Repomap-style compression (NetworkX PageRank + tree-sitter) preserves ≥85% of code-Q&A accuracy at 30% of the token budget. Spec v0.3 row 24 locks repomap as the v1 compressed-view tool.

**Status:** INACTIVE — code-Q&A workload not yet curated; MCP code-aware tool layer not yet wired.

## What this measures (once active)

- **code_qa_accuracy_at_30pct_tokens**: accuracy on a code-Q&A suite, comparing repomap-compressed context to a full-context baseline
- **tokens_used_p50**: median token budget per query

## Pair with

`retrieval/continuedev-hybrid-retrieval` covers the production-blueprint hybrid stack. Repomap is the deterministic / no-LLM-at-retrieval-time compressed view; Continue.dev's hybrid is the LLM-rerank approach. Both feature in the spec v0.3 retrieval revisions.

## Source for the claim

- Aider's repomap implementation
- Repomix `--compress` (tree-sitter) benchmarks
- Spec v0.3 row 24 + research note `2026-05-09-decentralized-memory-palace-pattern.md`
