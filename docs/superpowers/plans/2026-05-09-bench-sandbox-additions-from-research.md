# Bench Framework — Sandbox Additions from Memory Research

> **Status:** Plan only — these sandboxes get implemented when Track C (bench framework scaffold) executes per [`2026-05-08-ocm-bench-framework-plan.md`](2026-05-08-ocm-bench-framework-plan.md).
> **Date:** 2026-05-09
> **Source:** [`research/2026-05-09-memory-context-retrieval-deep-dive.md`](../research/2026-05-09-memory-context-retrieval-deep-dive.md) Section 6.4

This document is a paste-ready set of `expected.json` files for **7 new isolation sandboxes** that confirm or refute the load-bearing claims from the memory deep-dive research. Each sandbox follows the pattern from the bench framework plan (`expected.json` + `docker-compose.yml` + `bench.py` + `README.md`), but only the `expected.json` is committed in this plan — the runtime artifacts get written when the sandbox is implemented.

## Why these specific sandboxes

The memory deep-dive research locked in some decisions (Mem0 over Letta) and surfaced new concerns (MemoryArena multi-session interdependent tasks). **The bench framework's job is to confirm or refute every claim before it becomes a user-facing feature.** These 7 sandboxes are the highest-leverage measurements for the v1 stack:

1. Confirm Mem0 v3's headline number (91.6 LoCoMo, 93.4 LongMemEval) reproduces with **Llama 3.1 8B** specifically (vendor numbers were on stronger models)
2. Validate the agentic-utility caveat (MemoryArena drop) — ensures we're not optimizing for the wrong metric
3. Test the "filesystem + grep is enough" counterexample from Letta's own benchmark
4. Quantify the Cognee 8B graph-quality risk (so we have hard evidence if/when we recommend the borrow-stronger-model workaround)
5. Confirm Aider repomap fidelity transfers to general structured corpora
6. Validate Continue.dev's hybrid retrieval pattern as the OCM blueprint
7. Prove DSPy GEPA skill portability (the v2+ network-effect lever)

## Sandbox 1 — Mem0 v3 LoCoMo recall on Llama 8B

**Path:** `bench/isolation/memory-layers/mem0-v3-llama8b-locomo/expected.json`

```json
{
  "hypothesis_id": "mem0-v3-llama8b-locomo",
  "claim": "Mem0 v3 single-pass extraction with Llama 3.1 8B Q4 hits >=85% accuracy on LoCoMo with average <=8000 tokens per retrieval call",
  "metric": "locomo_accuracy_pct",
  "thresholds": {"confirm_at_least": 85.0, "refute_below": 75.0},
  "secondary_metric": "avg_retrieval_tokens",
  "secondary_thresholds": {"confirm_at_most": 8000, "refute_above": 12000},
  "workload": "locomo-full.jsonl",
  "source_for_claim": "https://mem0.ai/blog/mem0-the-token-efficient-memory-algorithm",
  "timeout_seconds": 3600
}
```

**What this confirms or refutes:** Whether Mem0's published numbers (which were on stronger models in some cases) hold up on the 8B class OCM v1 actually targets. If REFUTED, OCM has to revise the model recommendation or the memory layer.

## Sandbox 2 — Mem0 v3 MemoryArena (interdependent multi-session)

**Path:** `bench/isolation/memory-layers/mem0-v3-llama8b-memoryarena/expected.json`

```json
{
  "hypothesis_id": "mem0-v3-llama8b-memoryarena",
  "claim": "Mem0 v3 with Llama 3.1 8B Q4 maintains >=60% on MemoryArena interdependent tasks (vs LoCoMo near-saturation), confirming agentic-memory utility not just recall",
  "metric": "memoryarena_avg_pct",
  "thresholds": {"confirm_at_least": 60.0, "refute_below": 40.0},
  "workload": "memoryarena-multisession.jsonl",
  "source_for_claim": "https://arxiv.org/abs/2602.16313",
  "timeout_seconds": 7200
}
```

**Why this is critical:** Stanford's MemoryArena paper (2026) shows agents at near-100% on LoCoMo plummet to 40-60% on multi-session interdependent tasks. **LoCoMo near-saturation does NOT prove the memory layer is delivering useful agentic capability.** If our Mem0 sandbox lands in the 40-60% band on MemoryArena, we know we're optimizing for the wrong metric and need to course-correct user-facing claims.

## Sandbox 3 — Letta filesystem pattern on Llama 8B

**Path:** `bench/isolation/memory-layers/letta-filesystem-llama8b-locomo/expected.json`

```json
{
  "hypothesis_id": "letta-filesystem-llama8b-locomo",
  "claim": "Letta's 'filesystem + grep' agentic memory pattern with Llama 3.1 8B Q4 hits >=70% on LoCoMo (Letta claims 74% with GPT-4o-mini)",
  "metric": "locomo_accuracy_pct",
  "thresholds": {"confirm_at_least": 70.0, "refute_below": 55.0},
  "workload": "locomo-full.jsonl",
  "source_for_claim": "https://www.letta.com/blog/benchmarking-ai-agent-memory",
  "timeout_seconds": 3600,
  "decision_rule": "If small-model filesystem pattern lands within 10pp of Mem0 v3, consider this as a simpler default for technically-inclined users."
}
```

**Why include this:** Letta's claim that "filesystem + grep" is enough deserves an honest test. Mem0 has more architecture; if simpler-pattern reaches similar quality on small models, the bench framework reveals that and we adjust accordingly. The decision rule is explicit.

## Sandbox 4 — Cognee 8B graph quality (testing the noisy-graph claim)

**Path:** `bench/isolation/memory-layers/cognee-llama8b-graph-quality/expected.json`

```json
{
  "hypothesis_id": "cognee-llama8b-graph-quality",
  "claim": "Cognee's graph extraction with Llama 3.1 8B Q4 produces graphs with <=20% hallucinated edges (Cognee docs claim >=90% hallucination at 8B; this tests our mesh-borrow workaround)",
  "metric": "hallucinated_edge_pct",
  "thresholds": {"confirm_at_most": 20.0, "refute_above": 50.0},
  "workload": "personal-conversation-corpus-1k-utterances.jsonl",
  "source_for_claim": "https://www.glukhov.org/ai-systems/memory/choosing-right-llm-for-cognee-on-ollama",
  "timeout_seconds": 1800
}
```

**What this tests:** Cognee explicitly recommends 32B+ models. Our v2+ "borrow a stronger model from a contributor for graph ingest" pattern depends on this being true (otherwise why borrow?). This sandbox validates the claim and quantifies the gap.

## Sandbox 5 — Aider repomap fidelity (1k-token PageRank compression)

**Path:** `bench/isolation/sub-context-retrieval/aider-repomap-1k-pagerank/expected.json`

```json
{
  "hypothesis_id": "aider-repomap-1k-pagerank-fidelity",
  "claim": "Aider repomap PageRank + tree-sitter compressed view of a 100k-LoC corpus, at 1k token budget, retains >=80% of identifiers needed to answer a held-out set of 50 code-comprehension questions",
  "metric": "identifier_recall_pct",
  "thresholds": {"confirm_at_least": 80.0, "refute_below": 65.0},
  "workload": "selfhost-codebase-100kloc + comprehension-50q.jsonl",
  "source_for_claim": "https://aider.chat/docs/repomap.html",
  "timeout_seconds": 1200
}
```

**Why include this:** Aider's repomap is a **deterministic** compressed-view technique with no LLM call at retrieval time — uniquely suited to the small-model thesis. If it preserves 80%+ of needed identifiers at 1k tokens, OCM should adopt it as a generic structured-corpus tool (code, conversation logs, docs).

## Sandbox 6 — Continue.dev hybrid vs pure-vector

**Path:** `bench/isolation/sub-context-retrieval/continue-hybrid-vs-pure-vector/expected.json`

```json
{
  "hypothesis_id": "continue-hybrid-vs-pure-vector",
  "claim": "Continue.dev's hybrid retrieval (LanceDB + ripgrep + LLM rerank) outperforms pure vector RAG by >=10pp on a code-question benchmark with Llama 3.1 8B Q4",
  "metric": "code_qa_accuracy_pct_delta",
  "thresholds": {"confirm_at_least": 10.0, "refute_below": 3.0},
  "workload": "code-questions-100q.jsonl",
  "source_for_claim": "https://lancedb.com/blog/the-future-of-ai-native-development-is-local-inside-continues-lancedb-powered-evolution/",
  "timeout_seconds": 1800
}
```

**Why include this:** Continue.dev's hybrid pattern (semantic + keyword + LLM rerank) is the production blueprint OCM v1 wants to lift wholesale for code context. The bench framework needs to confirm the +10pp delta over pure vector before we lock the architecture.

## Sandbox 7 — DSPy GEPA skill portability

**Path:** `bench/isolation/skill-federation/dspy-gepa-skill-portability/expected.json`

```json
{
  "hypothesis_id": "dspy-gepa-skill-portability",
  "claim": "A DSPy GEPA-compiled skill for 'extract entities from agent conversation' transferred via program.save/program.load reproduces accuracy within 2pp of in-process compilation",
  "metric": "skill_accuracy_pct_delta",
  "thresholds": {"confirm_at_most": 2.0, "refute_above": 5.0},
  "workload": "entity-extraction-200samples.jsonl",
  "source_for_claim": "https://dspy.ai/api/optimizers/GEPA/overview/",
  "timeout_seconds": 3600
}
```

**Why include this:** This sandbox validates **OCM's actual network-effect lever**. If skills don't reproduce after save/load, the entire "federated skill marketplace" v2+ thesis falls apart. We need to confirm portability before architecting the mesh's skill-distribution layer.

## Workload datasets needed

These sandboxes require workload files in `bench/workloads/`. Some are public datasets (need download scripts); some are synthesized:

| Workload file | Source | Synthesis needed? |
|---|---|---|
| `locomo-full.jsonl` | LoCoMo public dataset (Mem0/Letta papers) | Download + reformat |
| `memoryarena-multisession.jsonl` | MemoryArena public release (Stanford 2026) | Download + reformat |
| `personal-conversation-corpus-1k-utterances.jsonl` | Synthesize 1k diverse conversational utterances with known ground-truth entities | Generate + manually annotate |
| `selfhost-codebase-100kloc + comprehension-50q.jsonl` | Use OCM repo or sibling project as the 100kLoC corpus; hand-author 50 comprehension questions | Hand-author |
| `code-questions-100q.jsonl` | Public code-QA datasets (CodeQA, MBPP) + 50 hand-authored | Hybrid |
| `entity-extraction-200samples.jsonl` | Synthesize 200 conversation samples with annotated entities | Generate |

## Integration points with the bench framework

These sandboxes plug into the existing framework structure:

```
bench/
├── isolation/
│   ├── memory-layers/                          # Sandboxes 1, 2, 3, 4
│   │   ├── mem0-v3-llama8b-locomo/
│   │   ├── mem0-v3-llama8b-memoryarena/
│   │   ├── letta-filesystem-llama8b-locomo/
│   │   └── cognee-llama8b-graph-quality/
│   ├── sub-context-retrieval/                  # Sandboxes 5, 6
│   │   ├── aider-repomap-1k-pagerank/
│   │   └── continue-hybrid-vs-pure-vector/
│   └── skill-federation/                       # Sandbox 7 (new category)
│       └── dspy-gepa-skill-portability/
└── workloads/
    ├── locomo-full.jsonl
    ├── memoryarena-multisession.jsonl
    ├── personal-conversation-corpus-1k-utterances.jsonl
    ├── code-questions-100q.jsonl
    └── entity-extraction-200samples.jsonl
```

## Decision rules

The 7 hypothesis verdicts cumulatively determine real OCM design decisions:

| Combined verdict | OCM action |
|---|---|
| All 7 CONFIRMED | Lock spec as-is; ship v1 with confidence |
| Sandbox 1 REFUTED (Mem0 LoCoMo doesn't reach 85% on 8B) | Revisit memory layer choice OR upgrade default model recommendation to 13B+ |
| Sandbox 2 REFUTED (MemoryArena <40%) | Pivot user-facing claims away from "persistent memory just works"; document constraint clearly |
| Sandbox 3 CONFIRMED at >=70% (filesystem within 10pp of Mem0) | Add filesystem pattern as a "simpler alternative" for advanced users; preserve Mem0 as default |
| Sandbox 4 CONFIRMED (Cognee 8B graphs <=20% hallucination) | Cognee becomes viable on 8B; revisit; potentially adopt as alternative graph option |
| Sandbox 4 REFUTED (Cognee 8B graphs >50% hallucinated) | Confirms our v2+ "borrow stronger model" workaround is necessary; lock the architecture |
| Sandbox 5 CONFIRMED | Adopt repomap as a generic OCM tool (code + memory + docs) |
| Sandbox 6 CONFIRMED | Lock Continue.dev hybrid as the OCM code-context blueprint |
| Sandbox 7 REFUTED (skills don't transfer cleanly) | Federated-skill thesis breaks; v2+ network-effect story needs replacement |

## Priority order for implementation

When the bench framework scaffold lands (Track C of master operations plan), implement these in order:

1. **Sandbox 1 (Mem0 LoCoMo)** — locks v1's headline metric
2. **Sandbox 2 (MemoryArena)** — critical sanity check; cheap to validate
3. **Sandbox 6 (Continue hybrid)** — locks v1 code-context architecture
4. **Sandbox 5 (Aider repomap)** — locks generic compressed-view tool
5. **Sandbox 7 (DSPy skill portability)** — gates v2+ network-effect story
6. **Sandbox 3 (Letta filesystem)** — counter-evidence check
7. **Sandbox 4 (Cognee 8B graph)** — confirms v2+ borrow-stronger-model architecture

Sandboxes 1-4 use the same model (Llama 3.1 8B Q4) and overlap heavily; build the harness once, instantiate four times.
