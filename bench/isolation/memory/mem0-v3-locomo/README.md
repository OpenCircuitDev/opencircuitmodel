# Sandbox: mem0-v3-locomo

**Hypothesis:** Mem0 v3 (library-driven retrieval) achieves ≥88 LoCoMo recall on small-model setup, within 4 points of the published 91.6 figure on larger models. Library-driven retrieval is the directly-aligned pattern for the small-model thesis.

**Status:** INACTIVE — workload + harness not yet wired.

## What this measures (once active)

- **LoCoMo recall**: standard memory-retrieval benchmark across multi-session conversations
- **tokens_retrieved_p50**: median tokens injected as retrieval context per turn

## What this does NOT measure

- Multi-session interdependent task quality — that's MemoryArena (separate sandbox: `memory/mem0-v3-memoryarena`)
- Generation quality on retrieved context — orthogonal; see chat-quality sandboxes
- Agent-driven memory orchestration — that's Letta's paradigm, see `memory/letta-tool-memory`

## How to interpret

| Verdict | What it means |
|---|---|
| CONFIRMED | Library-driven retrieval is structurally aligned with small-model thesis; v0.4 row 9 lock holds |
| REFUTED on recall | Investigate Qwen3 8B's retrieval-context utilization or Mem0 v3 config tuning |
| REFUTED on tokens | 7000 token budget is too optimistic; revisit Effective-Context Triad quick-look-up budget |
| INCONCLUSIVE | Variance too high; expand workload size or repeat count |

## Source for the claim

Mem0 v3 release notes (April 2026), pinned in research note `docs/superpowers/research/2026-05-09-decentralized-memory-palace-pattern.md`.
