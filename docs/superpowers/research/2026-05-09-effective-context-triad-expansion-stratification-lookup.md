# Effective-Context Triad: Expansion, Stratification, Quick Look-Up

**Date:** 2026-05-09
**Trigger:** User-articulated three-word architectural principle for OCM's effective-context advantage over frontier closed AI: *expansion, stratification, quick look-up*. This document defines the triad as a cross-cutting design constraint that every layer of the OCM stack must satisfy, names the existing-locked-decision mechanisms that satisfy it, and identifies the gaps that v3.5+ Memory Palace work fills.

## The triad, defined

OCM cannot beat frontier closed AI on raw single-call context window. Claude Opus 4.7's 1M tokens, Gemini 2.5's 2M tokens — these are hardware-economics realities of running 70B+ dense models with sufficient KV cache. OCM's small-model thesis explicitly trades that battle.

But effective context — the knowledge an agent can *actually use to do its job* — is not a single number. It splits into three properties:

| Property | What it is | What frontier offers | What OCM can offer |
|---|---|---|---|
| **Expansion** | Total corpus the agent can reach | ~1M-2M tokens per call; static training cutoff | GB-to-TB across local + palace + subscribed mesh palaces |
| **Stratification** | Layered organization with appropriate routing | Single flat working window; everything competes for the same attention | Working ctx → Mem0 → personal palace → mesh palaces, each layer has its own retrieval policy |
| **Quick look-up** | Time-to-relevant-chunk | ~3-30s for hard questions through full 1M ctx | <500ms local index + <2s mesh search |

**A system that wins on all three simultaneously beats frontier on the dimension users actually feel** — "did the agent know enough to give me the right answer fast." Frontier wins single-call breadth; OCM wins multi-call depth with structure.

## Mapping each triad property to OCM's locked architecture

### EXPANSION — five mechanisms compound to grow effective corpus

Each is already a locked decision in the spec; together they multiply:

| Mechanism | Spec decision | What it expands |
|---|---|---|
| Mem0 v3 + OpenMemory MCP | row 9 (locked v1) | Local episodic memory, unbounded by disk |
| Aider repomap pattern | row 24 (locked v1) | Compressed structured-corpus view; ~70% token reduction at fixed budget |
| Continue.dev hybrid retrieval | row 25 (locked v1) | Local-first hybrid (vector + keyword + rerank) over arbitrary local corpus |
| DSPy GEPA skill federation | row 23 (locked v2+) | Compiled skills act as context-compressors — turn arbitrary corpus into task-relevant 1K tokens |
| Decentralized Memory Palace | row 26 (locked v3.5+) | Mesh-federated knowledge artifacts; cross-user curated corpus |

**Stack-up math:** local Mem0 (~100M tokens accessible) × personal palace (~10M tokens curated) × 5 subscribed mesh palaces (~50M tokens cumulative) × DSPy compiled skill compression ratio (~10× density advantage on specific tasks) = **effective accessible corpus on the order of 5-50 billion tokens**.

For comparison: Claude Opus 4.7 with full 1M context window can process 1M tokens of context per inference call. OCM has 1000-50000× more accessible corpus, traded for the requirement of multi-call retrieval-then-reason patterns.

### STRATIFICATION — six layers with explicit retrieval policies

The architecture explicitly stratifies by layer; each layer has a retrieval policy that determines when the agent reaches into it:

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 6: Cross-mesh model borrowing (v3+)                       │
│  Trigger: ingest of large-context tasks (entity extraction,      │
│  graph building, document distillation)                          │
│  Policy: borrow strong model from contributor; serve to local    │
│  Latency budget: 5-30s acceptable (offline-style)                │
└──────────────────────────────────────────────────────────────────┘
                              ▲
┌──────────────────────────────────────────────────────────────────┐
│  Layer 5: Subscribed mesh palaces (v3.5+)                        │
│  Trigger: agent's local sources don't return high-confidence    │
│  results; topic matches subscribed palace tags                   │
│  Policy: query 5+ palaces in parallel; rerank; cite provenance  │
│  Latency budget: 1-3s p50                                        │
└──────────────────────────────────────────────────────────────────┘
                              ▲
┌──────────────────────────────────────────────────────────────────┐
│  Layer 4: Personal palace (v3.5+)                                │
│  Trigger: same as L5 but checked first for freshness/relevance  │
│  Policy: BM25 + embedding + tag filter; cite specific node      │
│  Latency budget: <500ms p50                                      │
└──────────────────────────────────────────────────────────────────┘
                              ▲
┌──────────────────────────────────────────────────────────────────┐
│  Layer 3: Aider-style compressed views (v1)                      │
│  Trigger: agent works on a structured corpus (code/docs/logs)    │
│  Policy: PageRank + tree-sitter compression to fit budget       │
│  Latency budget: <100ms (deterministic, no LLM call)            │
└──────────────────────────────────────────────────────────────────┘
                              ▲
┌──────────────────────────────────────────────────────────────────┐
│  Layer 2: Local Mem0 episodic (v1)                               │
│  Trigger: every chat turn — library-driven retrieval auto-runs  │
│  Policy: ~7000 tokens/retrieval (Mem0 v3 token-efficient algo)  │
│  Latency budget: <300ms p50                                      │
└──────────────────────────────────────────────────────────────────┘
                              ▲
┌──────────────────────────────────────────────────────────────────┐
│  Layer 1: Working context (32K-128K tokens, per inference)       │
│  Trigger: every model call                                       │
│  Policy: built into Llama 3.1 8B / Qwen3-30B-A3B inference      │
│  Latency budget: native to the model                             │
└──────────────────────────────────────────────────────────────────┘
```

The arrow is one-way for retrieval (each layer can pull from layers above it) and one-way for write (curate downward only — Layer 1 can decide to write into Layer 2 / 4 / 5; never the reverse). Privacy zones (defined in Memory Palace research note section 6) determine *what* can flow between layers, with layers 4 and 5 honoring `mesh: public` frontmatter as the hard gate.

**The non-obvious property:** the agent doesn't have to *know* this stratification exists. The MCP retrieval tools (`palace_search`, `palace_read`, Mem0's automatic retrieval) abstract it. From the agent's perspective, there's just "retrieve relevant context" — the policy layer decides which physical layer answers.

### QUICK LOOK-UP — three latency budgets stacked

The retrieval pipeline must respect human-perceptible latency at each layer:

| Layer | Latency budget | Mechanism | Falls back to |
|---|---|---|---|
| Local Mem0 retrieval | <300ms p50 | sqlite-vec + BM25 + Mem0 v3 token-efficient algo | next layer if confidence low |
| Personal palace search | <500ms p50 | local git index + tree-sitter chunk + embedding cache | next layer if confidence low |
| Mesh palace search | <2000ms p50 | parallel queries to subscribed peers; rerank; cite | give up + tell user "I don't know" |
| Cross-mesh model borrow | 5-30s acceptable | offline-style; not on chat critical path | use locally available model if borrow times out |

**Engineering principle:** every layer must answer within its budget *or get out of the way*. A user typing a question into OCM should see first-token latency comparable to a frontier API (1-3s) — the multi-layer stratification happens *behind* that latency budget, with cheap layers always running first and expensive layers only invoked when cheap ones don't return high-confidence results.

This is the same pattern that makes vLLM's continuous batching feel responsive despite high contention: the cheap path is always cheap, expensive paths kick in only when needed.

## Why this triad is OCM's specific competitive advantage

Frontier closed AI optimizes for **expansion only** — the working window keeps growing (1M, 2M, soon 10M). They have no stratification (everything competes in the same attention window) and no cross-conversation persistence (look-up is bounded by the conversation, which resets per session).

OCM optimizes for **all three simultaneously** — moderate working window, rich stratification, fast retrieval at every layer. The triad lets OCM trade single-call breadth for multi-call depth-with-structure.

| Comparison axis | Frontier (e.g. Opus 4.7) | OCM mesh-augmented |
|---|---|---|
| Expansion (corpus reachable per task) | 1M-2M tokens per call | 5-50 GB across layers |
| Stratification (organized layers) | Flat: just the working window | 6-layer hierarchy with explicit policies |
| Quick look-up (time-to-relevant-chunk) | 3-30s through full window | <500ms local + <2s mesh |
| Cross-session persistent | No (resets per call) | Yes (Mem0 + palace) |
| Cross-user federated | No | Yes (mesh palaces) |
| Citation provenance | Generates plausibly | Returns specific node references |

Notice: OCM doesn't win EVERY axis. Frontier wins single-call breadth + raw model capability. OCM wins persistence + federation + citation. **The triad framing makes clear that "context" is at least 6 distinct properties, and OCM only commits to winning the 4 that compound with each other.**

## Engineering implications — what every component must satisfy

This triad becomes a *constraint* on every future OCM design decision. When v3.5 Memory Palace is implemented, when v6 sharded inference is implemented, when any new MCP tool is added, the question is:

1. **Does this expand effective corpus?** (or contract it — bad)
2. **Does this respect stratification?** (i.e., does it bypass the cheap layer when the expensive layer would do; if so, why)
3. **Does this preserve quick look-up at every layer?** (i.e., does it respect the latency budget for its layer)

A v3.5 Memory Palace implementation that takes 10s to search a 5GB corpus *fails the triad* even though it expands corpus, because it violates the "quick look-up" requirement at layer 4 / 5. The fix is index design (BM25 + embedding cache + tag indices + citation graph), not "live with slow search." This is *engineering discipline* the triad imposes.

Equally: a v3 reciprocity ledger that requires the agent to query 10 ledger nodes in series before answering any question fails stratification — the ledger should be Layer 6 (rare, high-value) not Layer 1 (every-turn). This is *architectural discipline* the triad imposes.

## Bench-framework instrumentation

Sandbox F (added to the [frontier comparison bench suite](../plans/2026-05-09-frontier-comparison-bench-suite.md)) explicitly measures the triad:

- **Quality delta** (≥20pp over Opus 4.7) measures whether expansion + stratification combined produce a real user-facing benefit
- **Citation accuracy** (≥80%) measures whether stratification preserves provenance
- **Retrieval latency p50** (≤2s) measures whether quick look-up holds across the full corpus

If Sandbox F confirms on all three thresholds, the triad is empirically validated. If it confirms on quality but fails on latency, the architecture is right but the index pipeline needs work. If it fails on quality, the federation thesis itself needs revisiting.

**This is the load-bearing measurement of OCM's effective-context advantage** — a single benchmark whose verdict determines whether v3.5+ work proceeds as planned or gets fundamentally reconsidered.

## What this triad changes about how OCM presents itself

If we land on the triad as the architectural principle, OCM's user-facing pitch evolves from generic "free agent with persistent memory" to specific:

> Frontier closed AI gives you 1 million tokens per call. OCM gives you a structured 5-gigabyte knowledge environment your agent can search in under 2 seconds, accumulating across sessions and across the contributor mesh. We compete on what's *useful* about context, not how big it is.

That's a sharper, more defensible pitch than "we're a free alternative to OpenAI." It's a pitch grounded in a measurable architectural property, not a marketing claim. **And it's a pitch that *only* makes sense as a mesh project — single-user OCM is just a personal-AI clone of existing tools, and frontier closed AI does single-call context better. The mesh + stratification + federation is what creates the structural niche.**

## Summary

OCM's effective-context advantage rests on three properties simultaneously, all of which must be engineered into every component:

- **EXPANSION** — by stacking borrowed primitives (Mem0 + palace + mesh + skill compression + cross-mesh model borrowing), accessible corpus reaches 5-50 GB
- **STRATIFICATION** — six layers with explicit retrieval policies and latency budgets, so the cheap path is always cheap
- **QUICK LOOK-UP** — every layer respects its latency budget; expensive layers only invoke when cheap layers return low confidence

Frontier closed AI competes on expansion alone. OCM competes on all three simultaneously, structurally — because that's what the mesh + multi-tier memory architecture enables.

This is the architectural principle that justifies the v0.4 Memory Palace addition (decision row 26), the Sandbox F frontier-comparison measurement, and the cross-cutting engineering discipline OCM enforces on every future feature.

---

## Sources backing this note

- [v0.4 spec decision row 26 — Decentralized Memory Palace](../specs/2026-05-08-ocm-v1-design-spec.md)
- [Memory Palace pattern analysis](2026-05-09-decentralized-memory-palace-pattern.md)
- [Frontier comparison bench suite — Sandbox F](../plans/2026-05-09-frontier-comparison-bench-suite.md)
- [Memory + sub-context retrieval deep dive](2026-05-09-memory-context-retrieval-deep-dive.md) — primary research on layers 1-3
- [Tool landscape synthesis](2026-05-08-tool-landscape-synthesis.md) — primary research on layers 5-6 (mesh + skill federation)
